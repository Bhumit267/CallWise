"""Unit and tenant isolation tests for core read APIs (Calls, Messages, Appointments, Contacts, Follow-ups, Misses, Inbox)."""

from datetime import datetime, timedelta, timezone
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from callwise.api.main import app
from callwise.api.security import auth_rate_limiter, hash_password, hash_token
from callwise.db.models import (
    Appointment,
    Business,
    Call,
    CallTurn,
    Contact,
    FollowUp,
    KnowledgeMiss,
    Membership,
    Message,
    Service,
    Session as UserSession,
    Transfer,
    User,
)
from callwise.db.session import async_engine, get_async_session


@pytest_asyncio.fixture(autouse=True)
async def cleanup():
    """Reset rate limiter and engine pool."""
    auth_rate_limiter.clear_all()
    yield
    auth_rate_limiter.clear_all()
    await async_engine.dispose()


@pytest_asyncio.fixture
async def client():
    """Async HTTP test client bound to FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def create_tenant_environment(session, biz_name: str, user_email: str, role: str = "staff"):
    """Helper to provision a tenant business, user, membership, and active session."""
    now = datetime.now(timezone.utc)
    biz = Business(
        id=uuid.uuid4(),
        name=biz_name,
        business_type="Dental",
        timezone="America/New_York",
        greeting=f"Hello from {biz_name}",
        tone="professional",
    )
    user = User(
        id=uuid.uuid4(),
        email=user_email,
        password_hash=hash_password("SecurePassword123!"),
        name=f"User {biz_name}",
        is_active=True,
    )
    membership = Membership(
        id=uuid.uuid4(),
        user_id=user.id,
        business_id=biz.id,
        role=role,
    )
    raw_token = f"test_session_{uuid.uuid4().hex}"
    user_session = UserSession(
        id=uuid.uuid4(),
        user_id=user.id,
        current_business_id=biz.id,
        session_token_hash=hash_token(raw_token),
        expires_at=now + timedelta(days=7),
    )
    session.add_all([biz, user, membership, user_session])
    await session.commit()
    return biz, user, raw_token


@pytest.mark.asyncio
async def test_calls_read_and_isolation(client: AsyncClient):
    """Test calls list with masking, search, full detail unmasked, and cross-tenant isolation."""
    now = datetime.now(timezone.utc)

    async with get_async_session() as session:
        biz_a, user_a, token_a = await create_tenant_environment(session, "Biz A Dental", f"owner_a_{uuid.uuid4().hex[:6]}@example.com")
        biz_b, user_b, token_b = await create_tenant_environment(session, "Biz B Dental", f"owner_b_{uuid.uuid4().hex[:6]}@example.com")

        # Create Call for Biz A
        call_a = Call(
            id=uuid.uuid4(),
            business_id=biz_a.id,
            caller_number="+15551234567",
            started_at=now - timedelta(hours=1),
            ended_at=now - timedelta(minutes=50),
            duration_seconds=600.0,
            summary="Patient asking for teeth cleaning schedule.",
        )
        turn_a1 = CallTurn(
            id=uuid.uuid4(),
            business_id=biz_a.id,
            call_id=call_a.id,
            speaker="caller",
            text="Hi, I need an appointment.",
            latency_ms=120.0,
            timestamp=now - timedelta(minutes=59),
        )
        turn_a2 = CallTurn(
            id=uuid.uuid4(),
            business_id=biz_a.id,
            call_id=call_a.id,
            speaker="agent",
            text="I can help you with that.",
            latency_ms=450.0,
            timestamp=now - timedelta(minutes=58),
        )

        # Create Call for Biz B
        call_b = Call(
            id=uuid.uuid4(),
            business_id=biz_b.id,
            caller_number="+15559876543",
            started_at=now - timedelta(hours=2),
            summary="Biz B call summary.",
        )

        session.add_all([call_a, turn_a1, turn_a2, call_b])
        await session.commit()

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 1. Biz A lists calls: must see call_a with masked phone number
    resp_a = await client.get("/api/calls", headers=headers_a)
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    assert data_a["total"] == 1
    assert data_a["items"][0]["id"] == str(call_a.id)
    assert data_a["items"][0]["caller_number"] == "***-***-4567"  # Masked!
    assert data_a["items"][0]["turn_count"] == 2

    # 2. Biz A gets call_a detail: must see unmasked phone number and turns
    detail_resp = await client.get(f"/api/calls/{call_a.id}", headers=headers_a)
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["caller_number"] == "+15551234567"  # Unmasked in detail!
    assert len(detail_data["turns"]) == 2
    assert detail_data["turns"][0]["speaker"] == "caller"

    # 3. Biz A attempts to read Biz B's call detail: MUST return 404
    cross_resp = await client.get(f"/api/calls/{call_b.id}", headers=headers_a)
    assert cross_resp.status_code == 404

    # 4. Biz B lists calls: must NOT see call_a
    resp_b = await client.get("/api/calls", headers=headers_b)
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    call_ids_b = [item["id"] for item in data_b["items"]]
    assert str(call_a.id) not in call_ids_b
    assert str(call_b.id) in call_ids_b


@pytest.mark.asyncio
async def test_messages_read_and_isolation(client: AsyncClient):
    """Test callback messages list (masked) and detail (unmasked), with cross-tenant isolation."""
    now = datetime.now(timezone.utc)

    async with get_async_session() as session:
        biz_a, _, token_a = await create_tenant_environment(session, "Clinic A", f"doc_a_{uuid.uuid4().hex[:6]}@example.com")
        biz_b, _, token_b = await create_tenant_environment(session, "Clinic B", f"doc_b_{uuid.uuid4().hex[:6]}@example.com")

        msg_a = Message(
            id=uuid.uuid4(),
            business_id=biz_a.id,
            caller_name="Alice Smith",
            callback_number="+15554443322",
            reason="Wants to ask about dental implant pricing.",
        )
        msg_b = Message(
            id=uuid.uuid4(),
            business_id=biz_b.id,
            caller_name="Bob Jones",
            callback_number="+15559998877",
            reason="Question for Clinic B.",
        )
        session.add_all([msg_a, msg_b])
        await session.commit()

    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Biz A lists messages: masked number
    list_resp = await client.get("/api/messages", headers=headers_a)
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] == 1
    assert list_data["items"][0]["caller_name"] == "Alice Smith"
    assert list_data["items"][0]["callback_number"] == "***-***-3322"

    # Biz A gets detail: unmasked number
    detail_resp = await client.get(f"/api/messages/{msg_a.id}", headers=headers_a)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["callback_number"] == "+15554443322"

    # Biz A attempts cross-tenant access to msg_b: 404
    cross_resp = await client.get(f"/api/messages/{msg_b.id}", headers=headers_a)
    assert cross_resp.status_code == 404


@pytest.mark.asyncio
async def test_appointments_read_calendar_and_isolation(client: AsyncClient):
    """Test appointments list, calendar range fetch, detail unmasking, and isolation."""
    now = datetime.now(timezone.utc)

    async with get_async_session() as session:
        biz_a, _, token_a = await create_tenant_environment(session, "Dental A", f"user_app_a_{uuid.uuid4().hex[:6]}@example.com")
        biz_b, _, token_b = await create_tenant_environment(session, "Dental B", f"user_app_b_{uuid.uuid4().hex[:6]}@example.com")

        svc_a = Service(
            id=uuid.uuid4(),
            business_id=biz_a.id,
            name="General Consultation",
            duration_minutes=30,
            price=150.0,
            is_active=True,
        )
        svc_b = Service(
            id=uuid.uuid4(),
            business_id=biz_b.id,
            name="Teeth Whitening",
            duration_minutes=60,
            price=300.0,
            is_active=True,
        )
        session.add_all([svc_a, svc_b])
        await session.flush()

        app_a = Appointment(
            id=uuid.uuid4(),
            business_id=biz_a.id,
            service_id=svc_a.id,
            customer_name="Carol White",
            customer_phone="+15556667788",
            customer_email="carol@example.com",
            start_at=now + timedelta(days=1),
            end_at=now + timedelta(days=1, minutes=30),
            status="booked",
            booking_code_hash="fakehash",
        )
        app_b = Appointment(
            id=uuid.uuid4(),
            business_id=biz_b.id,
            service_id=svc_b.id,
            customer_name="Dave Black",
            customer_phone="+15551112233",
            customer_email="dave@example.com",
            start_at=now + timedelta(days=2),
            end_at=now + timedelta(days=2, hours=1),
            status="booked",
            booking_code_hash="fakehash",
        )
        session.add_all([app_a, app_b])
        await session.commit()

    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 1. Biz A lists appointments: phone masked
    list_resp = await client.get("/api/appointments", headers=headers_a)
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["customer_phone"] == "***-***-7788"
    assert items[0]["service_name"] == "General Consultation"

    # 2. Biz A calendar range fetch
    start_str = now.isoformat()
    end_str = (now + timedelta(days=5)).isoformat()
    cal_resp = await client.get(f"/api/appointments/calendar?start_date={start_str}&end_date={end_str}", headers=headers_a)
    assert cal_resp.status_code == 200
    cal_items = cal_resp.json()
    assert len(cal_items) == 1
    assert cal_items[0]["id"] == str(app_a.id)

    # 3. Biz A detail: phone unmasked
    detail_resp = await client.get(f"/api/appointments/{app_a.id}", headers=headers_a)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["customer_phone"] == "+15556667788"

    # 4. Biz A cross-tenant access to app_b: 404
    cross_resp = await client.get(f"/api/appointments/{app_b.id}", headers=headers_a)
    assert cross_resp.status_code == 404


@pytest.mark.asyncio
async def test_contacts_read_and_detail(client: AsyncClient):
    """Test contacts list and detail with timeline history."""
    now = datetime.now(timezone.utc)

    async with get_async_session() as session:
        biz_a, _, token_a = await create_tenant_environment(session, "Care A", f"care_a_{uuid.uuid4().hex[:6]}@example.com")
        biz_b, _, token_b = await create_tenant_environment(session, "Care B", f"care_b_{uuid.uuid4().hex[:6]}@example.com")

        contact_a = Contact(
            id=uuid.uuid4(),
            business_id=biz_a.id,
            name="Emma Watson",
            phone="+15557778899",
            email="emma@example.com",
            notes="VIP client",
            do_not_contact=False,
        )
        contact_b = Contact(
            id=uuid.uuid4(),
            business_id=biz_b.id,
            name="Frank Miller",
            phone="+15553332211",
            email="frank@example.com",
        )
        session.add_all([contact_a, contact_b])
        await session.commit()

    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Biz A lists contacts
    resp = await client.get("/api/contacts", headers=headers_a)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "Emma Watson"
    assert items[0]["phone"] == "***-***-8899"

    # Biz A contact detail: unmasked phone
    detail_resp = await client.get(f"/api/contacts/{contact_a.id}", headers=headers_a)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["phone"] == "+15557778899"

    # Biz A cross-tenant contact access: 404
    cross_resp = await client.get(f"/api/contacts/{contact_b.id}", headers=headers_a)
    assert cross_resp.status_code == 404


@pytest.mark.asyncio
async def test_follow_ups_and_knowledge_misses(client: AsyncClient):
    """Test follow-ups and grouped knowledge misses."""
    now = datetime.now(timezone.utc)

    async with get_async_session() as session:
        biz_a, user_a, token_a = await create_tenant_environment(session, "Health A", f"health_a_{uuid.uuid4().hex[:6]}@example.com")
        biz_b, user_b, token_b = await create_tenant_environment(session, "Health B", f"health_b_{uuid.uuid4().hex[:6]}@example.com")

        # Follow-up
        fu_a = FollowUp(
            id=uuid.uuid4(),
            business_id=biz_a.id,
            assigned_to_user_id=user_a.id,
            title="Call back regarding insurance",
            description="Caller wanted to know if Aetna covers root canal.",
            source="message",
            status="open",
        )
        fu_b = FollowUp(
            id=uuid.uuid4(),
            business_id=biz_b.id,
            title="Follow up for Biz B",
            source="manual",
            status="open",
        )

        # Knowledge misses
        km_a1 = KnowledgeMiss(
            id=uuid.uuid4(),
            business_id=biz_a.id,
            query="Do you offer sedation dentistry?",
            status="unresolved",
        )
        km_a2 = KnowledgeMiss(
            id=uuid.uuid4(),
            business_id=biz_a.id,
            query="do you offer sedation dentistry?",  # case insensitive grouping test
            status="unresolved",
        )
        km_b = KnowledgeMiss(
            id=uuid.uuid4(),
            business_id=biz_b.id,
            query="Biz B missed query",
            status="unresolved",
        )

        session.add_all([fu_a, fu_b, km_a1, km_a2, km_b])
        await session.commit()

    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 1. Follow-ups list
    fu_resp = await client.get("/api/follow-ups?status=open", headers=headers_a)
    assert fu_resp.status_code == 200
    fu_items = fu_resp.json()["items"]
    assert len(fu_items) == 1
    assert fu_items[0]["title"] == "Call back regarding insurance"

    # Follow-up detail
    fu_det = await client.get(f"/api/follow-ups/{fu_a.id}", headers=headers_a)
    assert fu_det.status_code == 200
    assert fu_det.json()["assigned_to_email"] == user_a.email

    # Cross-tenant follow-up: 404
    cross_fu = await client.get(f"/api/follow-ups/{fu_b.id}", headers=headers_a)
    assert cross_fu.status_code == 404

    # 2. Knowledge misses list
    km_resp = await client.get("/api/knowledge-misses", headers=headers_a)
    assert km_resp.status_code == 200
    assert km_resp.json()["total"] == 2

    # Grouped knowledge misses
    grp_resp = await client.get("/api/knowledge-misses/grouped", headers=headers_a)
    assert grp_resp.status_code == 200
    groups = grp_resp.json()
    assert len(groups) == 1
    assert groups[0]["count"] == 2
    assert "sedation dentistry" in groups[0]["query"].lower()


@pytest.mark.asyncio
async def test_unified_inbox(client: AsyncClient):
    """Test unified activity inbox timeline and filters."""
    now = datetime.now(timezone.utc)

    async with get_async_session() as session:
        biz_a, _, token_a = await create_tenant_environment(session, "Inbox A", f"inbox_a_{uuid.uuid4().hex[:6]}@example.com")
        biz_b, _, token_b = await create_tenant_environment(session, "Inbox B", f"inbox_b_{uuid.uuid4().hex[:6]}@example.com")

        # Add 1 call, 1 message, 1 transfer for Biz A
        c_a = Call(
            id=uuid.uuid4(),
            business_id=biz_a.id,
            caller_number="+15550001111",
            started_at=now - timedelta(hours=3),
            summary="Call for inbox test",
        )
        m_a = Message(
            id=uuid.uuid4(),
            business_id=biz_a.id,
            caller_name="Grace Hopper",
            callback_number="+15552223333",
            reason="Message for inbox test",
            created_at=now - timedelta(hours=2),
        )
        tr_a = Transfer(
            id=uuid.uuid4(),
            business_id=biz_a.id,
            reason="Caller asked for human manager",
            status="completed",
            timestamp=now - timedelta(hours=1),
        )

        # Biz B item
        c_b = Call(
            id=uuid.uuid4(),
            business_id=biz_b.id,
            caller_number="+15559990000",
            started_at=now - timedelta(minutes=30),
            summary="Biz B inbox item",
        )

        session.add_all([c_a, m_a, tr_a, c_b])
        await session.commit()

    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Fetch all inbox items for Biz A
    resp = await client.get("/api/inbox?type=all", headers=headers_a)
    assert resp.status_code == 200
    inbox_data = resp.json()
    assert inbox_data["total"] == 3

    # Most recent first: Transfer (-1h), Message (-2h), Call (-3h)
    items = inbox_data["items"]
    assert items[0]["item_type"] == "transfer"
    assert items[1]["item_type"] == "message"
    assert items[2]["item_type"] == "call"

    # Filter only calls
    call_only = await client.get("/api/inbox?type=call", headers=headers_a)
    assert call_only.status_code == 200
    assert call_only.json()["total"] == 1
    assert call_only.json()["items"][0]["item_type"] == "call"
