"""Messages API router: list recorded callback messages with masked phone numbers and detail view."""

from datetime import datetime
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from callwise.api.deps import get_tenant_db
from callwise.api.permissions import require_staff
from callwise.api.schemas import (
    MessageDetail,
    MessageListItem,
    PaginatedResponse,
    mask_phone_number,
    parse_query_datetime,
)
from callwise.db.models import Business, Call, Contact, Message, Session as UserSession, User

router = APIRouter(prefix="/messages", tags=["Messages"])


@router.get("", response_model=PaginatedResponse[MessageListItem])
async def list_messages(
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search caller name, phone, or reason"),
    start_date: Optional[str] = Query(None, description="Filter messages after start date (ISO-8601)"),
    end_date: Optional[str] = Query(None, description="Filter messages before end date (ISO-8601)"),
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> PaginatedResponse[MessageListItem]:
    """List callback messages for the tenant with masked callback phone numbers."""
    _, business, _, _ = auth_ctx

    conditions = [Message.business_id == business.id]

    if search:
        search_filter = f"%{search.strip()}%"
        conditions.append(
            or_(
                Message.caller_name.ilike(search_filter),
                Message.callback_number.ilike(search_filter),
                Message.reason.ilike(search_filter),
            )
        )

    parsed_start = parse_query_datetime(start_date)
    parsed_end = parse_query_datetime(end_date)

    if parsed_start:
        conditions.append(Message.created_at >= parsed_start)
    if parsed_end:
        conditions.append(Message.created_at <= parsed_end)

    count_stmt = select(func.count(Message.id)).where(*conditions)
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(Message)
        .options(selectinload(Message.contact))
        .where(*conditions)
        .order_by(Message.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    records = (await db.execute(stmt)).scalars().all()

    items = [
        MessageListItem(
            id=m.id,
            call_id=m.call_id,
            contact_id=m.contact_id,
            contact_name=m.contact.name if m.contact else None,
            caller_name=m.caller_name,
            callback_number=mask_phone_number(m.callback_number) or m.callback_number,
            reason=m.reason,
            created_at=m.created_at,
        )
        for m in records
    ]

    return PaginatedResponse.create(items=items, total=total, page=page, page_size=page_size)


@router.get("/{message_id}", response_model=MessageDetail)
async def get_message_detail(
    message_id: uuid.UUID,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> MessageDetail:
    """Retrieve full message detail with unmasked callback phone number."""
    _, business, _, _ = auth_ctx

    stmt = (
        select(Message)
        .options(selectinload(Message.contact), selectinload(Message.call))
        .where(Message.id == message_id, Message.business_id == business.id)
    )
    message = (await db.execute(stmt)).scalar_one_or_none()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message '{message_id}' not found.",
        )

    return MessageDetail(
        id=message.id,
        call_id=message.call_id,
        contact_id=message.contact_id,
        contact_name=message.contact.name if message.contact else None,
        caller_name=message.caller_name,
        callback_number=message.callback_number,  # Unmasked in detail view
        reason=message.reason,
        created_at=message.created_at,
        call_summary=message.call.summary if message.call else None,
    )
