"""Calls API router: list calls with masked phones, eager loaded relationships, and full detail."""

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
    CallDetail,
    CallListItem,
    CallTurnItem,
    PaginatedResponse,
    mask_phone_number,
    parse_query_datetime,
)
from callwise.db.models import Business, Call, Contact, Session as UserSession, User

router = APIRouter(prefix="/calls", tags=["Calls"])


@router.get("", response_model=PaginatedResponse[CallListItem])
async def list_calls(
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search caller number or summary"),
    start_date: Optional[str] = Query(None, description="Filter calls after start date (ISO-8601)"),
    end_date: Optional[str] = Query(None, description="Filter calls before end date (ISO-8601)"),
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> PaginatedResponse[CallListItem]:
    """List calls for the tenant business with pagination and masked phone numbers."""
    _, business, _, _ = auth_ctx

    conditions = [Call.business_id == business.id]

    if search:
        search_filter = f"%{search.strip()}%"
        conditions.append(
            or_(
                Call.caller_number.ilike(search_filter),
                Call.summary.ilike(search_filter),
            )
        )

    parsed_start = parse_query_datetime(start_date)
    parsed_end = parse_query_datetime(end_date)

    if parsed_start:
        conditions.append(Call.started_at >= parsed_start)
    if parsed_end:
        conditions.append(Call.started_at <= parsed_end)

    # Total count query
    count_stmt = select(func.count(Call.id)).where(*conditions)
    total = (await db.execute(count_stmt)).scalar() or 0

    # Paginated items query with eager loading to avoid N+1 queries
    stmt = (
        select(Call)
        .options(
            selectinload(Call.contact),
            selectinload(Call.turns),
            selectinload(Call.appointments),
            selectinload(Call.messages),
            selectinload(Call.transfers),
        )
        .where(*conditions)
        .order_by(Call.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    records = (await db.execute(stmt)).scalars().all()

    items = [
        CallListItem(
            id=c.id,
            caller_number=mask_phone_number(c.caller_number),
            contact_id=c.contact_id,
            contact_name=c.contact.name if c.contact else None,
            started_at=c.started_at,
            ended_at=c.ended_at,
            duration_seconds=c.duration_seconds,
            summary=c.summary,
            turn_count=len(c.turns),
            has_appointment=len(c.appointments) > 0,
            has_message=len(c.messages) > 0,
            has_transfer=len(c.transfers) > 0,
        )
        for c in records
    ]

    return PaginatedResponse.create(items=items, total=total, page=page, page_size=page_size)


@router.get("/{call_id}", response_model=CallDetail)
async def get_call_detail(
    call_id: uuid.UUID,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> CallDetail:
    """Retrieve full call detail including unmasked caller number, full turns, and linked records."""
    _, business, _, _ = auth_ctx

    stmt = (
        select(Call)
        .options(
            selectinload(Call.contact),
            selectinload(Call.turns),
            selectinload(Call.appointments),
            selectinload(Call.messages),
            selectinload(Call.transfers),
            selectinload(Call.knowledge_misses),
        )
        .where(Call.id == call_id, Call.business_id == business.id)
    )
    call = (await db.execute(stmt)).scalar_one_or_none()

    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Call '{call_id}' not found.",
        )

    return CallDetail(
        id=call.id,
        caller_number=call.caller_number,  # Unmasked in detail view
        contact_id=call.contact_id,
        contact_name=call.contact.name if call.contact else None,
        started_at=call.started_at,
        ended_at=call.ended_at,
        duration_seconds=call.duration_seconds,
        summary=call.summary,
        llm_provider=call.llm_provider,
        llm_model=call.llm_model,
        tts_provider=call.tts_provider,
        stt_provider=call.stt_provider,
        turns=[
            CallTurnItem(
                id=t.id,
                speaker=t.speaker,
                text=t.text,
                latency_ms=t.latency_ms,
                timestamp=t.timestamp,
            )
            for t in call.turns
        ],
        appointments=[
            {
                "id": str(a.id),
                "service_id": str(a.service_id),
                "customer_name": a.customer_name,
                "start_at": a.start_at.isoformat(),
                "end_at": a.end_at.isoformat(),
                "status": a.status,
            }
            for a in call.appointments
        ],
        messages=[
            {
                "id": str(m.id),
                "caller_name": m.caller_name,
                "callback_number": m.callback_number,
                "reason": m.reason,
                "created_at": m.created_at.isoformat(),
            }
            for m in call.messages
        ],
        transfers=[
            {
                "id": str(tr.id),
                "reason": tr.reason,
                "status": tr.status,
                "timestamp": tr.timestamp.isoformat(),
            }
            for tr in call.transfers
        ],
        knowledge_misses=[
            {
                "id": str(km.id),
                "query": km.query,
                "status": km.status,
                "created_at": km.created_at.isoformat(),
            }
            for km in call.knowledge_misses
        ],
    )
