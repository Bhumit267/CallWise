"""Tests for transfer timeout, fallback message taking, silence handling, and max call duration."""

import asyncio
from datetime import datetime
import uuid
import pytest

from callwise.agent.text_agent import TextAgent
from callwise.booking.transfer import execute_transfer
from callwise.db.models import Business, Call, UsageLimits
from callwise.db.session import get_async_session
from callwise.providers.telephony import TelephonyProvider, TransferResult


class SlowTelephonyProvider(TelephonyProvider):
    """Simulates a SIP trunk transfer that hangs or takes too long to answer."""

    async def is_available(self, target_number: str) -> bool:
        return True

    async def transfer_call(
        self, call_id: uuid.UUID, target_number: str, reason: str
    ) -> TransferResult:
        # Sleep for longer than the transfer timeout
        await asyncio.sleep(20.0)
        return TransferResult(
            success=True,
            status="completed",
            message="Transfer finished late",
            target_phone=target_number,
        )


@pytest.mark.asyncio
async def test_transfer_timeout_triggers_fallback():
    """Verify that a slow or hanging SIP transfer times out and falls back to a polite apology."""
    biz_id = uuid.uuid4()

    async with get_async_session() as session:
        biz = Business(
            id=biz_id,
            name="Always Open Emergency Clinic",
            business_type="Healthcare",
            greeting="Hello",
            hours={
                "monday": {"open": "00:00", "close": "23:59", "closed": False},
                "tuesday": {"open": "00:00", "close": "23:59", "closed": False},
                "wednesday": {"open": "00:00", "close": "23:59", "closed": False},
                "thursday": {"open": "00:00", "close": "23:59", "closed": False},
                "friday": {"open": "00:00", "close": "23:59", "closed": False},
                "saturday": {"open": "00:00", "close": "23:59", "closed": False},
                "sunday": {"open": "00:00", "close": "23:59", "closed": False},
            },
            transfer_number="+15559998888",
        )
        session.add(biz)
        await session.commit()

        slow_p = SlowTelephonyProvider()
        result = await execute_transfer(
            session=session,
            business_id=biz_id,
            reason="Patient needs doctor",
            telephony_provider=slow_p,
        )

        assert result.success is False
        assert result.status == "failed"
        assert "unable to take your call" in result.message
        assert "leave a message" in result.message


@pytest.mark.asyncio
async def test_agent_silence_handling_two_strikes():
    """Verify agent prompts once on silence, then offers polite closure on second silence."""
    biz_id = uuid.uuid4()

    async with get_async_session() as session:
        biz = Business(
            id=biz_id,
            name="Silence Test Salon",
            business_type="Salon",
            greeting="Welcome to the salon",
            hours={},
        )
        session.add(biz)
        await session.commit()

    agent = TextAgent(business=biz)

    # First silence
    reply1 = await agent.ask("   ")
    assert "Are you still there?" in reply1
    assert agent.is_call_active is True

    # Second consecutive silence
    reply2 = await agent.ask("[silence]")
    assert "I haven't heard anything from you" in reply2
    assert "Goodbye" in reply2
    assert agent.is_call_active is False

    # Subsequent interaction on dead call
    reply3 = await agent.ask("Hello?")
    assert "This call has ended" in reply3


@pytest.mark.asyncio
async def test_agent_call_duration_cap():
    """Verify call terminates gracefully when max duration setting is exceeded."""
    biz_id = uuid.uuid4()

    async with get_async_session() as session:
        biz = Business(
            id=biz_id,
            name="Capped Call Practice",
            business_type="Consulting",
            greeting="Hello",
            hours={},
        )
        session.add(biz)

        limits = UsageLimits(
            id=uuid.uuid4(),
            business_id=biz_id,
            max_call_duration_seconds=300,  # 5 minutes
            hard_limit_enforced=True,
        )
        session.add(limits)
        await session.commit()

    agent = TextAgent(business=biz)
    # Caller speaks at 350 seconds (exceeding 300s limit)
    reply = await agent.ask(
        "I have one more question",
        session_type="phone",
        call_duration_seconds=350,
    )

    assert "reached the maximum permitted duration" in reply
    assert agent.is_call_active is False
