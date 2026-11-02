"""Unit and integration tests for Step 6: Call logging, turns, latencies, and summaries."""

from datetime import datetime, timezone
import uuid
import pytest
import pytest_asyncio
from sqlalchemy import select
from typer.testing import CliRunner

from callwise.calls.manager import (
    end_call,
    end_call_async,
    generate_call_summary_async,
    record_call_turn,
    record_call_turn_async,
)
from callwise.cli import app
from callwise.db.models import Business, Call, CallTurn, Message, KnowledgeMiss
from callwise.db.session import async_engine, get_async_session, get_sync_session

runner = CliRunner()


@pytest_asyncio.fixture(autouse=True)
async def cleanup_db_pool():
    """Ensure async engine pool is disposed within the running event loop."""
    yield
    await async_engine.dispose()


@pytest.fixture
def seeded_call():
    """Create a persistent Business and Call record for testing."""
    biz_id = uuid.uuid4()
    c_id = uuid.uuid4()
    with get_sync_session() as session:
        biz = Business(
            id=biz_id,
            name="Apex Family Dental",
            business_type="dental clinic",
            timezone="America/New_York",
            tone="professional, warm",
            greeting="Welcome to Apex Dental.",
            hours={},
        )
        session.add(biz)
        call_obj = Call(
            id=c_id,
            business_id=biz_id,
            caller_number="555-0199",
            llm_provider="groq",
            llm_model="openai/gpt-oss-120b",
        )
        session.add(call_obj)
        session.flush()

    return {"business_id": biz_id, "call_id": c_id}


@pytest.mark.asyncio
async def test_record_call_turn_async(seeded_call):
    """Verify recording turns records speaker, text, and latency accurately."""
    b_id = seeded_call["business_id"]
    c_id = seeded_call["call_id"]

    turn1 = await record_call_turn_async(
        call_id=c_id,
        business_id=b_id,
        speaker="caller",
        text="Hello, are you open today?",
    )
    assert turn1.id is not None
    assert turn1.speaker == "caller"
    assert turn1.text == "Hello, are you open today?"
    assert turn1.latency_ms is None

    turn2 = await record_call_turn_async(
        call_id=c_id,
        business_id=b_id,
        speaker="agent",
        text="Yes, we are open until 5 PM today.",
        latency_ms=482.35,
    )
    assert turn2.speaker == "agent"
    assert turn2.latency_ms == 482.35

    # Verify database persistence
    async with get_async_session() as session:
        turns = (
            await session.scalars(
                select(CallTurn).where(CallTurn.call_id == c_id).order_by(CallTurn.timestamp)
            )
        ).all()
        assert len(turns) == 2
        assert turns[0].speaker == "caller"
        assert turns[1].speaker == "agent"
        assert turns[1].latency_ms == 482.35


@pytest.mark.asyncio
async def test_end_call_lifecycle_and_summary(seeded_call):
    """Test ending a call sets ended_at, duration_seconds, and generates summary."""
    b_id = seeded_call["business_id"]
    c_id = seeded_call["call_id"]

    await record_call_turn_async(
        call_id=c_id,
        business_id=b_id,
        speaker="caller",
        text="I would like to reschedule my root canal appointment to next Tuesday.",
    )
    await record_call_turn_async(
        call_id=c_id,
        business_id=b_id,
        speaker="agent",
        text="I have taken down your message and our scheduling team will call you back to confirm.",
        latency_ms=620.0,
    )

    # Record message for call
    async with get_async_session() as session:
        msg = Message(
            business_id=b_id,
            call_id=c_id,
            caller_name="Jordan Baker",
            callback_number="555-0144",
            reason="Reschedule root canal to next Tuesday",
        )
        session.add(msg)
        await session.commit()

    finished = await end_call_async(call_id=c_id, generate_summary=True)
    assert finished is not None
    assert finished.ended_at is not None
    assert finished.duration_seconds >= 0.0
    assert finished.summary is not None
    assert len(finished.summary) > 10


def test_cli_call_inspection_commands(seeded_call):
    """Test CLI commands: list-calls, show-call, list-messages, and list-misses."""
    b_id = seeded_call["business_id"]
    c_id = seeded_call["call_id"]

    # Record turns & message synchronously
    record_call_turn(c_id, b_id, "caller", "What is your teeth whitening price?")
    record_call_turn(c_id, b_id, "agent", "Our in-office whitening is $350.", latency_ms=510.0)

    with get_sync_session() as session:
        msg = Message(
            business_id=b_id,
            call_id=c_id,
            caller_name="Morgan",
            callback_number="555-4321",
            reason="Price inquiry",
        )
        session.add(msg)
        km = KnowledgeMiss(
            business_id=b_id,
            call_id=c_id,
            query="Do you do acupuncture?",
        )
        session.add(km)
        session.commit()

    end_call(c_id, generate_summary=False)

    # Test list-calls
    res1 = runner.invoke(app, ["list-calls", "--business-id", str(b_id)])
    assert res1.exit_code == 0
    assert "Call ID" in res1.output
    assert "Apex Family Dental" in res1.output

    # Test show-call
    res2 = runner.invoke(app, ["show-call", "--call-id", str(c_id)])
    assert res2.exit_code == 0
    assert "Call Details" in res2.output
    assert "CALLER" in res2.output
    assert "AGENT" in res2.output
    assert "510ms" in res2.output
    assert "Messages Taken" in res2.output
    assert "Morgan" in res2.output
    assert "Knowledge Misses" in res2.output

    # Test list-messages
    res3 = runner.invoke(app, ["list-messages", "--business-id", str(b_id)])
    assert res3.exit_code == 0
    assert "Morgan" in res3.output
    assert "555-4321" in res3.output

    # Test list-misses
    res4 = runner.invoke(app, ["list-misses", "--business-id", str(b_id)])
    assert res4.exit_code == 0
    assert "acupuncture" in res4.output
