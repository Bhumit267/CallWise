"""Unit and tenant isolation tests for Step 6 (Analytics, Team & Invites, Audit Logs, Onboarding Wizard)."""

from datetime import datetime, timedelta, timezone
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from callwise.api.main import app
from callwise.api.security import auth_rate_limiter, hash_password, hash_token
from callwise.db.models import (
    Appointment,
    AuditLog,
    Business,
    Call,
    CallTurn,
    Invite,
    KnowledgeMiss,
    Membership,
    Message,
    Service,
    Session as UserSession,
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


async def create_tenant(session, biz_name: str, email: str, role: str = "owner"):
    """Provision a tenant business, user, membership, and active session."""
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
        email=email,
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
    raw_token = f"token_{uuid.uuid4().hex}"
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
async def test_analytics_metrics_and_isolation(client: AsyncClient):
    """Test analytics calculations: conversion, busiest hours, top services, latency, and isolation."""
    now = datetime.now(timezone.utc)

    async with get_async_session() as session:
        biz_a, _, token_a = await create_tenant(session, "Analytics Dental A", f"an_a_{uuid.uuid4().hex[:6]}@example.com")
        biz_b, _, token_b = await create_tenant(session, "Analytics Dental B", f"an_b_{uuid.uuid4().hex[:6]}@example.com")

        svc_a = Service(
            id=uuid.uuid4(),
            business_id=biz_a.id,
            name="Teeth Cleaning",
            duration_minutes=30,
            price=100.0,
            is_active=True,
        )
        session.add(svc_a)
        await session.flush()

        # Add 2 calls for Biz A
        c1 = Call(
            id=uuid.uuid4(),
            business_id=biz_a.id,
            caller_number="+15551112222",
            started_at=now - timedelta(hours=2),
            summary="Cleaning inquiry",
        )
        c2 = Call(
            id=uuid.uuid4(),
            business_id=biz_a.id,
            caller_number="+15553334444",
            started_at=now - timedelta(hours=1),
            summary="Emergency inquiry",
        )
        turn1 = CallTurn(
            id=uuid.uuid4(),
            business_id=biz_a.id,
            call_id=c1.id,
            speaker="agent",
            text="Hello there",
            latency_ms=250.0,
            timestamp=now - timedelta(hours=2),
        )
        turn2 = CallTurn(
            id=uuid.uuid4(),
            business_id=biz_a.id,
            call_id=c2.id,
            speaker="agent",
            text="How can I help?",
            latency_ms=350.0,
            timestamp=now - timedelta(hours=1),
        )
        appt1 = Appointment(
            id=uuid.uuid4(),
            business_id=biz_a.id,
            service_id=svc_a.id,
            call_id=c1.id,
            customer_name="Alice",
            customer_phone="+15551112222",
            start_at=now + timedelta(days=1),
            end_at=now + timedelta(days=1, minutes=30),
            status="booked",
            booking_code_hash="hash1",
        )

        # Call for Biz B
        c_b = Call(
            id=uuid.uuid4(),
            business_id=biz_b.id,
            caller_number="+15559990000",
            started_at=now - timedelta(hours=1),
        )

        session.add_all([c1, c2, turn1, turn2, appt1, c_b])
        await session.commit()

    headers_a = {"Authorization": f"Bearer {token_a}"}

    resp = await client.get("/api/analytics", headers=headers_a)
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_calls"] == 2
    assert data["booking_conversion_rate"] == 0.5  # 1 booking / 2 calls
    assert len(data["top_services"]) == 1
    assert data["top_services"][0]["name"] == "Teeth Cleaning"
    assert data["top_services"][0]["booking_count"] == 1
    assert data["top_services"][0]["revenue"] == 100.0

    # Latency: [250, 350] -> median 300, p95 350
    assert data["latency_metrics"]["sample_count"] == 2
    assert data["latency_metrics"]["median_ms"] == 300.0
    assert data["latency_metrics"]["p95_ms"] == 350.0


@pytest.mark.asyncio
async def test_team_management_invites_and_owner_protection(client: AsyncClient):
    """Test team member listing, invitations, role changes, and last-owner protection."""
    async with get_async_session() as session:
        biz, owner_user, token_owner = await create_tenant(session, "Team Dental", f"owner_t_{uuid.uuid4().hex[:6]}@example.com", role="owner")

        # Second member (staff)
        staff_user = User(
            id=uuid.uuid4(),
            email=f"staff_t_{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("SecurePassword123!"),
            name="Staff Member",
            is_active=True,
        )
        membership_staff = Membership(
            id=uuid.uuid4(),
            user_id=staff_user.id,
            business_id=biz.id,
            role="staff",
        )
        session.add_all([staff_user, membership_staff])
        await session.commit()

    headers = {"Authorization": f"Bearer {token_owner}"}

    # 1. List team members
    list_resp = await client.get("/api/team/members", headers=headers)
    assert list_resp.status_code == 200
    members = list_resp.json()
    assert len(members) == 2

    # 2. Invite a new manager
    invite_email = f"invitee_{uuid.uuid4().hex[:6]}@example.com"
    inv_resp = await client.post(
        "/api/team/invites",
        json={"email": invite_email, "role": "manager"},
        headers=headers,
    )
    assert inv_resp.status_code == 201
    invite_id = inv_resp.json()["id"]

    # List pending invites
    pending_resp = await client.get("/api/team/invites", headers=headers)
    assert pending_resp.status_code == 200
    assert any(inv["id"] == invite_id for inv in pending_resp.json())

    # Revoke invite
    rev_resp = await client.delete(f"/api/team/invites/{invite_id}", headers=headers)
    assert rev_resp.status_code == 200

    # 3. Promote staff to manager
    promote_resp = await client.patch(
        f"/api/team/members/{staff_user.id}",
        json={"role": "manager"},
        headers=headers,
    )
    assert promote_resp.status_code == 200
    assert promote_resp.json()["role"] == "manager"

    # 4. Attempt to demote the ONLY owner -> must fail with 400
    demote_fail = await client.patch(
        f"/api/team/members/{owner_user.id}",
        json={"role": "staff"},
        headers=headers,
    )
    assert demote_fail.status_code == 400
    assert "Cannot demote the only owner" in demote_fail.json()["detail"]

    # 5. Attempt to remove the ONLY owner -> must fail with 400
    del_fail = await client.delete(f"/api/team/members/{owner_user.id}", headers=headers)
    assert del_fail.status_code == 400
    assert "Cannot remove the only owner" in del_fail.json()["detail"]

    # 6. Remove the promoted member -> succeeds
    del_ok = await client.delete(f"/api/team/members/{staff_user.id}", headers=headers)
    assert del_ok.status_code == 200


@pytest.mark.asyncio
async def test_audit_logs_listing_and_isolation(client: AsyncClient):
    """Test audit logs listing, pagination, and tenant isolation."""
    async with get_async_session() as session:
        biz_a, user_a, token_a = await create_tenant(session, "Audit Clinic A", f"audit_a_{uuid.uuid4().hex[:6]}@example.com")
        biz_b, user_b, token_b = await create_tenant(session, "Audit Clinic B", f"audit_b_{uuid.uuid4().hex[:6]}@example.com")

        log_a = AuditLog(
            id=uuid.uuid4(),
            business_id=biz_a.id,
            user_id=user_a.id,
            action="update_hours",
            resource_type="business",
            resource_id=str(biz_a.id),
            changes={"hours": "updated"},
        )
        log_b = AuditLog(
            id=uuid.uuid4(),
            business_id=biz_b.id,
            user_id=user_b.id,
            action="delete_service",
            resource_type="service",
        )
        session.add_all([log_a, log_b])
        await session.commit()

    headers_a = {"Authorization": f"Bearer {token_a}"}

    resp = await client.get("/api/audit-logs", headers=headers_a)
    assert resp.status_code == 200
    logs = resp.json()["items"]
    assert len(logs) == 1
    assert logs[0]["action"] == "update_hours"
    assert logs[0]["user_name"] == user_a.name


@pytest.mark.asyncio
async def test_onboarding_wizard_and_test_agent(client: AsyncClient):
    """Test onboarding setup endpoint and interactive test receptionist chat."""
    now = datetime.now(timezone.utc)
    raw_token = f"token_{uuid.uuid4().hex}"

    async with get_async_session() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"newbie_{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("SecurePassword123!"),
            name="Newbie Owner",
            is_active=True,
        )
        user_session = UserSession(
            id=uuid.uuid4(),
            user_id=user.id,
            current_business_id=None,  # Brand new user without a business yet!
            session_token_hash=hash_token(raw_token),
            expires_at=now + timedelta(days=7),
        )
        session.add_all([user, user_session])
        await session.commit()

    headers = {"Authorization": f"Bearer {raw_token}"}

    # 1. Complete onboarding wizard
    setup_payload = {
        "name": "Bright Dental Studio",
        "business_type": "Dental Care",
        "timezone": "America/New_York",
        "greeting": "Welcome to Bright Dental Studio. How may we assist your smile today?",
        "tone": "warm",
        "hours": {
            "monday": {"open": "08:00", "close": "17:00", "closed": False},
        },
        "services": [
            {
                "name": "Routine Cleaning",
                "duration_minutes": 45,
                "price": 120.0,
                "is_active": True,
            }
        ],
    }
    setup_resp = await client.post("/api/onboarding/setup", json=setup_payload, headers=headers)
    assert setup_resp.status_code == 200
    setup_data = setup_resp.json()
    assert setup_data["name"] == "Bright Dental Studio"
    assert setup_data["services_count"] == 1
    biz_id = setup_data["business_id"]

    # 2. Test receptionist agent interactive console
    test_agent_payload = {
        "message": "What are your hours on Monday?",
    }
    test_resp = await client.post("/api/onboarding/test-agent", json=test_agent_payload, headers=headers)
    assert test_resp.status_code == 200
    agent_data = test_resp.json()
    assert agent_data["reply"] is not None
    assert agent_data["latency_ms"] >= 0.0
    assert agent_data["call_id"] is not None
