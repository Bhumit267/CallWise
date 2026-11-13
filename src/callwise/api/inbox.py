"""Unified Inbox API router: chronological timeline of calls, messages, transfers, and appointments."""

from datetime import datetime
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from callwise.api.deps import get_tenant_db
from callwise.api.permissions import require_staff
from callwise.api.schemas import (
    InboxItem,
    PaginatedResponse,
    mask_phone_number,
)
from callwise.db.models import (
    Appointment,
    Business,
    Call,
    Contact,
    Message,
    Service,
    Session as UserSession,
    Transfer,
    User,
)

router = APIRouter(prefix="/inbox", tags=["Inbox"])


@router.get("", response_model=PaginatedResponse[InboxItem])
async def get_unified_inbox(
    item_type: Optional[str] = Query("all", alias="type", description="Filter by event type: all, call, message, transfer, appointment"),
    search: Optional[str] = Query(None, description="Search caller/customer or description/summary"),
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> PaginatedResponse[InboxItem]:
    """Retrieve unified chronological activity timeline for the business."""
    _, business, _, _ = auth_ctx

    type_choice = (item_type or "all").lower().strip()
    search_term = f"%{search.strip()}%" if search and search.strip() else None

    # Fetch window large enough to merge across types or fetch directly if single type
    merged_items: List[InboxItem] = []

    # 1. Calls
    if type_choice in ("all", "call"):
        call_conds = [Call.business_id == business.id]
        if search_term:
            call_conds.append(
                or_(
                    Call.caller_number.ilike(search_term),
                    Call.summary.ilike(search_term),
                )
            )
        call_stmt = (
            select(Call)
            .options(selectinload(Call.contact))
            .where(*call_conds)
            .order_by(Call.started_at.desc())
            .limit(page * page_size * 2)
        )
        calls = (await db.execute(call_stmt)).scalars().all()
        for c in calls:
            masked = mask_phone_number(c.caller_number) or "Unknown"
            merged_items.append(
                InboxItem(
                    id=f"call_{c.id}",
                    item_type="call",
                    timestamp=c.started_at,
                    title=f"Call from {masked}",
                    description=c.summary or "Inbound phone call",
                    contact_id=c.contact_id,
                    contact_name=c.contact.name if c.contact else None,
                    phone=masked,
                    meta={
                        "call_id": str(c.id),
                        "duration_seconds": c.duration_seconds,
                        "intent": c.intent,
                        "urgency": c.urgency or "normal",
                        "sentiment": c.sentiment or "neutral",
                        "tags": c.tags or [],
                    },
                )
            )

    # 2. Messages
    if type_choice in ("all", "message"):
        msg_conds = [Message.business_id == business.id]
        if search_term:
            msg_conds.append(
                or_(
                    Message.caller_name.ilike(search_term),
                    Message.callback_number.ilike(search_term),
                    Message.reason.ilike(search_term),
                )
            )
        msg_stmt = (
            select(Message)
            .options(selectinload(Message.contact))
            .where(*msg_conds)
            .order_by(Message.created_at.desc())
            .limit(page * page_size * 2)
        )
        msgs = (await db.execute(msg_stmt)).scalars().all()
        for m in msgs:
            masked = mask_phone_number(m.callback_number) or m.callback_number
            merged_items.append(
                InboxItem(
                    id=f"message_{m.id}",
                    item_type="message",
                    timestamp=m.created_at,
                    title=f"Message from {m.caller_name}",
                    description=m.reason,
                    contact_id=m.contact_id,
                    contact_name=m.contact.name if m.contact else m.caller_name,
                    phone=masked,
                    meta={
                        "message_id": str(m.id),
                        "call_id": str(m.call_id) if m.call_id else None,
                    },
                )
            )

    # 3. Transfers
    if type_choice in ("all", "transfer"):
        tr_conds = [Transfer.business_id == business.id]
        if search_term:
            tr_conds.append(
                or_(
                    Transfer.reason.ilike(search_term),
                    Transfer.status.ilike(search_term),
                )
            )
        tr_stmt = (
            select(Transfer)
            .where(*tr_conds)
            .order_by(Transfer.timestamp.desc())
            .limit(page * page_size * 2)
        )
        transfers = (await db.execute(tr_stmt)).scalars().all()
        for tr in transfers:
            merged_items.append(
                InboxItem(
                    id=f"transfer_{tr.id}",
                    item_type="transfer",
                    timestamp=tr.timestamp,
                    title=f"Call Transfer ({tr.status.capitalize()})",
                    description=tr.reason,
                    contact_id=None,
                    contact_name=None,
                    phone=None,
                    meta={
                        "transfer_id": str(tr.id),
                        "call_id": str(tr.call_id) if tr.call_id else None,
                        "status": tr.status,
                    },
                )
            )

    # 4. Appointments
    if type_choice in ("all", "appointment"):
        app_conds = [Appointment.business_id == business.id]
        if search_term:
            app_conds.append(
                or_(
                    Appointment.customer_name.ilike(search_term),
                    Appointment.customer_phone.ilike(search_term),
                    Appointment.service.has(Service.name.ilike(search_term)),
                )
            )
        app_stmt = (
            select(Appointment)
            .options(selectinload(Appointment.service), selectinload(Appointment.contact))
            .where(*app_conds)
            .order_by(Appointment.created_at.desc())
            .limit(page * page_size * 2)
        )
        appointments = (await db.execute(app_stmt)).scalars().all()
        for a in appointments:
            masked = mask_phone_number(a.customer_phone) or a.customer_phone
            svc_name = a.service.name if a.service else "Service"
            merged_items.append(
                InboxItem(
                    id=f"appointment_{a.id}",
                    item_type="appointment",
                    timestamp=a.created_at,
                    title=f"Appointment Booked: {svc_name}",
                    description=f"{a.customer_name} - {a.start_at.strftime('%b %d, %Y %I:%M %p UTC')}",
                    contact_id=a.contact_id,
                    contact_name=a.contact.name if a.contact else a.customer_name,
                    phone=masked,
                    meta={
                        "appointment_id": str(a.id),
                        "service_name": svc_name,
                        "status": a.status,
                        "start_at": a.start_at.isoformat(),
                        "end_at": a.end_at.isoformat(),
                    },
                )
            )

    # Sort descending by timestamp
    merged_items.sort(key=lambda x: x.timestamp, reverse=True)
    total = len(merged_items)

    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_items = merged_items[start_idx:end_idx]

    return PaginatedResponse.create(items=page_items, total=total, page=page, page_size=page_size)
