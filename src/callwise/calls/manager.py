"""Call lifecycle manager: turn recording, latency tracking, and LLM call summaries."""

import asyncio
from datetime import datetime, timezone
import logging
import time
from typing import List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from callwise.config import settings
from callwise.db.models import Business, Call, CallTurn, Message
from callwise.db.session import get_async_session, get_sync_session
from callwise.providers.llm import get_llm_provider

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM_PROMPT = (
    "You are an executive assistant summarizing phone call logs for business management. "
    "Write a concise, professional 1 to 2 sentence summary of the call. "
    "Include the caller's main intent or question, the information provided, "
    "and any callback message or action item left. "
    "Do NOT include markdown asterisks, bullet points, or conversational filler like 'In this call'."
)


async def record_call_turn_async(
    call_id: uuid.UUID,
    business_id: uuid.UUID,
    speaker: str,
    text: str,
    latency_ms: Optional[float] = None,
) -> CallTurn:
    """Record an individual conversation turn asynchronously."""
    cleaned_text = text.strip()
    turn = CallTurn(
        id=uuid.uuid4(),
        call_id=call_id,
        business_id=business_id,
        speaker=speaker.lower().strip(),
        text=cleaned_text,
        latency_ms=round(latency_ms, 2) if latency_ms is not None else None,
        timestamp=datetime.now(timezone.utc),
    )

    async with get_async_session() as session:
        # Verify Call row exists to satisfy foreign key
        call_obj = await session.get(Call, call_id)
        if not call_obj:
            call_obj = Call(
                id=call_id,
                business_id=business_id,
                caller_number="console",
                llm_provider=settings.llm_provider,
                llm_model=settings.groq_model,
            )
            session.add(call_obj)
            await session.flush()

        session.add(turn)
        await session.commit()

    return turn


def record_call_turn(
    call_id: uuid.UUID,
    business_id: uuid.UUID,
    speaker: str,
    text: str,
    latency_ms: Optional[float] = None,
) -> CallTurn:
    """Synchronous recording of a conversation turn using sync database session."""
    cleaned_text = text.strip()
    turn = CallTurn(
        id=uuid.uuid4(),
        call_id=call_id,
        business_id=business_id,
        speaker=speaker.lower().strip(),
        text=cleaned_text,
        latency_ms=round(latency_ms, 2) if latency_ms is not None else None,
        timestamp=datetime.now(timezone.utc),
    )

    with get_sync_session() as session:
        call_obj = session.get(Call, call_id)
        if not call_obj:
            call_obj = Call(
                id=call_id,
                business_id=business_id,
                caller_number="console",
                llm_provider=settings.llm_provider,
                llm_model=settings.groq_model,
            )
            session.add(call_obj)
            session.flush()

        session.add(turn)
        session.commit()

    return turn


async def generate_call_summary_async(
    call_id: uuid.UUID,
    provider_name: Optional[str] = None,
) -> str:
    """Generate a concise executive summary for a completed call using the configured LLM."""
    async with get_async_session() as session:
        call_obj = await session.scalar(
            select(Call)
            .where(Call.id == call_id)
            .options(
                selectinload(Call.turns),
                selectinload(Call.messages),
                selectinload(Call.business),
            )
        )
        if not call_obj:
            return "Call record not found."

        if not call_obj.turns:
            return "No conversational dialogue was recorded during this call."

        # Format transcript
        lines: List[str] = []
        for t in sorted(call_obj.turns, key=lambda x: x.timestamp):
            spk = "Caller" if t.speaker == "caller" else "Receptionist"
            lines.append(f"{spk}: {t.text}")
        transcript_str = "\n".join(lines)

        # Append messages info if any
        messages_str = ""
        if call_obj.messages:
            msg_details = [
                f"- Name: {m.caller_name}, Phone: {m.callback_number}, Reason: {m.reason}"
                for m in call_obj.messages
            ]
            messages_str = f"\n\nMessages left by caller:\n" + "\n".join(msg_details)

        biz_name = call_obj.business.name if call_obj.business else "the business"
        user_prompt = (
            f"Business: {biz_name}\n"
            f"Call Transcript:\n{transcript_str}"
            f"{messages_str}\n\n"
            "Summary:"
        )

    try:
        llm = get_llm_provider(provider_name or settings.llm_provider)
        raw_summary = await llm.generate_response(
            prompt=user_prompt,
            system_prompt=SUMMARY_SYSTEM_PROMPT,
        )
        # Strip any accidental markdown formatting
        summary = raw_summary.replace("*", "").replace("#", "").strip()
        if not summary:
            summary = "Call completed with no specific action items."
        return summary
    except Exception as exc:
        logger.warning(f"Failed to generate LLM call summary: {exc}")
        return f"Call completed with {len(call_obj.turns)} dialogue turn(s)."


def generate_call_summary(call_id: uuid.UUID, provider_name: Optional[str] = None) -> str:
    """Synchronous wrapper for generating a call summary."""
    return asyncio.run(generate_call_summary_async(call_id, provider_name))


async def end_call_async(
    call_id: uuid.UUID,
    generate_summary: bool = True,
    provider_name: Optional[str] = None,
) -> Optional[Call]:
    """End a call session, calculate duration, and generate LLM summary."""
    now_utc = datetime.now(timezone.utc)
    summary_text = None

    if generate_summary:
        summary_text = await generate_call_summary_async(call_id, provider_name=provider_name)

    async with get_async_session() as session:
        call_obj = await session.get(Call, call_id)
        if not call_obj:
            return None

        call_obj.ended_at = now_utc
        if call_obj.started_at:
            call_obj.duration_seconds = max(0.0, (now_utc - call_obj.started_at).total_seconds())

        if summary_text:
            call_obj.summary = summary_text

        await session.commit()
        await session.refresh(call_obj)
        return call_obj


def end_call(
    call_id: uuid.UUID,
    generate_summary: bool = True,
    provider_name: Optional[str] = None,
) -> Optional[Call]:
    """Synchronous wrapper for ending a call using sync database session."""
    now_utc = datetime.now(timezone.utc)
    summary_text = None

    if generate_summary:
        summary_text = generate_call_summary(call_id, provider_name=provider_name)

    with get_sync_session() as session:
        call_obj = session.get(Call, call_id)
        if not call_obj:
            return None

        call_obj.ended_at = now_utc
        if call_obj.started_at:
            call_obj.duration_seconds = max(0.0, (now_utc - call_obj.started_at).total_seconds())

        if summary_text:
            call_obj.summary = summary_text

        session.commit()
        session.refresh(call_obj)
        return call_obj
