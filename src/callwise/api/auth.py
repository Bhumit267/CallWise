"""Authentication router: signup, login, logout, sessions, CSRF, password resets, and invites."""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from callwise.api.deps import get_auth_context, get_current_session, get_db, verify_csrf
from callwise.api.security import (
    auth_rate_limiter,
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)
from callwise.config import settings
from callwise.db.models import (
    Business,
    Invite,
    Membership,
    PasswordReset,
    Session as UserSession,
    User,
)
from callwise.providers.email import EmailMessage, get_email_provider

router = APIRouter(prefix="/api/auth", tags=["auth"])


# --- Schemas ---

class SignupRequest(BaseModel):
    business_name: str = Field(min_length=1, max_length=255)
    business_type: str = Field(min_length=1, max_length=100)
    timezone: str = Field(default="UTC", max_length=100)
    owner_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class AcceptInviteRequest(BaseModel):
    token: str = Field(min_length=1)
    name: Optional[str] = Field(default=None, max_length=255)
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class SwitchBusinessRequest(BaseModel):
    business_id: uuid.UUID


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str


class BusinessSummary(BaseModel):
    id: uuid.UUID
    name: str
    business_type: str
    timezone: str
    role: str


class AuthResponse(BaseModel):
    user: UserResponse
    current_business: Optional[BusinessSummary] = None
    memberships: List[BusinessSummary] = []
    csrf_token: str
    session_token: Optional[str] = None


class MessageResponse(BaseModel):
    message: str


# --- Helpers ---

def _set_auth_cookies(response: Response, raw_session_token: str, raw_csrf_token: str) -> None:
    """Set secure httpOnly session cookie and accessible CSRF cookie."""
    max_age = settings.session_expiry_days * 86400
    response.set_cookie(
        key="callwise_session",
        value=raw_session_token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key="callwise_csrf",
        value=raw_csrf_token,
        max_age=max_age,
        httponly=False,  # JS client reads this to send X-CSRF-Token header
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    """Clear session and CSRF cookies."""
    response.delete_cookie(key="callwise_session", path="/")
    response.delete_cookie(key="callwise_csrf", path="/")


async def _build_auth_response(
    db: AsyncSession,
    user: User,
    current_business_id: Optional[uuid.UUID],
    csrf_token: str,
    raw_session_token: Optional[str] = None,
) -> AuthResponse:
    """Construct complete auth response with memberships and active business."""
    stmt = (
        select(Membership)
        .options(selectinload(Membership.business))
        .where(Membership.user_id == user.id)
    )
    memberships = (await db.execute(stmt)).scalars().all()

    mem_summaries: List[BusinessSummary] = []
    curr_summary: Optional[BusinessSummary] = None

    for m in memberships:
        if m.business:
            summary = BusinessSummary(
                id=m.business.id,
                name=m.business.name,
                business_type=m.business.business_type,
                timezone=m.business.timezone,
                role=m.role,
            )
            mem_summaries.append(summary)
            if current_business_id and m.business.id == current_business_id:
                curr_summary = summary

    # Fallback to first business if active not selected or not found
    if not curr_summary and mem_summaries:
        curr_summary = mem_summaries[0]

    return AuthResponse(
        user=UserResponse(id=user.id, email=user.email, name=user.name),
        current_business=curr_summary,
        memberships=mem_summaries,
        csrf_token=csrf_token,
        session_token=raw_session_token,
    )


# --- Endpoints ---

@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    req: SignupRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Register a new business account and owner user."""
    clean_email = req.email.strip().lower()

    # Check if email is already taken
    existing_user = (
        await db.execute(select(User).where(User.email == clean_email))
    ).scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    # 1. Create Business
    business = Business(
        name=req.business_name.strip(),
        business_type=req.business_type.strip(),
        timezone=req.timezone.strip(),
        greeting=f"Thank you for calling {req.business_name.strip()}. How may I help you today?",
        tone="professional and friendly",
        notification_email=clean_email,
        hours={
            "monday": {"open": "09:00", "close": "17:00", "closed": False},
            "tuesday": {"open": "09:00", "close": "17:00", "closed": False},
            "wednesday": {"open": "09:00", "close": "17:00", "closed": False},
            "thursday": {"open": "09:00", "close": "17:00", "closed": False},
            "friday": {"open": "09:00", "close": "17:00", "closed": False},
            "saturday": {"open": None, "close": None, "closed": True},
            "sunday": {"open": None, "close": None, "closed": True},
        },
    )
    db.add(business)
    await db.flush()

    # 2. Create User
    user = User(
        email=clean_email,
        password_hash=hash_password(req.password),
        name=req.owner_name.strip(),
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # 3. Create Owner Membership
    membership = Membership(
        user_id=user.id,
        business_id=business.id,
        role="owner",
    )
    db.add(membership)

    # 4. Create Session
    raw_session_token = generate_token(32)
    raw_csrf_token = generate_token(32)
    now = datetime.now(timezone.utc)

    user_session = UserSession(
        session_token_hash=hash_token(raw_session_token),
        user_id=user.id,
        current_business_id=business.id,
        expires_at=now + timedelta(days=settings.session_expiry_days),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(user_session)
    await db.flush()

    _set_auth_cookies(response, raw_session_token, raw_csrf_token)

    return await _build_auth_response(
        db=db,
        user=user,
        current_business_id=business.id,
        csrf_token=raw_csrf_token,
        raw_session_token=raw_session_token,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    req: LoginRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with email and password with brute-force rate limiting."""
    clean_email = req.email.strip().lower()
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"login:{client_ip}:{clean_email}"

    # Rate limiting & lockout check
    is_limited, retry_after = auth_rate_limiter.is_rate_limited(rate_key)
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Please try again in {retry_after} seconds.",
        )

    # Look up user
    stmt = (
        select(User)
        .options(selectinload(User.memberships))
        .where(User.email == clean_email)
    )
    user = (await db.execute(stmt)).scalar_one_or_none()

    # Constant-time verification & zero email existence leakage
    if not user or not user.is_active or not verify_password(req.password, user.password_hash):
        auth_rate_limiter.record_attempt(rate_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # Clear rate limiter on successful login
    auth_rate_limiter.reset(rate_key)

    # Resolve default business
    default_biz_id = user.memberships[0].business_id if user.memberships else None

    # Create session
    raw_session_token = generate_token(32)
    raw_csrf_token = generate_token(32)
    now = datetime.now(timezone.utc)

    user_session = UserSession(
        session_token_hash=hash_token(raw_session_token),
        user_id=user.id,
        current_business_id=default_biz_id,
        expires_at=now + timedelta(days=settings.session_expiry_days),
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(user_session)
    await db.flush()

    _set_auth_cookies(response, raw_session_token, raw_csrf_token)

    return await _build_auth_response(
        db=db,
        user=user,
        current_business_id=default_biz_id,
        csrf_token=raw_csrf_token,
        raw_session_token=raw_session_token,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    session_data: tuple = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(verify_csrf),
):
    """Terminate the active session and remove auth cookies."""
    user_session, _ = session_data
    await db.delete(user_session)
    await db.commit()

    _clear_auth_cookies(response)
    return MessageResponse(message="Logged out successfully.")


@router.get("/me", response_model=AuthResponse)
async def get_me(
    session_data: tuple = Depends(get_current_session),
    csrf_cookie: Optional[str] = Cookie(None, alias="callwise_csrf"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve profile of the currently signed-in user and active business."""
    user_session, _ = session_data
    csrf_token = csrf_cookie or generate_token(32)

    return await _build_auth_response(
        db=db,
        user=user_session.user,
        current_business_id=user_session.current_business_id,
        csrf_token=csrf_token,
    )


@router.post("/switch-business", response_model=AuthResponse)
async def switch_business(
    req: SwitchBusinessRequest,
    session_data: tuple = Depends(get_current_session),
    csrf_cookie: Optional[str] = Cookie(None, alias="callwise_csrf"),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(verify_csrf),
):
    """Switch active tenant business context for multi-business users."""
    user_session, _ = session_data
    user = user_session.user

    # Verify membership
    stmt = select(Membership).where(
        Membership.user_id == user.id,
        Membership.business_id == req.business_id,
    )
    membership = (await db.execute(stmt)).scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this business.",
        )

    user_session.current_business_id = req.business_id
    await db.flush()

    csrf_token = csrf_cookie or generate_token(32)

    return await _build_auth_response(
        db=db,
        user=user,
        current_business_id=req.business_id,
        csrf_token=csrf_token,
    )


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    req: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Request a password reset email using single-use hashed token."""
    clean_email = req.email.strip().lower()
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"forgot_pw:{client_ip}"

    # Rate limiting (max 10 requests per 15 min per IP)
    is_limited, retry_after = auth_rate_limiter.is_rate_limited(rate_key, max_attempts=10)
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many password reset requests. Please try again in {retry_after} seconds.",
        )

    auth_rate_limiter.record_attempt(rate_key)

    # Look up user
    user = (
        await db.execute(select(User).where(User.email == clean_email, User.is_active == True))
    ).scalar_one_or_none()

    if user:
        raw_token = generate_token(32)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=1)

        reset_record = PasswordReset(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=expires_at,
        )
        db.add(reset_record)
        await db.flush()

        reset_url = f"{settings.app_url}/reset-password?token={raw_token}"
        msg = EmailMessage(
            to=user.email,
            subject="Reset Your Callwise Password",
            body_text=(
                f"Hello {user.name},\n\n"
                f"We received a request to reset your password for your Callwise account.\n"
                f"Click the link below to set a new password:\n{reset_url}\n\n"
                f"This link will expire in 1 hour. If you did not request this, you can ignore this email."
            ),
        )
        try:
            email_provider = get_email_provider()
            await email_provider.send_email(msg)
        except Exception:
            pass  # Do not leak failure to user

    # Security requirement: Never leak whether an email exists in reset flows
    return MessageResponse(
        message="If that email address is registered, password reset instructions have been sent."
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    req: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reset password using a verified, single-use token."""
    t_hash = hash_token(req.token.strip())
    now = datetime.now(timezone.utc)

    stmt = (
        select(PasswordReset)
        .options(selectinload(PasswordReset.user))
        .where(
            PasswordReset.token_hash == t_hash,
            PasswordReset.used_at.is_(None),
            PasswordReset.expires_at > now,
        )
    )
    reset_record = (await db.execute(stmt)).scalar_one_or_none()

    if not reset_record or not reset_record.user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset link is invalid or has expired.",
        )

    # Update user password
    user = reset_record.user
    user.password_hash = hash_password(req.new_password)
    reset_record.used_at = now

    # Invalidate all existing sessions for this user for security
    await db.execute(delete(UserSession).where(UserSession.user_id == user.id))
    await db.commit()

    return MessageResponse(
        message="Your password has been successfully reset. You may now log in with your new password."
    )


@router.post("/accept-invite", response_model=AuthResponse)
async def accept_invite(
    req: AcceptInviteRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Accept a team invite and establish membership in the business."""
    t_hash = hash_token(req.token.strip())
    now = datetime.now(timezone.utc)

    stmt = select(Invite).where(
        Invite.token_hash == t_hash,
        Invite.accepted_at.is_(None),
        Invite.expires_at > now,
    )
    invite = (await db.execute(stmt)).scalar_one_or_none()

    if not invite:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invite link is invalid or has expired.",
        )

    # Check if user already exists
    user = (
        await db.execute(select(User).where(User.email == invite.email))
    ).scalar_one_or_none()

    if not user:
        if not req.name or not req.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Name and password are required to create your account.",
            )
        user = User(
            email=invite.email,
            name=req.name.strip(),
            password_hash=hash_password(req.password),
            is_active=True,
        )
        db.add(user)
        await db.flush()

    # Add or update membership
    existing_mem = (
        await db.execute(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.business_id == invite.business_id,
            )
        )
    ).scalar_one_or_none()

    if existing_mem:
        existing_mem.role = invite.role
    else:
        membership = Membership(
            user_id=user.id,
            business_id=invite.business_id,
            role=invite.role,
        )
        db.add(membership)

    invite.accepted_at = now

    # Log in user immediately
    raw_session_token = generate_token(32)
    raw_csrf_token = generate_token(32)

    user_session = UserSession(
        session_token_hash=hash_token(raw_session_token),
        user_id=user.id,
        current_business_id=invite.business_id,
        expires_at=now + timedelta(days=settings.session_expiry_days),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(user_session)
    await db.flush()

    _set_auth_cookies(response, raw_session_token, raw_csrf_token)

    return await _build_auth_response(
        db=db,
        user=user,
        current_business_id=invite.business_id,
        csrf_token=raw_csrf_token,
        raw_session_token=raw_session_token,
    )


@router.get("/csrf")
async def get_csrf_token(
    response: Response,
    csrf_cookie: Optional[str] = Cookie(None, alias="callwise_csrf"),
):
    """Retrieve or generate CSRF token cookie."""
    token = csrf_cookie or generate_token(32)
    response.set_cookie(
        key="callwise_csrf",
        value=token,
        max_age=settings.session_expiry_days * 86400,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return {"csrf_token": token}
