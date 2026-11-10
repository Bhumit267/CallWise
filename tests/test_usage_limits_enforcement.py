"""Comprehensive tests for usage tracking, cost estimation, and monthly limit enforcement."""

from datetime import datetime, timezone
import uuid
import pytest
from sqlalchemy import select

from callwise.agent.text_agent import TextAgent
from callwise.calls.usage import (
    calculate_estimated_cost,
    check_usage_limits_async,
    record_usage_record_async,
)
from callwise.db.models import Business, Call, UsageLimits, UsageRecord
from callwise.db.session import get_async_session
from callwise.notifications.service import notify_usage_limit_reached
from callwise.providers.email import ConsoleEmailProvider


def test_pricing_calculation():
    """Verify itemized cost estimation calculation matching pricing lookup table."""
    # Groq LLM: 1000 input ($0.00059) + 500 output ($0.00079 * 0.5 = $0.000395)
    # STT Deepgram: 60 sec * $0.000072 = $0.00432
    # TTS Deepgram: 1000 chars * $0.000015 = $0.015
    # Telephony: 60 sec * ($0.004 / 60) = $0.004
    cost = calculate_estimated_cost(
        duration_seconds=60,
        stt_seconds=60.0,
        tts_characters=1000,
        llm_input_tokens=1000,
        llm_output_tokens=500,
        llm_provider="groq",
        tts_provider="deepgram",
        stt_provider="deepgram",
        telephony_provider="livekit",
    )
    expected = 0.00059 + 0.000395 + 0.00432 + 0.015 + 0.004
    assert abs(cost - expected) < 1e-4
    assert cost > 0.02


@pytest.mark.asyncio
async def test_usage_limit_enforcement_and_graceful_degradation():
    """Verify limit checks trigger graceful degradation when limits are hit."""
    biz_id = uuid.uuid4()

    async with get_async_session() as session:
        biz = Business(
            id=biz_id,
            name="Apex Clinic",
            business_type="Medical",
            greeting="Hello Apex",
            hours={},
            notification_email="owner@apexclinic.com",
        )
        session.add(biz)

        # Set tight usage limits: 5 minutes of voice, 2 chat sessions
        limits = UsageLimits(
            id=uuid.uuid4(),
            business_id=biz_id,
            voice_minutes_per_month=5,
            chat_messages_per_month=2,
            max_concurrent_calls=2,
            max_call_duration_seconds=120,
            llm_tokens_per_month=2000,
            hard_limit_enforced=True,
        )
        session.add(limits)
        await session.commit()

    # 1. Under limits initially
    res_under = await check_usage_limits_async(biz_id, session_type="phone")
    assert res_under.allowed is True

    # 2. Test Single Call Duration Cap (120s limit)
    res_dur = await check_usage_limits_async(
        biz_id, session_type="phone", current_call_duration_seconds=130
    )
    assert res_dur.allowed is False
    assert res_dur.limit_type == "call_duration"
    assert "maximum permitted duration" in res_dur.graceful_message

    # 3. Exceed chat limit by seeding 3 usage records
    for _ in range(3):
        await record_usage_record_async(
            business_id=biz_id,
            session_type="widget",
            duration_seconds=30,
            llm_input_tokens=50,
            llm_output_tokens=50,
        )

    res_chat_exceeded = await check_usage_limits_async(biz_id, session_type="widget")
    assert res_chat_exceeded.allowed is False
    assert res_chat_exceeded.limit_type == "chat_messages"
    assert "Chat assistance is temporarily unavailable" in res_chat_exceeded.graceful_message


@pytest.mark.asyncio
async def test_text_agent_degradation_on_limit_hit():
    """Verify TextAgent returns graceful callback degradation rather than crashing."""
    biz_id = uuid.uuid4()

    async with get_async_session() as session:
        biz = Business(
            id=biz_id,
            name="Graceful Degradation Test Clinic",
            business_type="Healthcare",
            greeting="Welcome",
            hours={},
        )
        session.add(biz)

        # Zero chat allowance to force immediate limit breach
        limits = UsageLimits(
            id=uuid.uuid4(),
            business_id=biz_id,
            voice_minutes_per_month=100,
            chat_messages_per_month=0,
            max_concurrent_calls=5,
            max_call_duration_seconds=600,
            llm_tokens_per_month=100000,
            hard_limit_enforced=True,
        )
        session.add(limits)
        await session.commit()

    agent = TextAgent(business=biz)
    reply = await agent.ask("Can I speak to someone?", session_type="widget")

    # Agent should return a polite fallback without calling LLM
    assert "Chat assistance is temporarily unavailable" in reply


@pytest.mark.asyncio
async def test_notify_usage_limit_reached_email():
    """Verify owner receives alert email when limit is exceeded."""
    biz_id = uuid.uuid4()
    mock_email = ConsoleEmailProvider()

    async with get_async_session() as session:
        biz = Business(
            id=biz_id,
            name="Dr. Smith Practice",
            business_type="Healthcare",
            greeting="Hello",
            hours={},
            notification_email="doctor@smithpractice.com",
        )
        session.add(biz)
        await session.commit()

        await notify_usage_limit_reached(
            session=session,
            business=biz,
            limit_type="voice_minutes",
            current_value=302.5,
            limit_value=300.0,
            email_provider=mock_email,
        )

    assert len(mock_email.sent_messages) == 1
    sent = mock_email.sent_messages[0]
    assert sent.to == "doctor@smithpractice.com"
    assert "Voice Minutes Limit Reached" in sent.subject
    assert "302.5" in sent.body_text
