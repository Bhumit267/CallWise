"""Contacts API router: list contacts with masked phones, call/appointment counts, and full detail history."""

from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from callwise.api.deps import get_tenant_db
from callwise.api.permissions import require_staff
from callwise.api.schemas import (
    AppointmentListItem,
    CallListItem,
    ContactDetail,
    ContactListItem,
    MessageListItem,
    PaginatedResponse,
    mask_phone_number,
)
from callwise.db.models import (
    Appointment,
    Business,
    Call,
    Contact,
    FollowUp,
    Message,
    Session as UserSession,
    User,
)

router = APIRouter(prefix="/contacts", tags=["Contacts"])


@router.get("", response_model=PaginatedResponse[ContactListItem])
async def list_contacts(
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search contact name, phone, or email"),
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> PaginatedResponse[ContactListItem]:
    """List customer contacts for the tenant business with masked phone numbers."""
    _, business, _, _ = auth_ctx

    conditions = [Contact.business_id == business.id]

    if search:
        search_filter = f"%{search.strip()}%"
        conditions.append(
            or_(
                Contact.name.ilike(search_filter),
                Contact.phone.ilike(search_filter),
                Contact.email.ilike(search_filter),
            )
        )

    count_stmt = select(func.count(Contact.id)).where(*conditions)
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(Contact)
        .options(
            selectinload(Contact.calls),
            selectinload(Contact.appointments),
        )
        .where(*conditions)
        .order_by(Contact.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    records = (await db.execute(stmt)).scalars().all()

    items = [
        ContactListItem(
            id=c.id,
            name=c.name,
            phone=mask_phone_number(c.phone) or c.phone,
            email=c.email,
            notes=c.notes,
            do_not_contact=c.do_not_contact,
            created_at=c.created_at,
            calls_count=len(c.calls),
            appointments_count=len(c.appointments),
        )
        for c in records
    ]

    return PaginatedResponse.create(items=items, total=total, page=page, page_size=page_size)


@router.get("/{contact_id}", response_model=ContactDetail)
async def get_contact_detail(
    contact_id: uuid.UUID,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> ContactDetail:
    """Retrieve full contact profile with unmasked phone and timeline history across calls, appointments, messages, and follow-ups."""
    _, business, _, _ = auth_ctx

    stmt = (
        select(Contact)
        .options(
            selectinload(Contact.calls).selectinload(Call.turns),
            selectinload(Contact.calls).selectinload(Call.appointments),
            selectinload(Contact.calls).selectinload(Call.messages),
            selectinload(Contact.calls).selectinload(Call.transfers),
            selectinload(Contact.appointments).selectinload(Appointment.service),
            selectinload(Contact.messages),
            selectinload(Contact.follow_ups),
        )
        .where(Contact.id == contact_id, Contact.business_id == business.id)
    )
    contact = (await db.execute(stmt)).scalar_one_or_none()

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contact '{contact_id}' not found.",
        )

    return ContactDetail(
        id=contact.id,
        name=contact.name,
        phone=contact.phone,  # Unmasked in detail view
        email=contact.email,
        notes=contact.notes,
        do_not_contact=contact.do_not_contact,
        created_at=contact.created_at,
        updated_at=contact.updated_at,
        calls=[
            CallListItem(
                id=c.id,
                caller_number=mask_phone_number(c.caller_number),
                contact_id=c.contact_id,
                contact_name=contact.name,
                started_at=c.started_at,
                ended_at=c.ended_at,
                duration_seconds=c.duration_seconds,
                summary=c.summary,
                turn_count=len(c.turns),
                has_appointment=len(c.appointments) > 0,
                has_message=len(c.messages) > 0,
                has_transfer=len(c.transfers) > 0,
            )
            for c in contact.calls
        ],
        appointments=[
            AppointmentListItem(
                id=a.id,
                service_id=a.service_id,
                service_name=a.service.name if a.service else "Unknown Service",
                customer_name=a.customer_name,
                customer_phone=mask_phone_number(a.customer_phone) or a.customer_phone,
                customer_email=a.customer_email,
                start_at=a.start_at,
                end_at=a.end_at,
                status=a.status,
                contact_id=a.contact_id,
                call_id=a.call_id,
                created_at=a.created_at,
            )
            for a in contact.appointments
        ],
        messages=[
            MessageListItem(
                id=m.id,
                call_id=m.call_id,
                contact_id=m.contact_id,
                contact_name=contact.name,
                caller_name=m.caller_name,
                callback_number=mask_phone_number(m.callback_number) or m.callback_number,
                reason=m.reason,
                created_at=m.created_at,
            )
            for m in contact.messages
        ],
        follow_ups=[
            {
                "id": str(fu.id),
                "title": fu.title,
                "description": fu.description,
                "status": fu.status,
                "source": fu.source,
                "due_at": fu.due_at.isoformat() if fu.due_at else None,
                "created_at": fu.created_at.isoformat(),
            }
            for fu in contact.follow_ups
        ],
    )
