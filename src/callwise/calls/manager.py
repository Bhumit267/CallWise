"""Call lifecycle manager: turn recording, latency tracking, and LLM call summaries."""

import asyncio
from datetime import datetime, timezone
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional
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

INSIGHTS_SYSTEM_PROMPT = (
    "You are an AI call intelligence analyzer for business customer service calls.\n"
    "Analyze the call transcript and extract structured intelligence in pure JSON with this exact schema:\n"
    "{\n"
    '  "summary": "1 to 2 concise sentences summarizing the call without markdown asterisks.",\n'
    '  "intent": "appointment_request | pricing_inquiry | complaint | general_faq | cancellation | other",\n'
    '  "urgency": "high | normal",\n'
    '  "sentiment": "positive | neutral | frustrated",\n'
    '  "tags": ["short", "lowercase", "tags"],\n'
    '  "structured_notes": {\n'
    '    "key_details": "Critical requirements, symptoms, requested times, or services",\n'
    '    "action_items": "Specific follow-up required by business staff, or None"\n'
    "  }\n"
    "}\n"
    "Guidelines:\n"
    "- Urgency is 'high' if the caller expresses extreme pain, dental emergency, urgent same-day needs, billing disputes, or intense frustration. Otherwise 'normal'.\n"
    "- Sentiment is 'frustrated' if caller is annoyed, repeating themselves, demanding human/supervisor, or angry; 'positive' if caller expresses gratitude or happiness; otherwise 'neutral'.\n"
    "- Tags should include relevant labels e.g. 'urgent', 'appointment', 'pricing', 'hinglish_caller', 'callback_needed', 'complaint'.\n"
    "Output valid JSON only. Do not wrap in markdown or add conversational preamble."
)


def _heuristic_extract_insights(
    transcript: str, turns: List[CallTurn], messages: List[Message]
) -> Dict[str, Any]:
    """Heuristic fallback when LLM is unavailable or outputs non-JSON."""
    lower_text = transcript.lower()

    # Urgency check
    high_urgency_keywords = [
        "emergency", "severe pain", "hurts a lot", "bleeding", "unbearable",
        "asap", "immediately", "right now", "urgent", "unacceptable",
        "furious", "angry", "complaint", "cancel everything", "terrible service",
    ]
    is_urgent = any(kw in lower_text for kw in high_urgency_keywords)
    urgency = "high" if is_urgent else "normal"

    # Sentiment check
    frustrated_keywords = [
        "angry", "frustrated", "ridiculous", "unacceptable", "upset",
        "waste of time", "horrible", "terrible", "awful", "bad experience",
        "speak to a person", "talk to human", "manager", "supervisor",
        "bakwaas", "gussa", "pareshan",
    ]
    positive_keywords = [
        "thank you", "thanks", "great", "awesome", "perfect", "appreciate",
        "helpful", "wonderful", "shukriya", "dhanyawad",
    ]

    if any(kw in lower_text for kw in frustrated_keywords) or (is_urgent and "pain" in lower_text):
        sentiment = "frustrated"
    elif any(kw in lower_text for kw in positive_keywords):
        sentiment = "positive"
    else:
        sentiment = "neutral"

    # Intent check
    if any(kw in lower_text for kw in [
        "reschedule", "appointment", "schedule", "book", "slot", "timing",
        "visit", "consultation", "pain", "hurts", "emergency", "doctor", "bleeding"
    ]):
        intent = "appointment_request"
    elif any(kw in lower_text for kw in ["how much", "cost", "price", "pricing", "rate", "fee", "charges", "kitna"]):
        intent = "pricing_inquiry"
    elif any(kw in lower_text for kw in ["cancel", "cancellation", "drop"]):
        intent = "cancellation"
    elif any(kw in lower_text for kw in ["complaint", "unacceptable", "refund", "bad service", "poor"]):
        intent = "complaint"
    elif any(kw in lower_text for kw in ["open", "hours", "address", "location", "where", "insurance", "timing", "kahan"]):
        intent = "general_faq"
    else:
        intent = "other"

    # Tags
    tags: List[str] = []
    if urgency == "high":
        tags.append("urgent")
    if intent != "other":
        tags.append(intent)
    if any(w in lower_text for w in ["haan", "theek", "achha", "kal", "arre", "bhaiya", "shaam", "subah", "ji"]):
        tags.append("hinglish_caller")
    if messages:
        tags.append("callback_requested")

    summary = f"Call completed with {len(turns)} dialogue turn(s)."
    first_caller = next((t.text for t in turns if t.speaker == "caller"), "")
    if first_caller:
        summary = f"Caller inquiry: {first_caller[:120]}."

    key_details = [t.text[:100] for t in turns if t.speaker == "caller"][:3]
    action_items = [
        f"Callback {m.caller_name} ({m.callback_number}): {m.reason}"
        for m in messages
    ]

    return {
        "summary": summary,
        "intent": intent,
        "urgency": urgency,
        "sentiment": sentiment,
        "tags": tags,
        "structured_notes": {
            "key_details": "; ".join(key_details) if key_details else "Standard call inquiry",
            "action_items": "; ".join(action_items) if action_items else "None",
        },
    }


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


async def extract_call_insights_async(
    call_id: uuid.UUID,
    provider_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Extract structured call insights (summary, intent, urgency, sentiment, tags, structured_notes)."""
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
            return {
                "summary": "Call record not found.",
                "intent": "other",
                "urgency": "normal",
                "sentiment": "neutral",
                "tags": [],
                "structured_notes": {},
            }

        if not call_obj.turns:
            return {
                "summary": "No conversational dialogue was recorded during this call.",
                "intent": "other",
                "urgency": "normal",
                "sentiment": "neutral",
                "tags": [],
                "structured_notes": {},
            }

        # Format transcript
        lines: List[str] = []
        for t in sorted(call_obj.turns, key=lambda x: x.timestamp):
            spk = "Caller" if t.speaker == "caller" else "Receptionist"
            lines.append(f"{spk}: {t.text}")
        transcript_str = "\n".join(lines)

        messages_str = ""
        if call_obj.messages:
            msg_details = [
                f"- Name: {m.caller_name}, Phone: {m.callback_number}, Reason: {m.reason}"
                for m in call_obj.messages
            ]
            messages_str = "\n\nMessages left by caller:\n" + "\n".join(msg_details)

        biz_name = call_obj.business.name if call_obj.business else "the business"
        user_prompt = (
            f"Business: {biz_name}\n"
            f"Call Transcript:\n{transcript_str}"
            f"{messages_str}\n\n"
            "JSON Analysis:"
        )

        turns_snapshot = list(call_obj.turns)
        messages_snapshot = list(call_obj.messages)

    fallback_insights = _heuristic_extract_insights(
        transcript_str, turns_snapshot, messages_snapshot
    )

    try:
        llm = get_llm_provider(provider_name or settings.llm_provider)
        raw_response = await llm.generate_response(
            prompt=user_prompt,
            system_prompt=INSIGHTS_SYSTEM_PROMPT,
        )
        cleaned_json = raw_response.strip()
        # Strip markdown code blocks if present
        if cleaned_json.startswith("```"):
            cleaned_json = re.sub(r"^```(?:json)?\s*", "", cleaned_json, flags=re.IGNORECASE)
            cleaned_json = re.sub(r"\s*```$", "", cleaned_json)

        parsed = json.loads(cleaned_json)
        if not isinstance(parsed, dict):
            return fallback_insights

        valid_intents = {
            "appointment_request", "pricing_inquiry", "complaint",
            "general_faq", "cancellation", "other"
        }
        intent = str(parsed.get("intent", "")).lower().strip()
        if intent not in valid_intents:
            intent = fallback_insights["intent"]

        urgency = str(parsed.get("urgency", "")).lower().strip()
        if urgency not in {"high", "normal"}:
            urgency = fallback_insights["urgency"]

        sentiment = str(parsed.get("sentiment", "")).lower().strip()
        if sentiment not in {"positive", "neutral", "frustrated"}:
            sentiment = fallback_insights["sentiment"]

        summary = str(parsed.get("summary", "")).replace("*", "").replace("#", "").strip()
        if not summary:
            summary = fallback_insights["summary"]

        tags = parsed.get("tags")
        if not isinstance(tags, list):
            tags = fallback_insights["tags"]
        else:
            tags = [str(t).lower().strip() for t in tags if str(t).strip()]
            if urgency == "high" and "urgent" not in tags:
                tags.append("urgent")
            lower_trans = transcript_str.lower()
            if any(w in lower_trans for w in ["haan", "theek", "achha", "kal", "arre", "bhaiya", "shaam", "subah", "ji", "namaste"]):
                if "hinglish_caller" not in tags:
                    tags.append("hinglish_caller")

        structured_notes = parsed.get("structured_notes")
        if not isinstance(structured_notes, dict):
            structured_notes = fallback_insights["structured_notes"]

        return {
            "summary": summary,
            "intent": intent,
            "urgency": urgency,
            "sentiment": sentiment,
            "tags": tags,
            "structured_notes": structured_notes,
        }
    except Exception as exc:
        logger.warning(f"Failed to generate LLM call insights, using heuristic fallback: {exc}")
        return fallback_insights


def extract_call_insights(
    call_id: uuid.UUID,
    provider_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Synchronous wrapper for extracting call insights."""
    return asyncio.run(extract_call_insights_async(call_id, provider_name))


async def generate_call_summary_async(
    call_id: uuid.UUID,
    provider_name: Optional[str] = None,
) -> str:
    """Generate a concise executive summary for a completed call."""
    insights = await extract_call_insights_async(call_id, provider_name=provider_name)
    return insights.get("summary", "Call completed.")


def generate_call_summary(call_id: uuid.UUID, provider_name: Optional[str] = None) -> str:
    """Synchronous wrapper for generating a call summary."""
    return asyncio.run(generate_call_summary_async(call_id, provider_name))


async def end_call_async(
    call_id: uuid.UUID,
    generate_summary: bool = True,
    provider_name: Optional[str] = None,
) -> Optional[Call]:
    """End a call session, calculate duration, and generate LLM summary and structured intelligence."""
    now_utc = datetime.now(timezone.utc)
    insights: Optional[Dict[str, Any]] = None

    if generate_summary:
        insights = await extract_call_insights_async(call_id, provider_name=provider_name)

    async with get_async_session() as session:
        call_obj = await session.scalar(
            select(Call)
            .where(Call.id == call_id)
            .options(selectinload(Call.turns), selectinload(Call.messages))
        )
        if not call_obj:
            return None

        call_obj.ended_at = now_utc
        if call_obj.started_at:
            call_obj.duration_seconds = max(0.0, (now_utc - call_obj.started_at).total_seconds())

        if insights:
            call_obj.summary = insights.get("summary")
            call_obj.intent = insights.get("intent")
            call_obj.urgency = insights.get("urgency", "normal")
            call_obj.sentiment = insights.get("sentiment", "neutral")
            call_obj.tags = insights.get("tags", [])
            call_obj.structured_notes = insights.get("structured_notes", {})

        await session.commit()
        return call_obj


def end_call(
    call_id: uuid.UUID,
    generate_summary: bool = True,
    provider_name: Optional[str] = None,
) -> Optional[Call]:
    """Synchronous wrapper for ending a call using sync database session."""
    now_utc = datetime.now(timezone.utc)
    insights: Optional[Dict[str, Any]] = None

    if generate_summary:
        insights = extract_call_insights(call_id, provider_name=provider_name)

    with get_sync_session() as session:
        call_obj = session.scalar(
            select(Call)
            .where(Call.id == call_id)
            .options(selectinload(Call.turns), selectinload(Call.messages))
        )
        if not call_obj:
            return None

        call_obj.ended_at = now_utc
        if call_obj.started_at:
            call_obj.duration_seconds = max(0.0, (now_utc - call_obj.started_at).total_seconds())

        if insights:
            call_obj.summary = insights.get("summary")
            call_obj.intent = insights.get("intent")
            call_obj.urgency = insights.get("urgency", "normal")
            call_obj.sentiment = insights.get("sentiment", "neutral")
            call_obj.tags = insights.get("tags", [])
            call_obj.structured_notes = insights.get("structured_notes", {})

        session.commit()
        return call_obj
