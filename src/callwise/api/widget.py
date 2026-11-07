"""FastAPI router for public embeddable website chat widget."""

from datetime import datetime, timezone
import html
import logging
import re
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from callwise.agent.text_agent import TextAgent
from callwise.api.deps import get_db, get_tenant_db
from callwise.api.permissions import require_manager, require_owner, require_staff
from callwise.api.security import RateLimiter, generate_token
from callwise.calls.usage import check_usage_limits_async
from callwise.db.models import (
    BlocklistEntry,
    Business,
    Call,
    Contact,
    FollowUp,
    Session as UserSession,
    User,
    WidgetSettings,
)
from callwise.db.session import get_async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/widget", tags=["Website Chat Widget"])

# Dedicated rate limiter for public widget chat
widget_rate_limiter = RateLimiter()


# ============================================================================
# Schemas
# ============================================================================

class WidgetConfigResponse(BaseModel):
    business_id: uuid.UUID
    business_name: str
    primary_color: str
    greeting_message: str
    ask_lead_capture: bool
    require_lead_name: bool
    allow_booking: bool


class WidgetSettingsUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    allowed_origins: Optional[str] = None
    primary_color: Optional[str] = None
    greeting_message: Optional[str] = None
    ask_lead_capture: Optional[bool] = None
    require_lead_name: Optional[bool] = None
    allow_booking: Optional[bool] = None
    rate_limit_rpm: Optional[int] = Field(None, ge=1, le=120)
    max_turns_per_session: Optional[int] = Field(None, ge=5, le=100)


class WidgetSettingsResponse(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    public_key: str
    is_enabled: bool
    allowed_origins: str
    primary_color: str
    greeting_message: str
    ask_lead_capture: bool
    require_lead_name: bool
    allow_booking: bool
    rate_limit_rpm: int
    max_turns_per_session: int
    created_at: datetime
    updated_at: datetime


class LeadCaptureRequest(BaseModel):
    public_key: str
    call_id: Optional[uuid.UUID] = None
    name: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)


class WidgetChatRequest(BaseModel):
    public_key: str
    message: str = Field(..., min_length=1, max_length=1000, description="Visitor query, capped at 1,000 characters")
    call_id: Optional[uuid.UUID] = Field(None, description="Active widget chat session UUID")
    visitor_name: Optional[str] = None
    visitor_email: Optional[EmailStr] = None
    visitor_phone: Optional[str] = None


class WidgetChatResponse(BaseModel):
    call_id: uuid.UUID
    reply: str
    latency_ms: float
    turn_number: int


# ============================================================================
# Helper Functions
# ============================================================================

def sanitize_text(text: str) -> str:
    """Escape HTML to prevent XSS injection in widget responses."""
    return html.escape(text.strip())


def is_origin_allowed(origin_header: Optional[str], allowed_origins_str: str) -> bool:
    """Verify incoming Origin or Referer header matches allowed origins list."""
    if not allowed_origins_str or allowed_origins_str.strip() == "*":
        return True
    if not origin_header:
        return True  # Direct embedding or test clients

    origin = origin_header.strip().lower()
    allowed_list = [o.strip().lower() for o in allowed_origins_str.split(",") if o.strip()]

    for allowed in allowed_list:
        if allowed == "*" or origin == allowed or origin.endswith("." + allowed.lstrip(".")):
            return True
    return False


async def get_widget_by_public_key(session: AsyncSession, public_key: str) -> Optional[WidgetSettings]:
    """Retrieve WidgetSettings and related Business given a public key."""
    stmt = (
        select(WidgetSettings)
        .where(WidgetSettings.public_key == public_key)
        .options(selectinload(WidgetSettings.business))
    )
    return (await session.execute(stmt)).scalar_one_or_none()


# ============================================================================
# Public Endpoints (Unauthenticated / Public Key Authenticated)
# ============================================================================

@router.get("/config/{public_key}", response_model=WidgetConfigResponse)
async def get_public_widget_config(
    public_key: str,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> WidgetConfigResponse:
    """Fetch public configuration and styling for the embeddable chat widget."""
    widget = await get_widget_by_public_key(db, public_key)
    if not widget or not widget.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Widget not found or disabled.",
        )

    # Origin validation
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not is_origin_allowed(origin, widget.allowed_origins):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Domain origin is not authorized to embed this widget.",
        )

    # Allow embedding in iframe across authorized origins
    response.headers["X-Frame-Options"] = "ALLOWALL"
    response.headers["Content-Security-Policy"] = "frame-ancestors *"

    return WidgetConfigResponse(
        business_id=widget.business.id,
        business_name=widget.business.name,
        primary_color=widget.primary_color,
        greeting_message=sanitize_text(widget.greeting_message),
        ask_lead_capture=widget.ask_lead_capture,
        require_lead_name=widget.require_lead_name,
        allow_booking=widget.allow_booking,
    )


@router.post("/chat", response_model=WidgetChatResponse)
async def public_widget_chat(
    payload: WidgetChatRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> WidgetChatResponse:
    """
    Public conversational endpoint for the website widget.
    Enforces origin checks, rate limits per IP/session, cap turns, anti-injection, and lead capture.
    """
    client_ip = request.client.host if request.client else "unknown"

    # 1. Validate public key
    widget = await get_widget_by_public_key(db, payload.public_key)
    if not widget or not widget.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or disabled widget public key.",
        )

    business = widget.business

    # 2. Check tenant IP blocklist
    block_stmt = select(BlocklistEntry).where(
        BlocklistEntry.business_id == business.id,
        BlocklistEntry.identifier_type == "ip",
        BlocklistEntry.identifier_value == client_ip,
    )
    blocked = (await db.execute(block_stmt)).scalar_one_or_none()
    if blocked:
        now_utc = datetime.now(timezone.utc)
        if blocked.blocked_until is None or blocked.blocked_until > now_utc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access temporarily denied.",
            )

    # 3. Origin check
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not is_origin_allowed(origin, widget.allowed_origins):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized origin.",
        )

    # 4. Rate Limiting per IP
    ip_key = f"widget_ip_{widget.business_id}_{client_ip}"
    is_limited, retry_after = widget_rate_limiter.is_rate_limited(
        key=ip_key,
        max_attempts=widget.rate_limit_rpm,
        window_seconds=60,
        lockout_seconds=60,
    )
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Please wait {retry_after}s.",
        )
    widget_rate_limiter.record_attempt(ip_key)

    call_id = payload.call_id or uuid.uuid4()

    # 5. Get or create Call record
    call_stmt = select(Call).where(Call.id == call_id, Call.business_id == business.id)
    call_record = (await db.execute(call_stmt)).scalar_one_or_none()
    if not call_record:
        call_record = Call(
            id=call_id,
            business_id=business.id,
            caller_number=f"widget_{client_ip}",
            summary="Website chat widget session",
        )
        db.add(call_record)
        await db.flush()

    # 6. Check session turn cap
    from callwise.db.models import CallTurn
    turn_count_stmt = select(CallTurn).where(CallTurn.call_id == call_id)
    existing_turns = (await db.execute(turn_count_stmt)).scalars().all()
    if len(existing_turns) >= (widget.max_turns_per_session * 2):
        return WidgetChatResponse(
            call_id=call_id,
            reply="This chat conversation has reached its length limit. Please call our office or submit a message for further assistance.",
            latency_ms=10.0,
            turn_number=len(existing_turns),
        )

    # 7. Optional Lead Capture update
    if payload.visitor_email or payload.visitor_phone or payload.visitor_name:
        contact_stmt = select(Contact).where(
            Contact.business_id == business.id,
            (Contact.email == str(payload.visitor_email)) if payload.visitor_email else (Contact.phone == payload.visitor_phone)
        )
        contact = (await db.execute(contact_stmt)).scalar_one_or_none()
        if not contact:
            contact = Contact(
                id=uuid.uuid4(),
                business_id=business.id,
                name=payload.visitor_name or "Website Visitor",
                email=str(payload.visitor_email) if payload.visitor_email else None,
                phone=payload.visitor_phone,
            )
            db.add(contact)
            await db.flush()

        call_record.contact_id = contact.id
        await db.flush()

    # 8. Run TextAgent
    import time
    t0 = time.perf_counter()
    agent = TextAgent(business=business, call_id=call_id)
    clean_message = payload.message.strip()

    reply = await agent.ask(clean_message, session_type="widget")
    latency_ms = (time.perf_counter() - t0) * 1000.0

    # Ensure response headers permit iframe display
    response.headers["X-Frame-Options"] = "ALLOWALL"

    return WidgetChatResponse(
        call_id=call_id,
        reply=sanitize_text(reply),
        latency_ms=round(latency_ms, 2),
        turn_number=len(existing_turns) + 2,
    )


@router.post("/lead", status_code=status.HTTP_201_CREATED)
async def public_widget_lead_capture(
    payload: LeadCaptureRequest,
    db: AsyncSession = Depends(get_db),
):
    """Save visitor contact info and create a follow-up task for business staff."""
    widget = await get_widget_by_public_key(db, payload.public_key)
    if not widget or not widget.is_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")

    business = widget.business
    contact = None

    if payload.email or payload.phone:
        contact_stmt = select(Contact).where(
            Contact.business_id == business.id,
            (Contact.email == str(payload.email)) if payload.email else (Contact.phone == payload.phone)
        )
        contact = (await db.execute(contact_stmt)).scalar_one_or_none()

    if not contact:
        contact = Contact(
            id=uuid.uuid4(),
            business_id=business.id,
            name=payload.name or "Website Visitor",
            email=str(payload.email) if payload.email else None,
            phone=payload.phone,
        )
        db.add(contact)
        await db.flush()

    # Create FollowUp actionable task
    follow_up = FollowUp(
        id=uuid.uuid4(),
        business_id=business.id,
        contact_id=contact.id,
        title=f"Website Lead: {contact.name}",
        description=f"Captured from website chat widget. Email: {contact.email or 'N/A'}, Phone: {contact.phone or 'N/A'}",
        source="widget_lead_capture",
        source_id=str(payload.call_id) if payload.call_id else None,
        status="open",
    )
    db.add(follow_up)
    await db.commit()

    return {"status": "success", "contact_id": str(contact.id)}


# ============================================================================
# Authenticated Dashboard Management Endpoints
# ============================================================================

@router.get("/settings", response_model=WidgetSettingsResponse)
async def get_dashboard_widget_settings(
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> WidgetSettingsResponse:
    """Retrieve widget configuration for the dashboard settings page."""
    _, business, _, _ = auth_ctx
    stmt = select(WidgetSettings).where(WidgetSettings.business_id == business.id)
    widget = (await db.execute(stmt)).scalar_one_or_none()

    if not widget:
        widget = WidgetSettings(
            id=uuid.uuid4(),
            business_id=business.id,
            public_key=f"cw_live_{generate_token(16)}",
            is_enabled=True,
            allowed_origins="*",
            primary_color="#2563EB",
            greeting_message=f"Hi! How can {business.name} help you today?",
            ask_lead_capture=True,
            require_lead_name=False,
            allow_booking=True,
        )
        db.add(widget)
        await db.commit()

    return widget


@router.patch("/settings", response_model=WidgetSettingsResponse)
async def update_dashboard_widget_settings(
    payload: WidgetSettingsUpdate,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> WidgetSettingsResponse:
    """Update widget configuration (colors, allowed origins, greetings, lead capture)."""
    _, business, _, _ = auth_ctx
    stmt = select(WidgetSettings).where(WidgetSettings.business_id == business.id)
    widget = (await db.execute(stmt)).scalar_one_or_none()

    if not widget:
        widget = WidgetSettings(
            id=uuid.uuid4(),
            business_id=business.id,
            public_key=f"cw_live_{generate_token(16)}",
        )
        db.add(widget)

    if payload.is_enabled is not None:
        widget.is_enabled = payload.is_enabled
    if payload.allowed_origins is not None:
        widget.allowed_origins = payload.allowed_origins.strip()
    if payload.primary_color is not None:
        widget.primary_color = payload.primary_color.strip()
    if payload.greeting_message is not None:
        widget.greeting_message = payload.greeting_message.strip()
    if payload.ask_lead_capture is not None:
        widget.ask_lead_capture = payload.ask_lead_capture
    if payload.require_lead_name is not None:
        widget.require_lead_name = payload.require_lead_name
    if payload.allow_booking is not None:
        widget.allow_booking = payload.allow_booking
    if payload.rate_limit_rpm is not None:
        widget.rate_limit_rpm = payload.rate_limit_rpm
    if payload.max_turns_per_session is not None:
        widget.max_turns_per_session = payload.max_turns_per_session

    widget.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return widget


@router.post("/settings/regenerate-key", response_model=WidgetSettingsResponse)
async def regenerate_widget_public_key(
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_owner),
    db: AsyncSession = Depends(get_tenant_db),
) -> WidgetSettingsResponse:
    """Regenerate widget public key (invalidates previous embed snippets)."""
    _, business, _, _ = auth_ctx
    stmt = select(WidgetSettings).where(WidgetSettings.business_id == business.id)
    widget = (await db.execute(stmt)).scalar_one_or_none()
    if not widget:
        raise HTTPException(status_code=404, detail="Widget settings not found.")

    widget.public_key = f"cw_live_{generate_token(16)}"
    widget.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return widget

