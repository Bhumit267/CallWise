"""FastAPI dependency injection: database sessions, auth resolution, and CSRF protection."""

from datetime import datetime, timezone
import hashlib
from typing import AsyncGenerator, Optional, Tuple
import uuid

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from callwise.api.security import hash_token
from callwise.config import settings
from callwise.db.models import Business, Membership, Session as UserSession, User
from callwise.db.session import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional asynchronous database session for API requests."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def extract_session_token(
    request: Request,
    cookie_token: Optional[str] = Cookie(None, alias="callwise_session"),
    auth_header: Optional[str] = Header(None, alias="Authorization"),
) -> Optional[Tuple[str, str]]:
    """
    Extract session token from httpOnly cookie or Authorization Bearer header.
    Returns: (token_str, auth_source) where auth_source is 'cookie' or 'bearer'.
    """
    if auth_header and auth_header.startswith("Bearer "):
        bearer_val = auth_header[7:].strip()
        if bearer_val:
            return bearer_val, "bearer"

    if cookie_token:
        return cookie_token.strip(), "cookie"

    return None


async def get_current_session(
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth_tuple: Optional[Tuple[str, str]] = Depends(extract_session_token),
) -> Tuple[UserSession, str]:
    """Resolve and validate active server-side session."""
    if not auth_tuple:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
        )

    raw_token, auth_source = auth_tuple
    token_hash = hash_token(raw_token)
    now = datetime.now(timezone.utc)

    stmt = (
        select(UserSession)
        .options(
            selectinload(UserSession.user),
            selectinload(UserSession.current_business),
        )
        .where(
            UserSession.session_token_hash == token_hash,
            UserSession.expires_at > now,
        )
    )
    user_session = (await db.execute(stmt)).scalar_one_or_none()

    if not user_session or not user_session.user or not user_session.user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired or is invalid. Please log in again.",
        )

    # Update last active timestamp
    user_session.last_active_at = now
    await db.flush()

    return user_session, auth_source


async def verify_csrf(
    request: Request,
    session_data: Tuple[UserSession, str] = Depends(get_current_session),
    csrf_header: Optional[str] = Header(None, alias="X-CSRF-Token"),
    csrf_cookie: Optional[str] = Cookie(None, alias="callwise_csrf"),
) -> None:
    """
    Enforce CSRF token verification for state-changing HTTP requests authenticated via cookie.
    Bearer-token requests do not require CSRF token since browsers do not send Bearer headers implicitly.
    """
    _, auth_source = session_data

    if auth_source == "cookie" and request.method in ("POST", "PUT", "PATCH", "DELETE"):
        if not csrf_header or not csrf_cookie or csrf_header != csrf_cookie:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token missing or invalid. Please refresh the page.",
            )


async def get_auth_context(
    session_data: Tuple[UserSession, str] = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> Tuple[User, Optional[Business], Optional[str], UserSession]:
    """
    Resolve active authentication context.
    Returns: (user, current_business, role, session_obj)
    """
    user_session, _ = session_data
    user = user_session.user
    current_business = user_session.current_business

    role = None
    if current_business:
        stmt = select(Membership.role).where(
            Membership.user_id == user.id,
            Membership.business_id == current_business.id,
        )
        role = (await db.execute(stmt)).scalar_one_or_none()

    return user, current_business, role, user_session
