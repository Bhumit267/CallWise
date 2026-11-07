"""Usage cost estimation, metrics tracking, and per-tenant limit enforcement."""

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional, Tuple
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from callwise.config import settings
from callwise.db.models import Business, Call, UsageLimits, UsageRecord
from callwise.db.session import get_async_session, get_sync_session

logger = logging.getLogger(__name__)

# Standard estimate rates (USD per unit)
# Clearly documented as estimated metrics for cost-tracking
PRICING_TABLE = {
    # LLM pricing per 1,000 tokens
    "llm": {
        "groq": {"input": 0.00059, "output": 0.00079},
        "gemini": {"input": 0.00010, "output": 0.00040},
        "ollama": {"input": 0.0, "output": 0.0},
        "default": {"input": 0.00050, "output": 0.00050},
    },
    # STT per audio second ($0.0043/min -> ~$0.0000716/sec)
    "stt": {
        "deepgram": 0.000072,
        "default": 0.000072,
    },
    # TTS per character ($0.015/1,000 chars -> $0.000015/char)
    "tts": {
        "deepgram": 0.000015,
        "cartesia": 0.000038,
        "default": 0.000020,
    },
    # Telephony per minute ($0.004/min LiveKit/SIP egress estimate)
    "telephony": {
        "livekit": 0.004 / 60.0,  # per second
        "sip": 0.005 / 60.0,
        "default": 0.004 / 60.0,
    },
}


def calculate_estimated_cost(
    duration_seconds: int = 0,
    stt_seconds: float = 0.0,
    tts_characters: int = 0,
    llm_input_tokens: int = 0,
    llm_output_tokens: int = 0,
    llm_provider: Optional[str] = None,
    tts_provider: Optional[str] = None,
    stt_provider: Optional[str] = None,
    telephony_provider: Optional[str] = None,
) -> float:
    """
    Calculate estimated cost in USD based on transparent pricing lookup table.
    """
    # 1. LLM Cost
    llm_key = (llm_provider or "default").lower()
    rates = PRICING_TABLE["llm"].get(llm_key, PRICING_TABLE["llm"]["default"])
    llm_cost = (llm_input_tokens / 1000.0) * rates["input"] + (
        llm_output_tokens / 1000.0
    ) * rates["output"]

    # 2. STT Cost
    stt_key = (stt_provider or "default").lower()
    stt_rate = PRICING_TABLE["stt"].get(stt_key, PRICING_TABLE["stt"]["default"])
    stt_cost = stt_seconds * stt_rate

    # 3. TTS Cost
    tts_key = (tts_provider or "default").lower()
    tts_rate = PRICING_TABLE["tts"].get(tts_key, PRICING_TABLE["tts"]["default"])
    tts_cost = tts_characters * tts_rate

    # 4. Telephony Egress Cost
    tel_key = (telephony_provider or "default").lower()
    tel_rate = PRICING_TABLE["telephony"].get(
        tel_key, PRICING_TABLE["telephony"]["default"]
    )
    tel_cost = duration_seconds * tel_rate

    total = llm_cost + stt_cost + tts_cost + tel_cost
    return round(total, 6)


@dataclass
class LimitCheckResult:
    """Status result of evaluating tenant usage limits."""
    allowed: bool
    limit_type: Optional[str] = None  # "voice_minutes", "chat_messages", "concurrent_calls", "llm_tokens", "call_duration"
    current_value: float = 0.0
    limit_value: float = 0.0
    graceful_message: Optional[str] = None


async def get_or_create_usage_limits(
    session: AsyncSession, business_id: uuid.UUID
) -> UsageLimits:
    """Fetch existing usage limits or seed default limits for the business."""
    stmt = select(UsageLimits).where(UsageLimits.business_id == business_id)
    limits = (await session.execute(stmt)).scalar_one_or_none()
    if not limits:
        limits = UsageLimits(
            id=uuid.uuid4(),
            business_id=business_id,
            voice_minutes_per_month=300,
            chat_messages_per_month=1000,
            max_concurrent_calls=3,
            max_call_duration_seconds=600,
            llm_tokens_per_month=500000,
            hard_limit_enforced=True,
        )
        session.add(limits)
        await session.flush()
    return limits


async def check_usage_limits_async(
    business_id: uuid.UUID,
    session_type: str = "phone",  # "phone", "widget", "chat"
    current_call_duration_seconds: int = 0,
) -> LimitCheckResult:
    """
    Check if tenant has exceeded limits for the current calendar month.
    Returns LimitCheckResult. Never raises an uncaught exception; fails open if DB fails.
    """
    try:
        async with get_async_session() as session:
            limits = await get_or_create_usage_limits(session, business_id)

            if not limits.hard_limit_enforced:
                return LimitCheckResult(allowed=True)

            # Check single call duration cap
            if (
                session_type == "phone"
                and current_call_duration_seconds > limits.max_call_duration_seconds
            ):
                return LimitCheckResult(
                    allowed=False,
                    limit_type="call_duration",
                    current_value=current_call_duration_seconds,
                    limit_value=limits.max_call_duration_seconds,
                    graceful_message=(
                        "This call has reached the maximum permitted duration. "
                        "I will save our notes and end the call now. Thank you for calling!"
                    ),
                )

            # Calculate current month date window (UTC)
            now = datetime.now(timezone.utc)
            start_of_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

            # Sum month-to-date metrics
            metrics_stmt = select(
                func.coalesce(func.sum(UsageRecord.duration_seconds), 0),
                func.coalesce(func.count(UsageRecord.id), 0),
                func.coalesce(
                    func.sum(
                        UsageRecord.llm_input_tokens + UsageRecord.llm_output_tokens
                    ),
                    0,
                ),
            ).where(
                UsageRecord.business_id == business_id,
                UsageRecord.created_at >= start_of_month,
            )

            row = (await session.execute(metrics_stmt)).one()
            total_duration_secs = row[0]
            total_sessions = row[1]
            total_tokens = row[2]

            total_voice_minutes = total_duration_secs / 60.0

            # 1. Voice Minutes Limit
            if (
                session_type == "phone"
                and total_voice_minutes >= limits.voice_minutes_per_month
            ):
                logger.warning(
                    f"[Usage Limits] Tenant {business_id} exceeded voice minutes: {total_voice_minutes:.1f}/{limits.voice_minutes_per_month}"
                )
                return LimitCheckResult(
                    allowed=False,
                    limit_type="voice_minutes",
                    current_value=total_voice_minutes,
                    limit_value=limits.voice_minutes_per_month,
                    graceful_message=(
                        "We are currently experiencing high call volume and cannot accept new calls at this time. "
                        "May I take down your name and number for a callback?"
                    ),
                )

            # 2. Chat / Widget Messages Limit
            if (
                session_type in ("widget", "chat")
                and total_sessions >= limits.chat_messages_per_month
            ):
                logger.warning(
                    f"[Usage Limits] Tenant {business_id} exceeded chat sessions: {total_sessions}/{limits.chat_messages_per_month}"
                )
                return LimitCheckResult(
                    allowed=False,
                    limit_type="chat_messages",
                    current_value=total_sessions,
                    limit_value=limits.chat_messages_per_month,
                    graceful_message=(
                        "Chat assistance is temporarily unavailable right now. "
                        "Please leave your name and contact info and our staff will get back to you shortly."
                    ),
                )

            # 3. Monthly LLM Tokens Limit
            if total_tokens >= limits.llm_tokens_per_month:
                logger.warning(
                    f"[Usage Limits] Tenant {business_id} exceeded token allocation: {total_tokens}/{limits.llm_tokens_per_month}"
                )
                return LimitCheckResult(
                    allowed=False,
                    limit_type="llm_tokens",
                    current_value=total_tokens,
                    limit_value=limits.llm_tokens_per_month,
                    graceful_message=(
                        "Our assistant is currently operating at monthly capacity. "
                        "Would you like to leave a message for the team?"
                    ),
                )

            # 4. Concurrent Calls Limit
            if session_type == "phone":
                concurrent_stmt = select(func.count(Call.id)).where(
                    Call.business_id == business_id,
                    Call.ended_at.is_(None),
                )
                active_calls = (await session.execute(concurrent_stmt)).scalar() or 0
                if active_calls >= limits.max_concurrent_calls:
                    logger.warning(
                        f"[Usage Limits] Tenant {business_id} hit concurrent call cap: {active_calls}/{limits.max_concurrent_calls}"
                    )
                    return LimitCheckResult(
                        allowed=False,
                        limit_type="concurrent_calls",
                        current_value=active_calls,
                        limit_value=limits.max_concurrent_calls,
                        graceful_message=(
                            "All receptionists are currently assisting other callers. "
                            "Please leave a message with your contact number and we will return your call promptly."
                        ),
                    )

            return LimitCheckResult(allowed=True)
    except Exception as exc:
        logger.error(f"[Usage Limits] Error evaluating usage limits: {exc}", exc_info=True)
        # Never crash a call on limit check error (fail open safely)
        return LimitCheckResult(allowed=True)


async def record_usage_record_async(
    business_id: uuid.UUID,
    session_type: str = "phone",
    call_id: Optional[uuid.UUID] = None,
    duration_seconds: int = 0,
    stt_seconds: float = 0.0,
    tts_characters: int = 0,
    llm_input_tokens: int = 0,
    llm_output_tokens: int = 0,
    llm_provider: Optional[str] = None,
    llm_model: Optional[str] = None,
    tts_provider: Optional[str] = None,
    stt_provider: Optional[str] = None,
    telephony_provider: Optional[str] = None,
) -> UsageRecord:
    """
    Persist an itemized usage record with estimated cost.
    """
    estimated_cost = calculate_estimated_cost(
        duration_seconds=duration_seconds,
        stt_seconds=stt_seconds,
        tts_characters=tts_characters,
        llm_input_tokens=llm_input_tokens,
        llm_output_tokens=llm_output_tokens,
        llm_provider=llm_provider,
        tts_provider=tts_provider,
        stt_provider=stt_provider,
        telephony_provider=telephony_provider,
    )

    record = UsageRecord(
        id=uuid.uuid4(),
        business_id=business_id,
        call_id=call_id,
        session_type=session_type,
        duration_seconds=duration_seconds,
        stt_seconds=round(stt_seconds, 2),
        tts_characters=tts_characters,
        llm_input_tokens=llm_input_tokens,
        llm_output_tokens=llm_output_tokens,
        llm_provider=llm_provider,
        llm_model=llm_model,
        tts_provider=tts_provider,
        stt_provider=stt_provider,
        estimated_cost_usd=estimated_cost,
        created_at=datetime.now(timezone.utc),
    )

    async with get_async_session() as session:
        session.add(record)
        await session.commit()

    return record

