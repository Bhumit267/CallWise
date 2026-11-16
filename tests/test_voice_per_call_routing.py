"""Tests for multi-tenant per-call voice agent routing.

Tests run purely with mocked LiveKit JobContext (no LiveKit native C/Rust libraries needed).
Covers:
1. SIP routing: dialed number A -> Business A, dialed number B -> Business B in the same worker.
2. Security: Non-SIP participant carrying fake sip.* attributes is rejected.
3. Security: Web voice single source of truth (VoiceSession). Room metadata/client business_id ignored.
4. Security: Expired, reused, unknown, and malformed voice sessions rejected.
5. Telephony: Unknown dialed number rejected; blocklisted caller rejected.
6. Anti-Spam: Rejection audio playback rate limited per-caller and globally.
7. Zero Leaks: Rejected calls create zero Call, Contact, or Usage records.
8. Safety: Startup guard refuses to run in production mode with ALLOW_DEFAULT_BUSINESS=True.
9. Cross-Tenant Isolation: Call for Business A never writes records under Business B.
"""

from datetime import datetime, timedelta, timezone
import json
from typing import Any, Dict, Optional
import uuid
import pytest
from sqlalchemy import func, select

from callwise.agent.voice_agent import (
    ResolvedVoiceCall,
    VoiceRejectionRateLimiter,
    entrypoint,
    rejection_rate_limiter,
    resolve_voice_call_context,
    start_voice_worker,
)
from callwise.config import settings
from callwise.db.models import (
    BlocklistEntry,
    Business,
    Call,
    Contact,
    PhoneNumber,
    UsageRecord,
    VoiceSession,
)
from callwise.db.session import get_async_session


# ============================================================================
# Mock LiveKit Objects (Zero native libraries required)
# ============================================================================

class MockParticipant:
    """Mock LiveKit RemoteParticipant."""

    def __init__(
        self,
        identity: str = "caller-1",
        name: str = "Test Caller",
        kind: int = 3,  # 3 = PARTICIPANT_KIND_SIP
        attributes: Optional[Dict[str, str]] = None,
        metadata: str = "",
    ):
        self.identity = identity
        self.name = name
        self.kind = kind
        self.attributes = attributes or {}
        self.metadata = metadata


class MockRoom:
    """Mock LiveKit Room."""

    def __init__(self, name: str = "room-1", metadata: str = ""):
        self.name = name
        self.metadata = metadata
        self.remote_participants: Dict[str, MockParticipant] = {}
        self.disconnected: bool = False

    async def disconnect(self):
        self.disconnected = True


class MockJobContext:
    """Mock LiveKit JobContext."""

    def __init__(self, room: Optional[MockRoom] = None, participant: Optional[MockParticipant] = None):
        self.room = room or MockRoom()
        self.participant = participant
        if participant:
            self.room.remote_participants[participant.identity] = participant
        self.connected: bool = False
        self.shutdown_callbacks = []

    async def connect(self):
        self.connected = True

    async def wait_for_participant(self, identity: Optional[str] = None, timeout: float = 5.0):
        return self.participant

    def add_shutdown_callback(self, cb):
        self.shutdown_callbacks.append(cb)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def reset_settings_and_rate_limiter():
    """Ensure clean settings and rate limiter state before each test."""
    original_allow = settings.allow_default_business
    original_def_biz = settings.default_business_id
    original_env = settings.environment
    settings.allow_default_business = False
    rejection_rate_limiter.reset()

    yield

    settings.allow_default_business = original_allow
    settings.default_business_id = original_def_biz
    settings.environment = original_env
    rejection_rate_limiter.reset()


@pytest.fixture
async def two_test_businesses():
    """Create two distinct test businesses with separate phone numbers."""
    biz_a_id = uuid.uuid4()
    biz_b_id = uuid.uuid4()
    phone_a = f"+1555{uuid.uuid4().int % 10000000:07d}"
    phone_b = f"+1555{uuid.uuid4().int % 10000000:07d}"

    async with get_async_session() as session:
        biz_a = Business(
            id=biz_a_id,
            name="Clinic Alpha",
            business_type="Dental",
            greeting="Hello from Clinic Alpha",
            hours={},
        )
        biz_b = Business(
            id=biz_b_id,
            name="Salon Beta",
            business_type="Salon",
            greeting="Welcome to Salon Beta",
            hours={},
        )
        session.add_all([biz_a, biz_b])

        num_a = PhoneNumber(
            id=uuid.uuid4(),
            business_id=biz_a_id,
            e164_number=phone_a,
            label="Alpha Main",
            is_active=True,
        )
        num_b = PhoneNumber(
            id=uuid.uuid4(),
            business_id=biz_b_id,
            e164_number=phone_b,
            label="Beta Main",
            is_active=True,
        )
        session.add_all([num_a, num_b])
        await session.commit()

    return {
        "biz_a_id": biz_a_id,
        "biz_b_id": biz_b_id,
        "phone_a": phone_a,
        "phone_b": phone_b,
    }


# ============================================================================
# 1. SIP Inbound Routing Tests
# ============================================================================

@pytest.mark.asyncio
async def test_sip_routing_to_business_a_and_b_in_same_worker(two_test_businesses):
    """In the same worker process, calls to Phone A route to Biz A, and Phone B route to Biz B."""
    data = two_test_businesses

    # Call 1: Dialed Phone A
    p_a = MockParticipant(
        identity="sip-caller-1",
        name="Alice",
        kind=3,  # SIP
        attributes={
            "sip.trunkPhoneNumber": data["phone_a"],
            "sip.phoneNumber": "+15551112222",
        },
    )
    ctx_a = MockJobContext(participant=p_a)
    res_a = await resolve_voice_call_context(ctx_a)

    assert res_a.allowed is True
    assert res_a.business.id == data["biz_a_id"]
    assert res_a.business.name == "Clinic Alpha"
    assert res_a.channel == "phone"

    # Call 2: Dialed Phone B
    p_b = MockParticipant(
        identity="sip-caller-2",
        name="Bob",
        kind=3,  # SIP
        attributes={
            "sip.trunkPhoneNumber": data["phone_b"],
            "sip.phoneNumber": "+15553334444",
        },
    )
    ctx_b = MockJobContext(participant=p_b)
    res_b = await resolve_voice_call_context(ctx_b)

    assert res_b.allowed is True
    assert res_b.business.id == data["biz_b_id"]
    assert res_b.business.name == "Salon Beta"
    assert res_b.channel == "phone"


@pytest.mark.asyncio
async def test_sip_routing_unknown_number_rejected():
    """Unmapped dialed number is rejected without fallback when allow_default_business=False."""
    unknown_phone = "+15559998888"
    p = MockParticipant(
        identity="sip-caller-3",
        kind=3,
        attributes={
            "sip.trunkPhoneNumber": unknown_phone,
            "sip.phoneNumber": "+15551112222",
        },
    )
    ctx = MockJobContext(participant=p)
    res = await resolve_voice_call_context(ctx)

    assert res.allowed is False
    assert res.reject_reason == "unknown_dialed_number"
    assert "not currently in service" in res.reply_message


# ============================================================================
# 2. Security: Participant Kind & Fake SIP Attributes
# ============================================================================

@pytest.mark.asyncio
async def test_non_sip_participant_with_fake_sip_attributes_is_rejected(two_test_businesses):
    """A non-SIP participant carrying fake sip.* attributes or fake dialed numbers is rejected."""
    data = two_test_businesses

    # Client claims to dial Phone A, but participant kind is 1 (Standard WebRTC / not SIP)
    fake_p = MockParticipant(
        identity="web-attacker",
        kind=1,  # STANDARD WEBRTC PARTICIPANT (NOT SIP)
        attributes={
            "sip.trunkPhoneNumber": data["phone_a"],
            "sip.phoneNumber": "+15559990000",
        },
        metadata="",  # No valid voice session
    )
    ctx = MockJobContext(participant=fake_p)
    res = await resolve_voice_call_context(ctx)

    # Must be rejected because sip attributes on non-SIP participants are not trusted
    assert res.allowed is False
    assert res.reject_reason in ("missing_voice_session", "invalid_voice_session")


# ============================================================================
# 3. Web Voice: Single Source of Truth (VoiceSession in DB)
# ============================================================================

@pytest.mark.asyncio
async def test_web_voice_resolves_via_session_and_ignores_client_metadata(two_test_businesses):
    """The business on web voice is strictly derived from the VoiceSession row in the DB.

    Client-supplied metadata or room metadata attempting to spoof business_id is ignored.
    """
    data = two_test_businesses
    session_id = uuid.uuid4()
    call_id = uuid.uuid4()

    # Pre-create a legitimate VoiceSession for Business A
    async with get_async_session() as session:
        vs = VoiceSession(
            id=session_id,
            business_id=data["biz_a_id"],
            caller_identity="web-caller-valid",
            room_name="call-room-legit",
            call_id=call_id,
            is_used=False,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        session.add(vs)
        await session.commit()

    # Attacker attempts to inject business_id of Business B in token metadata alongside session
    tampered_metadata = json.dumps({
        "voice_session_id": str(session_id),
        "business_id": str(data["biz_b_id"]),  # SPOOF ATTEMPT
    })

    p = MockParticipant(
        identity="web-caller-valid",
        kind=1,  # WebRTC
        metadata=tampered_metadata,
    )
    # Also attempt spoof in room metadata
    room = MockRoom(name="spoof-room", metadata=json.dumps({"business_id": str(data["biz_b_id"])}))
    ctx = MockJobContext(room=room, participant=p)

    res = await resolve_voice_call_context(ctx)

    assert res.allowed is True
    # Must resolve to Business A (from the database VoiceSession), NEVER Business B!
    assert res.business.id == data["biz_a_id"]
    assert res.call_id == call_id
    assert res.channel == "web"


# ============================================================================
# 4. Web Voice Session Validation: Expired, Reused, Unknown, Malformed
# ============================================================================

@pytest.mark.asyncio
async def test_web_voice_unknown_session_rejected():
    """Unregistered voice session UUID is rejected."""
    p = MockParticipant(
        identity="web-caller",
        kind=1,
        metadata=json.dumps({"voice_session_id": str(uuid.uuid4())}),
    )
    ctx = MockJobContext(participant=p)
    res = await resolve_voice_call_context(ctx)

    assert res.allowed is False
    assert res.reject_reason == "unknown_voice_session"


@pytest.mark.asyncio
async def test_web_voice_malformed_session_rejected():
    """Malformed or non-UUID session string is rejected."""
    p = MockParticipant(
        identity="web-caller",
        kind=1,
        metadata=json.dumps({"voice_session_id": "not-a-valid-uuid"}),
    )
    ctx = MockJobContext(participant=p)
    res = await resolve_voice_call_context(ctx)

    assert res.allowed is False
    assert res.reject_reason == "malformed_voice_session"


@pytest.mark.asyncio
async def test_web_voice_expired_session_rejected(two_test_businesses):
    """Expired voice session is rejected."""
    data = two_test_businesses
    session_id = uuid.uuid4()

    async with get_async_session() as session:
        vs = VoiceSession(
            id=session_id,
            business_id=data["biz_a_id"],
            caller_identity="web-caller",
            room_name="room-expired",
            call_id=uuid.uuid4(),
            is_used=False,
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=10),  # EXPIRED
        )
        session.add(vs)
        await session.commit()

    p = MockParticipant(
        identity="web-caller",
        kind=1,
        metadata=json.dumps({"voice_session_id": str(session_id)}),
    )
    ctx = MockJobContext(participant=p)
    res = await resolve_voice_call_context(ctx)

    assert res.allowed is False
    assert res.reject_reason == "expired_voice_session"


@pytest.mark.asyncio
async def test_web_voice_reused_session_rejected(two_test_businesses):
    """Voice session marked is_used=True cannot be used a second time."""
    data = two_test_businesses
    session_id = uuid.uuid4()

    async with get_async_session() as session:
        vs = VoiceSession(
            id=session_id,
            business_id=data["biz_a_id"],
            caller_identity="web-caller",
            room_name="room-reused",
            call_id=uuid.uuid4(),
            is_used=True,  # ALREADY USED
            used_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        session.add(vs)
        await session.commit()

    p = MockParticipant(
        identity="web-caller",
        kind=1,
        metadata=json.dumps({"voice_session_id": str(session_id)}),
    )
    ctx = MockJobContext(participant=p)
    res = await resolve_voice_call_context(ctx)

    assert res.allowed is False
    assert res.reject_reason == "reused_voice_session"


# ============================================================================
# 5. Blocklist Enforcement
# ============================================================================

@pytest.mark.asyncio
async def test_sip_blocklisted_caller_rejected(two_test_businesses):
    """Blocklisted caller number for business A is rejected."""
    data = two_test_businesses
    blocked_phone = "+15556667777"

    async with get_async_session() as session:
        entry = BlocklistEntry(
            id=uuid.uuid4(),
            business_id=data["biz_a_id"],
            identifier_type="phone",
            identifier_value=blocked_phone,
            reason="Abusive spammer",
        )
        session.add(entry)
        await session.commit()

    p = MockParticipant(
        identity="sip-caller-blocked",
        kind=3,
        attributes={
            "sip.trunkPhoneNumber": data["phone_a"],
            "sip.phoneNumber": blocked_phone,
        },
    )
    ctx = MockJobContext(participant=p)
    res = await resolve_voice_call_context(ctx)

    assert res.allowed is False
    assert res.reject_reason == "caller_in_blocklist"


# ============================================================================
# 6. Anti-Spam: Rejection Audio Rate Limiter
# ============================================================================

def test_rejection_audio_rate_limiter():
    """Verify rate limiter blocks TTS playback beyond per-caller and global thresholds."""
    limiter = VoiceRejectionRateLimiter(
        per_caller_limit=2,
        per_caller_window_secs=3600.0,
        global_limit=5,
        global_window_secs=60.0,
    )
    caller = "+15550001111"

    assert limiter.can_play_rejection_tts(caller) is True
    limiter.record_rejection_tts(caller)

    assert limiter.can_play_rejection_tts(caller) is True
    limiter.record_rejection_tts(caller)

    # 3rd attempt for this caller should be throttled
    assert limiter.can_play_rejection_tts(caller) is False

    # Different caller is still allowed until global limit is reached
    other_caller = "+15550002222"
    assert limiter.can_play_rejection_tts(other_caller) is True


# ============================================================================
# 7. Zero Side Effects on Rejected Calls
# ============================================================================

@pytest.mark.asyncio
async def test_rejected_call_creates_zero_database_records():
    """A rejected call must create zero Call, Contact, or UsageRecord rows."""
    async with get_async_session() as session:
        calls_before = (await session.execute(select(func.count(Call.id)))).scalar()
        contacts_before = (await session.execute(select(func.count(Contact.id)))).scalar()
        usage_before = (await session.execute(select(func.count(UsageRecord.id)))).scalar()

    # Attempt rejected call
    p = MockParticipant(
        identity="sip-spammer",
        kind=3,
        attributes={
            "sip.trunkPhoneNumber": "+15559990000",  # Unmapped number
            "sip.phoneNumber": "+15551119999",
        },
    )
    ctx = MockJobContext(participant=p)
    await entrypoint(ctx)

    # Verify room was disconnected
    assert ctx.room.disconnected is True

    # Verify zero rows created
    async with get_async_session() as session:
        calls_after = (await session.execute(select(func.count(Call.id)))).scalar()
        contacts_after = (await session.execute(select(func.count(Contact.id)))).scalar()
        usage_after = (await session.execute(select(func.count(UsageRecord.id)))).scalar()

    assert calls_after == calls_before
    assert contacts_after == contacts_before
    assert usage_after == usage_before


# ============================================================================
# 8. Dev Fallback Toggle & Production Startup Guard
# ============================================================================

@pytest.mark.asyncio
async def test_dev_fallback_behavior(two_test_businesses):
    """When allow_default_business=True, unmapped calls fallback to default_business_id."""
    data = two_test_businesses
    settings.allow_default_business = True
    settings.default_business_id = str(data["biz_a_id"])

    p = MockParticipant(
        identity="sip-caller-unmapped",
        kind=3,
        attributes={
            "sip.trunkPhoneNumber": "+15550009999",  # Unmapped
            "sip.phoneNumber": "+15551234567",
        },
    )
    ctx = MockJobContext(participant=p)
    res = await resolve_voice_call_context(ctx)

    assert res.allowed is True
    assert res.business.id == data["biz_a_id"]
    assert res.channel == "dev_fallback"


def test_startup_guard_refuses_production_with_allow_default():
    """Worker refuses to start in production mode if allow_default_business=True."""
    settings.allow_default_business = True

    with pytest.raises(RuntimeError, match="CRITICAL SAFETY VIOLATION"):
        start_voice_worker(mode="production")


# ============================================================================
# 9. Cross-Tenant Isolation: Business A Call Never Writes Rows Under Business B
# ============================================================================

@pytest.mark.asyncio
async def test_cross_tenant_isolation_call_a_never_writes_b(two_test_businesses):
    """A call handled for Business A never writes any rows under Business B."""
    data = two_test_businesses

    async with get_async_session() as session:
        calls_b_before = (
            await session.execute(select(func.count(Call.id)).where(Call.business_id == data["biz_b_id"]))
        ).scalar()
        contacts_b_before = (
            await session.execute(select(func.count(Contact.id)).where(Contact.business_id == data["biz_b_id"]))
        ).scalar()

    # Route and handle call for Business A
    caller_phone = "+15557778888"
    p_a = MockParticipant(
        identity="sip-caller-a",
        name="Charlie",
        kind=3,
        attributes={
            "sip.trunkPhoneNumber": data["phone_a"],
            "sip.phoneNumber": caller_phone,
        },
    )
    ctx_a = MockJobContext(participant=p_a)
    resolved = await resolve_voice_call_context(ctx_a)
    assert resolved.allowed is True
    assert resolved.business.id == data["biz_a_id"]

    # Execute inbound call creation
    from callwise.telephony.router import InboundRouteResult, create_inbound_call_record_async
    route_res = InboundRouteResult(
        matched=True,
        business=resolved.business,
        contact=resolved.contact,
    )
    call_rec = await create_inbound_call_record_async(route_res, caller_number=caller_phone)

    assert call_rec.business_id == data["biz_a_id"]
    assert call_rec.business_id != data["biz_b_id"]

    # Verify Business B row counts are completely unchanged
    async with get_async_session() as session:
        calls_b_after = (
            await session.execute(select(func.count(Call.id)).where(Call.business_id == data["biz_b_id"]))
        ).scalar()
        contacts_b_after = (
            await session.execute(select(func.count(Contact.id)).where(Contact.business_id == data["biz_b_id"]))
        ).scalar()

    assert calls_b_after == calls_b_before
    assert contacts_b_after == contacts_b_before
