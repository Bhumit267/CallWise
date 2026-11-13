"""Unit and integration tests for LiveKit WebRTC token generation endpoint."""

from datetime import datetime, timezone
import uuid
import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from callwise.api.main import app
from callwise.api.security import hash_password, hash_token
from callwise.config import settings
from callwise.db.models import Business, Call, Membership, Session as UserSession, User
from callwise.db.session import AsyncSessionLocal


@pytest.mark.asyncio
async def test_webrtc_token_unauthenticated_rejected():
    """Unauthenticated requests must be rejected with 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/onboarding/test-agent/webrtc-token")
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_webrtc_token_generation_success_and_jwt_claims():
    """Authenticated staff should receive a valid LiveKit WebRTC room token and active Call record."""
    user_id = uuid.uuid4()
    biz_id = uuid.uuid4()
    session_id = uuid.uuid4()
    raw_token = f"test-token-{uuid.uuid4().hex}"
    token_hash = hash_token(raw_token)
    csrf_token = f"csrf-{uuid.uuid4().hex}"

    async with AsyncSessionLocal() as db:
        async with db.begin():
            biz = Business(
                id=biz_id,
                name="Apex Dental WebRTC Test",
                business_type="dental clinic",
                timezone="America/New_York",
                greeting="Welcome to Apex Dental live test.",
            )
            user = User(
                id=user_id,
                email=f"tester-{uuid.uuid4().hex[:6]}@example.com",
                name="WebRTC Tester",
                password_hash=hash_password("Password123!"),
                is_active=True,
            )
            membership = Membership(
                id=uuid.uuid4(),
                user_id=user_id,
                business_id=biz_id,
                role="owner",
            )
            user_session = UserSession(
                id=session_id,
                user_id=user_id,
                current_business_id=biz_id,
                session_token_hash=token_hash,
                expires_at=datetime(2028, 1, 1, tzinfo=timezone.utc),
            )
            db.add_all([biz, user, membership, user_session])

    transport = ASGITransport(app=app)
    cookies = {"callwise_session": raw_token, "callwise_csrf": csrf_token}
    headers = {"X-CSRF-Token": csrf_token}

    async with AsyncClient(transport=transport, base_url="http://test", cookies=cookies) as client:
        res = await client.post("/api/onboarding/test-agent/webrtc-token", headers=headers)
        assert res.status_code == 200
        data = res.json()

        assert "token" in data
        assert "server_url" in data
        assert "room_name" in data
        assert "participant_identity" in data
        assert "call_id" in data

        assert str(biz_id) in data["room_name"]
        assert data["participant_identity"].startswith("web-caller-")

        # Decode the LiveKit JWT token to inspect claims
        # LiveKit AccessToken uses settings.livekit_api_secret for HMAC SHA256 signing
        decoded = jwt.decode(
            data["token"],
            settings.livekit_api_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        assert decoded["sub"] == data["participant_identity"]
        assert decoded["name"] == "WebRTC Tester"
        assert "video" in decoded
        grants = decoded["video"]
        assert grants["room"] == data["room_name"]
        assert grants["roomJoin"] is True
        assert grants["canPublish"] is True
        assert grants["canSubscribe"] is True

        # Verify active Call record was created in PostgreSQL
        async with AsyncSessionLocal() as db:
            call_uuid = uuid.UUID(data["call_id"])
            stmt = select(Call).where(Call.id == call_uuid)
            call_row = (await db.execute(stmt)).scalar_one_or_none()
            assert call_row is not None
            assert call_row.business_id == biz_id
            assert call_row.caller_number == "web_browser"
