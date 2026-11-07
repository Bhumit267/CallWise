"""Tests for Phase 4 Step 6: Usage summary API, per-call cost tracking, and call source resolution."""

from datetime import datetime, timezone
import uuid
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from callwise.api.main import app
from callwise.api.security import auth_rate_limiter, hash_password, hash_token
from callwise.calls.usage import calculate_estimated_cost
from callwise.db.models import (
    Business,
    Call,
    Membership,
    Session as UserSession,
    UsageLimits,
    UsageRecord,
    User,
)
from callwise.db.session import async_engine, get_async_session


@pytest_asyncio.fixture(autouse=True)
async def cleanup():
    auth_rate_limiter.clear_all()
    yield
    auth_rate_limiter.clear_all()
    await async_engine.dispose()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_usage_summary_and_call_cost_api(client: AsyncClient):
    """Verify tenant staff can retrieve monthly usage vs limits and recent session costs."""
    biz_id = uuid.uuid4()
    user_id = uuid.uuid4()
    session_token = f"sess_{uuid.uuid4().hex}"

    async with get_async_session() as session:
        biz = Business(
            id=biz_id,
            name="Apex Horizon Spa",
            business_type="Spa",
            greeting="Welcome to Apex Horizon Spa",
            hours={},
        )
        session.add(biz)

        user = User(
            id=user_id,
            email=f"owner_{uuid.uuid4().hex[:6]}@apexspa.com",
            password_hash=hash_password("Pass12345!"),
            name="Apex Owner",
        )
        session.add(user)

        membership = Membership(
            id=uuid.uuid4(),
            user_id=user_id,
            business_id=biz_id,
            role="owner",
        )
        session.add(membership)

        user_sess = UserSession(
            id=uuid.uuid4(),
            user_id=user_id,
            current_business_id=biz_id,
            session_token_hash=hash_token(session_token),
            expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        session.add(user_sess)

        # Seed UsageLimits
        limits = UsageLimits(
            id=uuid.uuid4(),
            business_id=biz_id,
            voice_minutes_per_month=400,
            chat_messages_per_month=1200,
            max_concurrent_calls=4,
            max_call_duration_seconds=900,
            llm_tokens_per_month=750000,
            hard_limit_enforced=True,
        )
        session.add(limits)

        # Seed UsageRecords
        rec1 = UsageRecord(
            id=uuid.uuid4(),
            business_id=biz_id,
            session_type="phone",
            duration_seconds=120,
            stt_seconds=115.0,
            tts_characters=300,
            llm_input_tokens=1500,
            llm_output_tokens=400,
            llm_provider="groq",
            llm_model="llama-3.3-70b-versatile",
            estimated_cost_usd=0.0125,
        )
        session.add(rec1)

        rec2 = UsageRecord(
            id=uuid.uuid4(),
            business_id=biz_id,
            session_type="widget",
            duration_seconds=45,
            stt_seconds=0.0,
            tts_characters=0,
            llm_input_tokens=800,
            llm_output_tokens=250,
            llm_provider="groq",
            llm_model="llama-3.3-70b-versatile",
            estimated_cost_usd=0.00067,
        )
        session.add(rec2)
        await session.commit()

    headers = {"Authorization": f"Bearer {session_token}"}

    # 1. GET /api/usage/summary
    res = await client.get("/api/usage/summary", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["limits"]["voice_minutes_per_month"] == 400
    assert data["limits"]["chat_messages_per_month"] == 1200
    assert data["current_month"]["voice_minutes"] == 2.0  # 120 secs / 60
    assert data["current_month"]["chat_messages"] == 1
    assert data["current_month"]["llm_tokens"] == (1500 + 400 + 800 + 250)
    assert data["current_month"]["total_cost_usd"] > 0
    assert "pricing_table" in data
    assert len(data["daily_usage"]) >= 14

    # 2. GET /api/usage/calls
    calls_res = await client.get("/api/usage/calls?limit=10", headers=headers)
    assert calls_res.status_code == 200
    records_list = calls_res.json()
    assert len(records_list) >= 2
    session_types = {r["session_type"] for r in records_list}
    assert "phone" in session_types
    assert "widget" in session_types


@pytest.mark.asyncio
async def test_call_source_identification_phone_chat_web(client: AsyncClient):
    """Verify Call list and detail endpoints identify source (phone/chat/web)."""
    biz_id = uuid.uuid4()
    user_id = uuid.uuid4()
    session_token = f"sess_{uuid.uuid4().hex}"

    call_phone_id = uuid.uuid4()
    call_chat_id = uuid.uuid4()
    call_web_id = uuid.uuid4()

    async with get_async_session() as session:
        biz = Business(
            id=biz_id,
            name="Source Test Business",
            business_type="Services",
            greeting="Welcome",
            hours={},
        )
        session.add(biz)

        user = User(
            id=user_id,
            email=f"staff_{uuid.uuid4().hex[:6]}@sourcetest.com",
            password_hash=hash_password("Pass12345!"),
            name="Staff Member",
        )
        session.add(user)

        membership = Membership(
            id=uuid.uuid4(),
            user_id=user_id,
            business_id=biz_id,
            role="staff",
        )
        session.add(membership)

        user_sess = UserSession(
            id=uuid.uuid4(),
            user_id=user_id,
            current_business_id=biz_id,
            session_token_hash=hash_token(session_token),
            expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        session.add(user_sess)

        call_phone = Call(
            id=call_phone_id,
            business_id=biz_id,
            caller_number="+15551234567",
            summary="Incoming telephone inquiry",
        )
        call_chat = Call(
            id=call_chat_id,
            business_id=biz_id,
            caller_number="widget_127.0.0.1",
            summary="Website widget chat session",
        )
        call_web = Call(
            id=call_web_id,
            business_id=biz_id,
            caller_number="web_client_agent",
            summary="Browser WebRTC call session",
        )
        session.add_all([call_phone, call_chat, call_web])
        await session.commit()

    headers = {"Authorization": f"Bearer {session_token}"}

    # 1. Test List Endpoint
    res = await client.get("/api/calls", headers=headers)
    assert res.status_code == 200
    items = res.json()["items"]
    source_map = {item["id"]: item["source"] for item in items}

    assert source_map[str(call_phone_id)] == "phone"
    assert source_map[str(call_chat_id)] == "chat"
    assert source_map[str(call_web_id)] == "web"

    # 2. Test Detail Endpoint
    detail_res = await client.get(f"/api/calls/{call_chat_id}", headers=headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["source"] == "chat"
