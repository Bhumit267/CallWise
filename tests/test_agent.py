"""Tests for Step 5: System prompt builder, CallwiseToolset, and Agent configuration."""

from datetime import datetime
import uuid
import pytest
import pytest_asyncio
from sqlalchemy import select
from zoneinfo import ZoneInfo

from callwise.agent.prompt import build_system_prompt
from callwise.agent.tools import CallwiseToolset
from callwise.agent.voice_agent import create_voice_agent
from callwise.agent.text_agent import TextAgent
from callwise.db.models import Business, Message, Call
from callwise.db.session import async_engine, get_async_session, get_sync_session
from callwise.knowledge.ingest import ingest_file


@pytest_asyncio.fixture(autouse=True)
async def cleanup_db_pool():
    """Ensure async engine pool is disposed within the running event loop."""
    yield
    await async_engine.dispose()


@pytest.fixture
def sample_business():
    """Create an in-memory Business object for testing prompts and tools."""
    return Business(
        id=uuid.uuid4(),
        name="Apex Smiles Dental",
        business_type="dental clinic",
        timezone="America/New_York",
        tone="professional, warm, and reassuring",
        greeting="Thank you for calling Apex Smiles Dental. How may I help you today?",
        hours={
            "monday": {"open": "08:00", "close": "17:00", "closed": False},
            "tuesday": {"open": "08:00", "close": "17:00", "closed": False},
            "wednesday": {"open": "08:00", "close": "17:00", "closed": False},
            "thursday": {"open": "08:00", "close": "17:00", "closed": False},
            "friday": {"open": "08:00", "close": "14:00", "closed": False},
            "saturday": {"open": None, "close": None, "closed": True},
            "sunday": {"open": None, "close": None, "closed": True},
        },
    )


def test_build_system_prompt(sample_business):
    """Test system prompt properly incorporates business info and strict guidelines."""
    fixed_time = datetime(2026, 11, 2, 10, 30, tzinfo=ZoneInfo("America/New_York"))
    prompt = build_system_prompt(sample_business, at_time=fixed_time)

    # Name and tone
    assert "Apex Smiles Dental" in prompt
    assert "dental clinic" in prompt
    assert "professional, warm, and reassuring" in prompt

    # Timezone & context
    assert "America/New_York" in prompt
    assert "Monday, November 02, 2026" in prompt

    # Weekly schedule in context
    assert "Monday: 8 AM to 5 PM" in prompt
    assert "Saturday: Closed" in prompt

    # Directives & Safety
    assert "medical, legal, or financial advice" in prompt
    assert "search_knowledge" in prompt
    assert "take_message" in prompt
    assert "get_business_hours" in prompt
    assert "Never use markdown formatting" in prompt


def test_toolset_get_business_hours(sample_business):
    """Test get_business_hours tool method."""
    toolset = CallwiseToolset(sample_business)

    # Specific day - open
    mon_hours = toolset.get_business_hours(day="Monday")
    assert "open from 08:00 to 17:00" in mon_hours

    # Specific day - closed
    sat_hours = toolset.get_business_hours(day="Saturday")
    assert "is closed" in sat_hours

    # General / current hours
    current_status = toolset.get_business_hours()
    assert "closed" in current_status.lower() or "open" in current_status.lower()
    assert "weekly schedule" in current_status.lower()


@pytest.mark.asyncio
async def test_toolset_take_message(sample_business):
    """Test take_message saves to the database correctly."""
    # First persist business to DB to satisfy FK constraints
    async with get_async_session() as session:
        session.add(sample_business)
        await session.commit()

    call_id = uuid.uuid4()
    async with get_async_session() as session:
        test_call = Call(id=call_id, business_id=sample_business.id)
        session.add(test_call)
        await session.commit()

    toolset = CallwiseToolset(sample_business, call_id=call_id)
    result = await toolset.take_message(
        caller_name="Alice Smith",
        callback_number="555-987-6543",
        reason="Need to reschedule teeth whitening appointment",
    )

    assert "Message recorded successfully" in result
    assert "Alice Smith" in result
    assert "555-987-6543" in result

    # Verify database persistence
    async with get_async_session() as session:
        msg = await session.scalar(
            select(Message).where(Message.call_id == call_id)
        )
        assert msg is not None
        assert msg.caller_name == "Alice Smith"
        assert msg.callback_number == "555-987-6543"
        assert msg.reason == "Need to reschedule teeth whitening appointment"
        assert msg.business_id == sample_business.id


@pytest.mark.asyncio
async def test_toolset_search_knowledge(sample_business, tmp_path):
    """Test search_knowledge tool matches ingested documents and handles misses."""
    # Ingest a sample doc
    sample_faq = tmp_path / "dental_faq.txt"
    sample_faq.write_text(
        "Whitening Procedure:\nProfessional in-office whitening costs $350 and takes 60 minutes.\n\n"
        "Dental Implants:\nImplants start at $2000 per tooth including crown.",
        encoding="utf-8",
    )

    async with get_async_session() as session:
        existing = await session.get(Business, sample_business.id)
        if not existing:
            session.add(sample_business)
            await session.commit()

    ingest_file(
        business_id=sample_business.id,
        file_path=sample_faq,
        title="Dental Services FAQ",
    )

    toolset = CallwiseToolset(sample_business)

    # Test hit
    hit_result = await toolset.search_knowledge("How much does professional whitening cost?")
    assert "Information found in 'Dental Services FAQ'" in hit_result
    assert "$350" in hit_result

    # Test miss
    miss_result = await toolset.search_knowledge("Do you repair antique grandfather clocks?")
    assert "NO MATCH" in miss_result
    assert "offer to take a message" in miss_result


def test_toolset_livekit_tools_wrapper(sample_business):
    """Test get_livekit_tools returns valid decorated tools."""
    toolset = CallwiseToolset(sample_business)
    tools = toolset.get_livekit_tools()

    assert len(tools) == 3
    tool_names = [t.__name__ for t in tools]
    assert "get_business_hours" in tool_names
    assert "search_knowledge" in tool_names
    assert "take_message" in tool_names


@pytest.mark.asyncio
async def test_create_voice_agent(sample_business):
    """Test voice agent creation initializes Agent and AgentSession without errors."""
    agent, session = create_voice_agent(sample_business)
    assert agent is not None
    assert session is not None
    assert "Apex Smiles Dental" in agent.instructions
    assert len(agent.tools) == 3


@pytest.mark.asyncio
async def test_text_agent_simulated_turn(sample_business):
    """Test TextAgent handles user queries and tool invocation flow."""
    agent = TextAgent(sample_business, provider_name="groq")
    assert agent.business.name == "Apex Smiles Dental"
    assert len(agent.conversation_history) == 1
    assert agent.conversation_history[0]["role"] == "system"

    # Test tool execution directly on agent
    hours_output = await agent._execute_tool("get_business_hours", {"day": "Friday"})
    assert "08:00 to 14:00" in hours_output
