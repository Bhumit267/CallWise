"""Unit and integration tests for Task 2: Agent Conversational Intelligence & Real-World Resilience."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid
import pytest
import pytest_asyncio
from sqlalchemy import select

from callwise.agent.prompt import build_system_prompt
from callwise.agent.voice_agent import (
    build_turn_handling_options,
    create_voice_agent,
)
from callwise.calls.manager import (
    _heuristic_extract_insights,
    end_call_async,
    extract_call_insights_async,
    record_call_turn_async,
)
from callwise.db.models import Business, Call, CallTurn, Message
from callwise.db.session import async_engine, get_async_session, get_sync_session


@pytest_asyncio.fixture(autouse=True)
async def cleanup_db_pool():
    """Ensure async engine pool is disposed within the running event loop."""
    yield
    await async_engine.dispose()


@pytest.fixture
def test_business_and_call():
    """Create a persistent Business and Call record for conversational tests."""
    biz_id = uuid.uuid4()
    c_id = uuid.uuid4()
    with get_sync_session() as session:
        biz = Business(
            id=biz_id,
            name="Apex Family Dental Care",
            business_type="dental clinic",
            timezone="Asia/Kolkata",
            tone="warm, polite, and reassuring",
            greeting="Namaste, thank you for calling Apex Dental.",
            hours={},
        )
        session.add(biz)
        call_obj = Call(
            id=c_id,
            business_id=biz_id,
            caller_number="+919876543210",
            llm_provider="groq",
            llm_model="openai/gpt-oss-20b",
        )
        session.add(call_obj)
        session.flush()

    return {"business_id": biz_id, "call_id": c_id}


# ============================================================================
# 1. Prompt Tests: Frustration De-escalation & Hinglish / Indian Nuances
# ============================================================================

def test_prompt_includes_frustration_and_emotion_deescalation():
    """Verify system prompt contains Section 5 emotion de-escalation rules."""
    biz = Business(
        id=uuid.uuid4(),
        name="Apex Family Dental",
        business_type="dental clinic",
        timezone="America/New_York",
        tone="warm, reassuring",
        hours={},
    )
    prompt = build_system_prompt(biz)
    assert "Caller Frustration & Emotion De-escalation Protocol" in prompt
    assert "De-escalation Directives" in prompt
    assert "frustration" in prompt.lower()


def test_prompt_includes_hinglish_and_indian_nuances():
    """Verify system prompt contains Section 6 Indian conversational nuances."""
    biz = Business(
        id=uuid.uuid4(),
        name="Apex Family Dental",
        business_type="dental clinic",
        timezone="Asia/Kolkata",
        tone="polite, friendly",
        hours={},
    )
    prompt = build_system_prompt(biz)
    assert "Indian & Hinglish Conversational Nuances" in prompt
    assert "Haan ji" in prompt
    assert "Arre" in prompt
    assert "kal subah" in prompt or "kal shaam" in prompt
    assert "10-digit Indian mobile number" in prompt


# ============================================================================
# 2. Barge-in & Dynamic Endpointing Configuration Tests
# ============================================================================

def test_turn_handling_barge_in_and_endpointing_options():
    """Verify TurnHandlingOptions enables low-latency VAD interruption and dynamic endpointing."""
    turn_options = build_turn_handling_options()
    assert turn_options is not None

    turn_det = turn_options.get("turn_detection") if isinstance(turn_options, dict) else getattr(turn_options, "turn_detection", None)
    assert turn_det == "vad"

    # Interruption resilience configuration
    interruption = turn_options.get("interruption") if isinstance(turn_options, dict) else getattr(turn_options, "interruption", None)
    assert interruption is not None
    int_enabled = interruption.get("enabled") if isinstance(interruption, dict) else getattr(interruption, "enabled", None)
    int_mode = interruption.get("mode") if isinstance(interruption, dict) else getattr(interruption, "mode", None)
    int_min_dur = interruption.get("min_duration") if isinstance(interruption, dict) else getattr(interruption, "min_duration", None)
    assert int_enabled is True
    assert int_mode == "vad"
    assert int_min_dur <= 0.20  # Fast barge-in trigger (<200ms)

    # Dynamic endpointing configuration
    endpointing = turn_options.get("endpointing") if isinstance(turn_options, dict) else getattr(turn_options, "endpointing", None)
    assert endpointing is not None
    ep_mode = endpointing.get("mode") if isinstance(endpointing, dict) else getattr(endpointing, "mode", None)
    ep_min_delay = endpointing.get("min_delay") if isinstance(endpointing, dict) else getattr(endpointing, "min_delay", None)
    ep_max_delay = endpointing.get("max_delay") if isinstance(endpointing, dict) else getattr(endpointing, "max_delay", None)
    assert ep_mode == "dynamic"
    assert ep_min_delay <= 0.05
    assert ep_max_delay <= 0.25


# ============================================================================
# 3. Post-Call Intelligence: Heuristic Insights Extraction
# ============================================================================

def test_heuristic_frustrated_and_emergency_caller():
    """Verify frustrated caller in severe pain is classified high urgency and frustrated sentiment."""
    transcript = (
        "Caller: I have severe pain in my lower molar and it hurts a lot! I called twice earlier and nobody answered!\n"
        "Receptionist: I am so sorry you are in pain. Let me help you immediately."
    )
    turns = [
        CallTurn(speaker="caller", text="I have severe pain in my lower molar and it hurts a lot!"),
        CallTurn(speaker="agent", text="I am so sorry you are in pain."),
    ]
    insights = _heuristic_extract_insights(transcript, turns, [])

    assert insights["urgency"] == "high"
    assert insights["sentiment"] == "frustrated"
    assert "urgent" in insights["tags"]
    assert insights["intent"] == "appointment_request"


def test_heuristic_hinglish_and_appointment_intent():
    """Verify Hinglish phrases are tagged hinglish_caller and mapped to appointment_request."""
    transcript = (
        "Caller: Arre actually mujhe kal shaam ko root canal ke liye doctor se milna hai. Can I book a slot?\n"
        "Receptionist: Haan ji, bilkul! We have slots open tomorrow at 5 PM."
    )
    turns = [
        CallTurn(speaker="caller", text="Arre actually mujhe kal shaam ko root canal ke liye doctor se milna hai."),
        CallTurn(speaker="agent", text="Haan ji, bilkul!"),
    ]
    insights = _heuristic_extract_insights(transcript, turns, [])

    assert insights["intent"] == "appointment_request"
    assert "hinglish_caller" in insights["tags"]
    assert insights["urgency"] == "normal"


def test_heuristic_pricing_inquiry_intent():
    """Verify questions about rates/fees classify as pricing_inquiry."""
    transcript = (
        "Caller: Hello, what is the cost of tooth cleaning and how much do you charge?\n"
        "Receptionist: Our routine dental cleaning is 1,500 rupees."
    )
    turns = [
        CallTurn(speaker="caller", text="Hello, what is the cost of tooth cleaning?"),
    ]
    insights = _heuristic_extract_insights(transcript, turns, [])

    assert insights["intent"] == "pricing_inquiry"
    assert "pricing_inquiry" in insights["tags"]


# ============================================================================
# 4. End-to-End Extraction & Call Model Persistence Tests
# ============================================================================

@pytest.mark.asyncio
async def test_end_call_async_persists_intelligence(test_business_and_call):
    """Verify ending a call populates intent, urgency, sentiment, tags, and structured_notes in DB."""
    b_id = test_business_and_call["business_id"]
    c_id = test_business_and_call["call_id"]

    await record_call_turn_async(
        call_id=c_id,
        business_id=b_id,
        speaker="caller",
        text="Haan ji, I need an emergency appointment today. My filling fell out and it is bleeding!",
    )
    await record_call_turn_async(
        call_id=c_id,
        business_id=b_id,
        speaker="agent",
        text="I understand this is urgent. We can see you today at 4:30 PM.",
        latency_ms=350.0,
    )

    finished_call = await end_call_async(call_id=c_id, generate_summary=True)

    assert finished_call is not None
    assert finished_call.ended_at is not None
    assert finished_call.intent == "appointment_request"
    assert finished_call.urgency == "high"
    assert "urgent" in finished_call.tags
    assert "hinglish_caller" in finished_call.tags
    assert finished_call.structured_notes is not None
    assert "key_details" in finished_call.structured_notes

    # Verify directly from database
    async with get_async_session() as session:
        call_in_db = await session.get(Call, c_id)
        assert call_in_db is not None
        assert call_in_db.intent == "appointment_request"
        assert call_in_db.urgency == "high"
        assert "urgent" in call_in_db.tags
        assert "hinglish_caller" in call_in_db.tags
        assert isinstance(call_in_db.structured_notes, dict)


@pytest.mark.asyncio
async def test_llm_insights_json_parsing_and_fallback(test_business_and_call):
    """Verify LLM JSON output is parsed correctly and invalid fields fallback safely."""
    b_id = test_business_and_call["business_id"]
    c_id = test_business_and_call["call_id"]

    await record_call_turn_async(
        call_id=c_id,
        business_id=b_id,
        speaker="caller",
        text="What are your clinic opening hours on Sunday?",
    )

    mock_llm_response = """
    ```json
    {
      "summary": "Caller inquired regarding Sunday operating hours.",
      "intent": "general_faq",
      "urgency": "normal",
      "sentiment": "neutral",
      "tags": ["faq", "hours", "sunday"],
      "structured_notes": {
        "key_details": "Asked about Sunday clinic hours",
        "action_items": "None"
      }
    }
    ```
    """

    with patch("callwise.calls.manager.get_llm_provider") as mock_get_llm:
        mock_provider = AsyncMock()
        mock_provider.generate_response.return_value = mock_llm_response
        mock_get_llm.return_value = mock_provider

        insights = await extract_call_insights_async(c_id)

        assert insights["intent"] == "general_faq"
        assert insights["urgency"] == "normal"
        assert insights["sentiment"] == "neutral"
        assert "sunday" in insights["tags"]
        assert insights["structured_notes"]["key_details"] == "Asked about Sunday clinic hours"
