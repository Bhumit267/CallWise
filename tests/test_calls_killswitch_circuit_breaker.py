"""Tests for kill switch, circuit breaker, abuse protection, and alert notifications."""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest
import pytest_asyncio
from sqlalchemy import select

from callwise.agent.circuit_breaker import CircuitBreakerRegistry, CircuitState, ProviderCircuit, circuit_breaker
from callwise.agent.text_agent import TextAgent
from callwise.calls.abuse import (
    add_to_blocklist,
    check_caller_rate_limit,
    detect_nonsense_repetition,
    is_caller_blocked,
    list_blocklist_entries,
    remove_from_blocklist,
)
from callwise.calls.killswitch import (
    FALLBACK_MESSAGE_TAKING_PROMPT,
    KILL_SWITCH_FILE,
    disable_kill_switch,
    enable_kill_switch,
    get_kill_switch_status,
    is_kill_switch_active,
)
from callwise.config import settings
from callwise.db.models import BlocklistEntry, Business, Call, Notification, PhoneNumber
from callwise.db.session import get_async_session
from callwise.notifications.service import notify_abuse_detected, notify_circuit_breaker_tripped
from callwise.telephony.router import resolve_inbound_call_async


@pytest.fixture(autouse=True)
def cleanup_killswitch_file():
    """Ensure killswitch file is cleared before and after each test."""
    if KILL_SWITCH_FILE.exists():
        KILL_SWITCH_FILE.unlink(missing_ok=True)
    yield
    if KILL_SWITCH_FILE.exists():
        KILL_SWITCH_FILE.unlink(missing_ok=True)
    circuit_breaker.reset_all()


@pytest_asyncio.fixture
async def sample_business():
    """Create a test business tenant."""
    async with get_async_session() as session:
        biz = Business(
            id=uuid.uuid4(),
            name="Apex Dental Clinic",
            business_type="Dental",
            greeting="Hello and welcome to Apex Dental Clinic.",
            tone="Professional",
            timezone="America/New_York",
            notification_email="owner@apexdental.com",
            hours={
                "monday": {"open": "08:00", "close": "17:00", "closed": False},
                "tuesday": {"open": "08:00", "close": "17:00", "closed": False},
            },
        )
        session.add(biz)
        await session.commit()
        await session.refresh(biz)
        return biz


# =========================================================================
# 1. KILL SWITCH TESTS
# =========================================================================

def test_killswitch_file_toggle():
    """Test dynamic enabling and disabling of kill switch via state file."""
    assert not is_kill_switch_active()

    status_before = get_kill_switch_status()
    assert not status_before["active"]

    # Enable
    data = enable_kill_switch(reason="Emergency DB Maintenance", activated_by="ops_team")
    assert data["active"]
    assert is_kill_switch_active()
    assert KILL_SWITCH_FILE.exists()

    status_after = get_kill_switch_status()
    assert status_after["active"]
    assert status_after["dynamic_enabled"]
    assert status_after["reason"] == "Emergency DB Maintenance"
    assert status_after["activated_by"] == "ops_team"
    assert status_after["message"] == FALLBACK_MESSAGE_TAKING_PROMPT

    # Disable
    disable_kill_switch()
    assert not is_kill_switch_active()
    assert not KILL_SWITCH_FILE.exists()


def test_killswitch_env_setting(monkeypatch):
    """Test environment variable kill switch activation."""
    assert not is_kill_switch_active()

    monkeypatch.setattr(settings, "kill_switch_enabled", True)
    assert is_kill_switch_active()
    status = get_kill_switch_status()
    assert status["active"]
    assert status["env_enabled"]


@pytest.mark.asyncio
async def test_text_agent_kill_switch_active(sample_business):
    """Test that TextAgent immediately diverts to message taking when kill switch is on."""
    enable_kill_switch(reason="Testing killswitch")

    agent = TextAgent(business=sample_business)
    reply = await agent.ask("Hello, I would like to book a dental checkup.")

    assert reply == FALLBACK_MESSAGE_TAKING_PROMPT
    assert "maintenance" in reply.lower()
    assert "take down your name" in reply.lower()


@pytest.mark.asyncio
async def test_telephony_router_kill_switch_active(sample_business):
    """Test that inbound call router diverts to message taking on active kill switch."""
    import random
    test_number = f"+1800555{random.randint(1000, 9999)}"
    async with get_async_session() as session:
        phone = PhoneNumber(
            id=uuid.uuid4(),
            business_id=sample_business.id,
            e164_number=test_number,
            provider="livekit",
            is_active=True,
        )
        session.add(phone)
        await session.commit()

    enable_kill_switch(reason="Router kill switch test")

    result = await resolve_inbound_call_async(
        dialed_number=test_number,
        caller_number="+15559998888",
    )

    assert result.matched
    assert result.reject_reason == "kill_switch_active"
    assert result.reply_message == FALLBACK_MESSAGE_TAKING_PROMPT


# =========================================================================
# 2. CIRCUIT BREAKER TESTS
# =========================================================================

def test_circuit_breaker_transitions():
    """Test ProviderCircuit state machine: CLOSED -> OPEN -> HALF_OPEN -> CLOSED."""
    tripped_events = []

    circuit = ProviderCircuit(
        provider="test_llm",
        failure_threshold=3,
        recovery_seconds=2,
        on_trip=lambda prov, count: tripped_events.append((prov, count)),
    )

    # Initial state
    assert circuit.state == CircuitState.CLOSED
    assert circuit.is_available()

    # 1 failure
    circuit.record_failure(ValueError("timeout"))
    assert circuit.state == CircuitState.CLOSED
    assert circuit.consecutive_failures == 1
    assert circuit.is_available()

    # 2 failures
    circuit.record_failure(ValueError("500 internal error"))
    assert circuit.state == CircuitState.CLOSED
    assert circuit.consecutive_failures == 2
    assert circuit.is_available()

    # 3 failures -> trips to OPEN
    circuit.record_failure(ValueError("rate limited 429"))
    assert circuit.state == CircuitState.OPEN
    assert circuit.consecutive_failures == 3
    assert not circuit.is_available()
    assert len(tripped_events) == 1
    assert tripped_events[0] == ("test_llm", 3)

    # Before cooldown
    assert not circuit.is_available()

    # Fast-forward past cooldown
    circuit.last_failure_time = circuit.last_failure_time - 3.0
    assert circuit.is_available()  # transitions to HALF_OPEN
    assert circuit.state == CircuitState.HALF_OPEN

    # Probe succeeds -> transitions to CLOSED
    circuit.record_success()
    assert circuit.state == CircuitState.CLOSED
    assert circuit.consecutive_failures == 0


def test_circuit_breaker_registry_failover():
    """Test registry fails over from primary to fallback when primary trips."""
    registry = CircuitBreakerRegistry()

    # Both start healthy
    selected = registry.select_active_provider(primary="groq", fallback="gemini")
    assert selected == "groq"

    # Trip primary provider
    for _ in range(settings.circuit_breaker_failure_threshold):
        registry.record_failure("groq", RuntimeError("Groq API down"))

    assert not registry.is_available("groq")

    # Failover to secondary
    selected = registry.select_active_provider(primary="groq", fallback="gemini")
    assert selected == "gemini"

    # Trip secondary as well
    for _ in range(settings.circuit_breaker_failure_threshold):
        registry.record_failure("gemini", RuntimeError("Gemini API down"))

    assert not registry.is_available("gemini")

    # Both down -> returns None
    selected = registry.select_active_provider(primary="groq", fallback="gemini")
    assert selected is None


@pytest.mark.asyncio
async def test_text_agent_circuit_breaker_failover(sample_business):
    """Test that TextAgent fails over to secondary provider when primary fails."""
    agent = TextAgent(business=sample_business, provider_name="groq")

    # Mock _run_provider_turn to fail on groq and succeed on gemini
    async def mock_run_turn(provider: str, user_msg: str):
        if provider == "groq":
            raise RuntimeError("Groq rate limit 429")
        return "I am responding from the Gemini fallback provider."

    with patch.object(agent, "_run_provider_turn", side_effect=mock_run_turn):
        reply = await agent.ask("What are your business hours?")

        assert "Gemini fallback" in reply
        # Groq recorded failure, Gemini recorded success
        groq_circuit = circuit_breaker.get_circuit("groq")
        assert groq_circuit.consecutive_failures >= 1


@pytest.mark.asyncio
async def test_text_agent_both_providers_fail_graceful(sample_business):
    """Test that TextAgent degrades gracefully when both AI providers fail."""
    agent = TextAgent(business=sample_business, provider_name="groq")

    async def mock_fail_all(provider: str, user_msg: str):
        raise RuntimeError(f"{provider} failed connection")

    with patch.object(agent, "_run_provider_turn", side_effect=mock_fail_all):
        reply = await agent.ask("Hello, can you help me?")

        assert "technical difficulties" in reply.lower() or "take down your name" in reply.lower()


# =========================================================================
# 3. ABUSE PROTECTION & NONSENSE DETECTION TESTS
# =========================================================================

def test_nonsense_repetition_detection():
    """Test detection of repeated nonsense and keyboard smashing utterances."""
    # Under 3 utterances
    assert not detect_nonsense_repetition(["hello", "how are you"])

    # 3 identical non-empty utterances
    assert detect_nonsense_repetition(["test", "test", "test"])
    assert detect_nonsense_repetition(["hello", "repeat", "repeat", "repeat"])

    # 3 short / single character utterances
    assert detect_nonsense_repetition(["a", "b", "c"])
    assert detect_nonsense_repetition(["ok", "hi", "no"])

    # 3 keyboard smashes
    assert detect_nonsense_repetition(["asdfghjk", "qwertz", "zxcvbnm"])

    # Normal conversation -> False
    assert not detect_nonsense_repetition([
        "Hello, what are your hours?",
        "Do you have appointments tomorrow?",
        "Great, what is the cost of a cleaning?",
    ])


@pytest.mark.asyncio
async def test_text_agent_nonsense_abuse_interception(sample_business):
    """Test that TextAgent catches repeated nonsense and diverts to message taking."""
    agent = TextAgent(business=sample_business, caller_number="+15550001111")

    # Mock LLM to avoid real API calls
    with patch.object(agent, "_run_provider_turn", return_value="Normal reply"):
        await agent.ask("asdfghjk")
        await agent.ask("qwertzuiop")
        # 3rd keyboard smash triggers abuse detection
        reply3 = await agent.ask("zxcvbnm")

        assert "having difficulty understanding" in reply3.lower()
        assert "take down your name" in reply3.lower()


@pytest.mark.asyncio
async def test_blocklist_crud(sample_business):
    """Test tenant blocklist add, list, check, and remove operations."""
    test_caller = "+15554443333"

    async with get_async_session() as session:
        # 1. Add to blocklist
        entry = await add_to_blocklist(
            session=session,
            business_id=sample_business.id,
            caller_number=test_caller,
            reason="Prank caller",
            expires_in_days=7,
        )
        assert entry.identifier_value == test_caller
        assert entry.reason == "Prank caller"
        assert entry.blocked_until is not None

        # 2. Check is blocked
        blocked, reason = await is_caller_blocked(session, test_caller, sample_business.id)
        assert blocked
        assert reason == "Prank caller"

        # 3. List entries
        entries = await list_blocklist_entries(session, sample_business.id)
        assert len(entries) >= 1
        assert any(e.identifier_value == test_caller for e in entries)

        # 4. Remove from blocklist
        removed = await remove_from_blocklist(session, sample_business.id, test_caller)
        assert removed

        # 5. Check no longer blocked
        blocked_after, _ = await is_caller_blocked(session, test_caller, sample_business.id)
        assert not blocked_after


@pytest.mark.asyncio
async def test_blocklist_expired_pruned(sample_business):
    """Test that an expired blocklist entry is pruned and not enforced."""
    test_caller = "+15557778888"

    async with get_async_session() as session:
        # Add expired entry
        entry = BlocklistEntry(
            id=uuid.uuid4(),
            business_id=sample_business.id,
            identifier_type="phone",
            identifier_value=test_caller,
            reason="Old temporary block",
            created_at=datetime.now(timezone.utc) - timedelta(days=10),
            blocked_until=datetime.now(timezone.utc) - timedelta(days=1),  # expired yesterday
        )
        session.add(entry)
        await session.commit()

        # is_caller_blocked should return False and prune the record
        blocked, _ = await is_caller_blocked(session, test_caller, sample_business.id)
        assert not blocked


@pytest.mark.asyncio
async def test_caller_rate_limit(sample_business):
    """Test per-caller hourly rate limit enforcement."""
    test_caller = "+15551112222"

    async with get_async_session() as session:
        # Create 5 calls within the last hour for this caller
        now = datetime.now(timezone.utc)
        for i in range(5):
            call = Call(
                id=uuid.uuid4(),
                business_id=sample_business.id,
                caller_number=test_caller,
                started_at=now - timedelta(minutes=10 * i),
            )
            session.add(call)
        await session.commit()

        # Check rate limit
        is_limited, count, msg = await check_caller_rate_limit(
            session=session,
            caller_number=test_caller,
            business_id=sample_business.id,
        )
        assert is_limited
        assert count == 5
        assert "maximum number of calls" in msg.lower()

        # Different caller is not limited
        unlimited, count2, _ = await check_caller_rate_limit(
            session=session,
            caller_number="+15559990000",
            business_id=sample_business.id,
        )
        assert not unlimited
        assert count2 == 0


# =========================================================================
# 4. OWNER ALERT NOTIFICATIONS TESTS
# =========================================================================

@pytest.mark.asyncio
async def test_owner_alert_circuit_breaker_tripped(sample_business):
    """Test notification generation when circuit breaker trips."""
    mock_email = MagicMock()
    mock_email.send_email = AsyncMock(return_value=True)

    async with get_async_session() as session:
        await notify_circuit_breaker_tripped(
            session=session,
            business=sample_business,
            provider="groq",
            failure_count=3,
            email_provider=mock_email,
        )

        # Check notification logged in DB
        stmt = select(Notification).where(
            Notification.business_id == sample_business.id,
            Notification.type == "owner_circuit_breaker_tripped",
        )
        notif = (await session.execute(stmt)).scalar_one_or_none()
        assert notif is not None
        assert notif.recipient == sample_business.notification_email
        mock_email.send_email.assert_called_once()
        msg_arg = mock_email.send_email.call_args[0][0]
        assert "GROQ" in msg_arg.subject
        assert "Circuit Breaker Tripped" in msg_arg.subject


@pytest.mark.asyncio
async def test_owner_alert_abuse_detected(sample_business):
    """Test notification generation when caller abuse is detected."""
    mock_email = MagicMock()
    mock_email.send_email = AsyncMock(return_value=True)

    async with get_async_session() as session:
        await notify_abuse_detected(
            session=session,
            business=sample_business,
            caller_number="+15559991234",
            reason="Exceeded 5 calls per hour limit",
            email_provider=mock_email,
        )

        stmt = select(Notification).where(
            Notification.business_id == sample_business.id,
            Notification.type == "owner_abuse_detected",
        )
        notif = (await session.execute(stmt)).scalar_one_or_none()
        assert notif is not None
        assert notif.recipient == sample_business.notification_email
        mock_email.send_email.assert_called_once()
        msg_arg = mock_email.send_email.call_args[0][0]
        assert "+15559991234" in msg_arg.subject
        assert "Security Alert" in msg_arg.subject
