"""Follow-ups API router: list actionable staff tasks, filter by status/assignee, and detail view."""

from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from callwise.api.deps import get_tenant_db
from callwise.api.permissions import require_staff
from callwise.api.schemas import (
    FollowUpDetail,
    FollowUpListItem,
    PaginatedResponse,
)
from callwise.db.models import Business, Contact, FollowUp, Session as UserSession, User

router = APIRouter(prefix="/follow-ups", tags=["Follow-ups"])


@router.get("", response_model=PaginatedResponse[FollowUpListItem])
async def list_follow_ups(
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (open, done, snoozed)"),
    assigned_to_user_id: Optional[uuid.UUID] = Query(None, description="Filter by assigned staff user ID"),
    search: Optional[str] = Query(None, description="Search task title or description"),
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> PaginatedResponse[FollowUpListItem]:
    """List staff follow-up items for the tenant business with pagination and filters."""
    _, business, _, _ = auth_ctx

    conditions = [FollowUp.business_id == business.id]

    if status_filter:
        conditions.append(FollowUp.status == status_filter.strip())

    if assigned_to_user_id:
        conditions.append(FollowUp.assigned_to_user_id == assigned_to_user_id)

    if search:
        search_filter = f"%{search.strip()}%"
        conditions.append(
            or_(
                FollowUp.title.ilike(search_filter),
                FollowUp.description.ilike(search_filter),
            )
        )

    count_stmt = select(func.count(FollowUp.id)).where(*conditions)
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(FollowUp)
        .options(
            selectinload(FollowUp.contact),
            selectinload(FollowUp.assigned_to),
        )
        .where(*conditions)
        .order_by(FollowUp.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    records = (await db.execute(stmt)).scalars().all()

    items = [
        FollowUpListItem(
            id=fu.id,
            contact_id=fu.contact_id,
            contact_name=fu.contact.name if fu.contact else None,
            assigned_to_user_id=fu.assigned_to_user_id,
            assigned_to_name=fu.assigned_to.name if fu.assigned_to else None,
            title=fu.title,
            description=fu.description,
            source=fu.source,
            source_id=fu.source_id,
            status=fu.status,
            snoozed_until=fu.snoozed_until,
            due_at=fu.due_at,
            created_at=fu.created_at,
        )
        for fu in records
    ]

    return PaginatedResponse.create(items=items, total=total, page=page, page_size=page_size)


@router.get("/{follow_up_id}", response_model=FollowUpDetail)
async def get_follow_up_detail(
    follow_up_id: uuid.UUID,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> FollowUpDetail:
    """Retrieve full follow-up detail with contact and assignee details."""
    _, business, _, _ = auth_ctx

    stmt = (
        select(FollowUp)
        .options(
            selectinload(FollowUp.contact),
            selectinload(FollowUp.assigned_to),
        )
        .where(FollowUp.id == follow_up_id, FollowUp.business_id == business.id)
    )
    fu = (await db.execute(stmt)).scalar_one_or_none()

    if not fu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Follow-up '{follow_up_id}' not found.",
        )

    return FollowUpDetail(
        id=fu.id,
        contact_id=fu.contact_id,
        contact_name=fu.contact.name if fu.contact else None,
        assigned_to_user_id=fu.assigned_to_user_id,
        assigned_to_name=fu.assigned_to.name if fu.assigned_to else None,
        assigned_to_email=fu.assigned_to.email if fu.assigned_to else None,
        title=fu.title,
        description=fu.description,
        source=fu.source,
        source_id=fu.source_id,
        status=fu.status,
        snoozed_until=fu.snoozed_until,
        due_at=fu.due_at,
        created_at=fu.created_at,
        updated_at=fu.updated_at,
    )
