"""Tests for Step 2: Auth in the backend (signup, login, sessions, CSRF, rate limits, reset, invites)."""

from datetime import datetime, timezone, timedelta
import uuid
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from callwise.api.main import app
from callwise.api.security import auth_rate_limiter, hash_token
from callwise.db.models import Business, Invite, Membership, PasswordReset, Session as UserSession, User
from callwise.db.session import async_engine, get_async_session


@pytest_asyncio.fixture(autouse=True)
async def cleanup_db_and_limiter():
    """Clear rate limiters and dispose db pool cleanly between tests."""
    auth_rate_limiter.clear_all()
    yield
    auth_rate_limiter.clear_all()
    await async_engine.dispose()


@pytest_asyncio.fixture
async def client():
    """Async test client bound to FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_api_health(client: AsyncClient):
    """Verify health endpoint."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_signup_flow(client: AsyncClient):
    """Verify business registration, owner user creation, and session initialization."""
    email = f"owner_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "business_name": "Apex Dental Studio",
        "business_type": "Dental Care",
        "timezone": "America/New_York",
        "owner_name": "Dr. Sarah Connor",
        "email": email,
        "password": "SecurePassword123!",
    }

    resp = await client.post("/api/auth/signup", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    assert data["user"]["email"] == email
    assert data["user"]["name"] == "Dr. Sarah Connor"
    assert data["current_business"]["name"] == "Apex Dental Studio"
    assert data["current_business"]["role"] == "owner"
    assert len(data["memberships"]) == 1
    assert "csrf_token" in data
    assert resp.cookies.get("callwise_session") is not None
    assert resp.cookies.get("callwise_csrf") is not None

    # Duplicate signup should fail with 400
    dup_resp = await client.post("/api/auth/signup", json=payload)
    assert dup_resp.status_code == 400
    assert "already exists" in dup_resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_success_and_logout(client: AsyncClient):
    """Verify successful login, session retention, and logout."""
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    signup_payload = {
        "business_name": "Smile Clinic",
        "business_type": "Dental",
        "timezone": "America/Chicago",
        "owner_name": "John Doe",
        "email": email,
        "password": "CorrectPassword123!",
    }
    signup_res = await client.post("/api/auth/signup", json=signup_payload)
    assert signup_res.status_code == 201

    # Login
    login_payload = {
        "email": email,
        "password": "CorrectPassword123!",
    }
    login_res = await client.post("/api/auth/login", json=login_payload)
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert login_data["user"]["email"] == email
    assert login_res.cookies.get("callwise_session") is not None

    csrf_token = login_data["csrf_token"]

    # Verify /api/auth/me with session cookie
    me_res = await client.get("/api/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["user"]["email"] == email

    # Logout (requires CSRF token)
    logout_res = await client.post(
        "/api/auth/logout",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert logout_res.status_code == 200

    # /api/auth/me should now fail with 401
    me_after = await client.get("/api/auth/me")
    assert me_after.status_code == 401


@pytest.mark.asyncio
async def test_login_invalid_credentials_and_zero_leakage(client: AsyncClient):
    """Verify 401 on bad password and non-existent email without leaking user existence."""
    email = f"valid_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/api/auth/signup",
        json={
            "business_name": "Clinic A",
            "business_type": "Clinic",
            "timezone": "UTC",
            "owner_name": "Alice",
            "email": email,
            "password": "Password123!",
        },
    )

    # 1. Valid email, wrong password
    bad_pw_res = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "WrongPassword!"},
    )
    assert bad_pw_res.status_code == 401
    assert bad_pw_res.json()["detail"] == "Invalid email or password."

    # 2. Non-existent email
    bad_email_res = await client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "AnyPassword!"},
    )
    assert bad_email_res.status_code == 401
    assert bad_email_res.json()["detail"] == "Invalid email or password."


@pytest.mark.asyncio
async def test_login_rate_limiting_lockout(client: AsyncClient):
    """Verify that multiple failed login attempts trigger 429 lockout."""
    target_email = f"locked_{uuid.uuid4().hex[:8]}@example.com"

    for _ in range(5):
        res = await client.post(
            "/api/auth/login",
            json={"email": target_email, "password": "BadPassword"},
        )
        assert res.status_code == 401

    # 6th attempt triggers 429 Too Many Requests
    locked_res = await client.post(
        "/api/auth/login",
        json={"email": target_email, "password": "BadPassword"},
    )
    assert locked_res.status_code == 429
    assert "Too many failed login attempts" in locked_res.json()["detail"]


@pytest.mark.asyncio
async def test_csrf_protection_enforcement(client: AsyncClient):
    """Verify CSRF token is required for state-changing requests when authenticated via cookie."""
    email = f"csrf_{uuid.uuid4().hex[:8]}@example.com"
    signup_res = await client.post(
        "/api/auth/signup",
        json={
            "business_name": "CSRF Clinic",
            "business_type": "Dental",
            "timezone": "UTC",
            "owner_name": "Bob",
            "email": email,
            "password": "Password123!",
        },
    )
    assert signup_res.status_code == 201

    # Attempt logout without X-CSRF-Token header -> 403 Forbidden
    no_csrf_res = await client.post("/api/auth/logout")
    assert no_csrf_res.status_code == 403
    assert "CSRF token missing or invalid" in no_csrf_res.json()["detail"]

    # Attempt logout with invalid X-CSRF-Token header -> 403 Forbidden
    bad_csrf_res = await client.post(
        "/api/auth/logout",
        headers={"X-CSRF-Token": "invalid_token_value"},
    )
    assert bad_csrf_res.status_code == 403

    # With matching token from cookie -> 200 OK
    csrf_val = signup_res.cookies.get("callwise_csrf")
    good_csrf_res = await client.post(
        "/api/auth/logout",
        headers={"X-CSRF-Token": csrf_val},
    )
    assert good_csrf_res.status_code == 200


@pytest.mark.asyncio
async def test_switch_business_multi_tenant(client: AsyncClient):
    """Verify switching active business context for a multi-tenant user."""
    email = f"multibiz_{uuid.uuid4().hex[:8]}@example.com"
    signup_res = await client.post(
        "/api/auth/signup",
        json={
            "business_name": "Main Office",
            "business_type": "Dental",
            "timezone": "UTC",
            "owner_name": "Carol",
            "email": email,
            "password": "Password123!",
        },
    )
    data = signup_res.json()
    user_id = uuid.UUID(data["user"]["id"])
    biz1_id = uuid.UUID(data["current_business"]["id"])
    csrf_token = data["csrf_token"]

    # Create second business directly and add membership
    biz2_id = uuid.uuid4()
    async with get_async_session() as session:
        biz2 = Business(
            id=biz2_id,
            name="Branch Office",
            business_type="Dental",
            timezone="America/Denver",
            greeting="Hello",
            tone="warm",
        )
        session.add(biz2)
        mem2 = Membership(user_id=user_id, business_id=biz2_id, role="manager")
        session.add(mem2)
        await session.commit()

    # Switch to second business
    switch_res = await client.post(
        "/api/auth/switch-business",
        json={"business_id": str(biz2_id)},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert switch_res.status_code == 200
    switch_data = switch_res.json()
    assert switch_data["current_business"]["id"] == str(biz2_id)
    assert switch_data["current_business"]["role"] == "manager"
    assert len(switch_data["memberships"]) == 2

    # Switch to unauthorized business -> 403 Forbidden
    unauth_biz_id = uuid.uuid4()
    unauth_res = await client.post(
        "/api/auth/switch-business",
        json={"business_id": str(unauth_biz_id)},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert unauth_res.status_code == 403


@pytest.mark.asyncio
async def test_forgot_and_reset_password(client: AsyncClient):
    """Verify single-use hashed token password reset flow."""
    email = f"reset_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/api/auth/signup",
        json={
            "business_name": "Reset Test Clinic",
            "business_type": "Dental",
            "timezone": "UTC",
            "owner_name": "Dan",
            "email": email,
            "password": "OldPassword123!",
        },
    )

    # 1. Request password reset (existing email)
    forgot_res = await client.post("/api/auth/forgot-password", json={"email": email})
    assert forgot_res.status_code == 200
    assert "instructions have been sent" in forgot_res.json()["message"]

    # 2. Request password reset (non-existing email, same message)
    ghost_res = await client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
    assert ghost_res.status_code == 200
    assert "instructions have been sent" in ghost_res.json()["message"]

    # 3. Retrieve raw token from test DB
    async with get_async_session() as session:
        user_stmt = select(User).where(User.email == email)
        u = (await session.execute(user_stmt)).scalar_one()
        reset_stmt = select(PasswordReset).where(PasswordReset.user_id == u.id)
        pr = (await session.execute(reset_stmt)).scalar_one()
        assert pr.used_at is None

    # Simulate reset with invalid token -> 400
    bad_reset = await client.post(
        "/api/auth/reset-password",
        json={"token": "bogus_token", "new_password": "BrandNewPassword123!"},
    )
    assert bad_reset.status_code == 400

    # Simulate reset by generating token whose hash matches pr.token_hash
    # We can inject a known token hash directly
    known_token = f"my_secret_reset_token_{uuid.uuid4().hex}"
    async with get_async_session() as session:
        pr_obj = (await session.execute(reset_stmt)).scalar_one()
        pr_obj.token_hash = hash_token(known_token)
        await session.commit()

    good_reset = await client.post(
        "/api/auth/reset-password",
        json={"token": known_token, "new_password": "BrandNewPassword123!"},
    )
    assert good_reset.status_code == 200
    assert "successfully reset" in good_reset.json()["message"]

    # Reusing the token should now fail (single-use)
    reuse_reset = await client.post(
        "/api/auth/reset-password",
        json={"token": known_token, "new_password": "AnotherPassword123!"},
    )
    assert reuse_reset.status_code == 400

    # User can now log in with new password
    login_res = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "BrandNewPassword123!"},
    )
    assert login_res.status_code == 200


@pytest.mark.asyncio
async def test_accept_team_invite(client: AsyncClient):
    """Verify accepting an invite creates user account and membership."""
    biz_id = uuid.uuid4()
    async with get_async_session() as session:
        biz = Business(
            id=biz_id,
            name="Team Dental Care",
            business_type="Dental",
            timezone="UTC",
            greeting="Hi",
            tone="formal",
        )
        session.add(biz)
        await session.commit()

    raw_token = f"invite_secret_token_{uuid.uuid4().hex}"
    invite_email = f"staff_{uuid.uuid4().hex[:8]}@example.com"
    now = datetime.now(timezone.utc)

    async with get_async_session() as session:
        inv = Invite(
            business_id=biz_id,
            email=invite_email,
            role="staff",
            token_hash=hash_token(raw_token),
            expires_at=now + timedelta(days=2),
        )
        session.add(inv)
        await session.commit()

    # Accept invite
    accept_payload = {
        "token": raw_token,
        "name": "Staff Member Dave",
        "password": "StaffPassword123!",
    }
    accept_res = await client.post("/api/auth/accept-invite", json=accept_payload)
    assert accept_res.status_code == 200
    data = accept_res.json()

    assert data["user"]["email"] == invite_email
    assert data["user"]["name"] == "Staff Member Dave"
    assert data["current_business"]["id"] == str(biz_id)
    assert data["current_business"]["role"] == "staff"
    assert accept_res.cookies.get("callwise_session") is not None

    # Accepting again should fail
    dup_accept = await client.post("/api/auth/accept-invite", json=accept_payload)
    assert dup_accept.status_code == 400
