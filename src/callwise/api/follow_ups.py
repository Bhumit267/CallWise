"""Follow-ups API router: list actionable staff tasks, create manual tasks, and update status/assignee."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from callwise.api.audit import record_audit_log
from callwise.api.deps import get_tenant_db
from callwise.api.permissions import require_staff
from callwise.api.schemas import (
    FollowUpDetail,
    FollowUpListItem,
    PaginatedResponse,
    parse_query_datetime,
)
from callwise.db.models import Business, Contact, FollowUp, Session as UserSession, User

router = APIRouter(prefix="/follow-ups", tags=["Follow-ups"])


class FollowUpCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    contact_id: Optional[uuid.UUID] = None
    assigned_to_user_id: Optional[uuid.UUID] = None
    due_at: Optional[str] = Field(None, description="Due date in ISO-8601")


class FollowUpUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = Field(None, description="Status: open, done, or snoozed")
    snoozed_until: Optional[str] = Field(None, description="Snoozed until ISO-8601")
    due_at: Optional[str] = Field(None, description="Due date in ISO-8601")
    assigned_to_user_id: Optional[uuid.UUID] = None


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


@router.post("", response_model=FollowUpDetail, status_code=status.HTTP_201_CREATED)
async def create_follow_up(
    payload: FollowUpCreate,
    request: Request,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> FollowUpDetail:
    """Create a manual staff follow-up task."""
    user, business, _, _ = auth_ctx

    due_dt = parse_query_datetime(payload.due_at)

    fu = FollowUp(
        id=uuid.uuid4(),
        business_id=business.id,
        contact_id=payload.contact_id,
        assigned_to_user_id=payload.assigned_to_user_id,
        title=payload.title,
        description=payload.description,
        source="manual",
        status="open",
        due_at=due_dt,
    )
    db.add(fu)
    await db.flush()

    await record_audit_log(
        db=db,
        business_id=business.id,
        user_id=user.id,
        action="create_follow_up",
        resource_type="follow_up",
        resource_id=str(fu.id),
        changes={"title": fu.title, "source": "manual"},
        ip_address=request.client.host if request.client else None,
    )
    await db.flush()

    return await get_follow_up_detail(fu.id, auth_ctx=auth_ctx, db=db)


@router.patch("/{follow_up_id}", response_model=FollowUpDetail)
async def update_follow_up(
    follow_up_id: uuid.UUID,
    payload: FollowUpUpdate,
    request: Request,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> FollowUpDetail:
    """Update follow-up task status, snooze, or assignment."""
    user, business, _, _ = auth_ctx

    stmt = select(FollowUp).where(FollowUp.id == follow_up_id, FollowUp.business_id == business.id)
    fu = (await db.execute(stmt)).scalar_one_or_none()

    if not fu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Follow-up '{follow_up_id}' not found.",
        )

    changes = {}
    if payload.title is not None and payload.title != fu.title:
        changes["title"] = {"old": fu.title, "new": payload.title}
        fu.title = payload.title

    if payload.description is not None and payload.description != fu.description:
        changes["description"] = {"old": fu.description, "new": payload.description}
        fu.description = payload.description

    if payload.status is not None and payload.status != fu.status:
        changes["status"] = {"old": fu.status, "new": payload.status}
        fu.status = payload.status

    if payload.snoozed_until is not None:
        snooze_dt = parse_query_datetime(payload.snoozed_until)
        changes["snoozed_until"] = {"old": str(fu.snoozed_until), "new": str(snooze_dt)}
        fu.snoozed_until = snooze_dt
        fu.status = "snoozed"

    if payload.due_at is not None:
        due_dt = parse_query_datetime(payload.due_at)
        changes["due_at"] = {"old": str(fu.due_at), "new": str(due_dt)}
        fu.due_at = due_dt

    if payload.assigned_to_user_id is not None and payload.assigned_to_user_id != fu.assigned_to_user_id:
        changes["assigned_to_user_id"] = {"old": str(fu.assigned_to_user_id), "new": str(payload.assigned_to_user_id)}
        fu.assigned_to_user_id = payload.assigned_to_user_id

    if changes:
        fu.updated_at = datetime.now(timezone.utc)
        await record_audit_log(
            db=db,
            business_id=business.id,
            user_id=user.id,
            action="update_follow_up",
            resource_type="follow_up",
            resource_id=str(fu.id),
            changes=changes,
            ip_address=request.client.host if request.client else None,
        )
        await db.flush()

    return await get_follow_up_detail(fu.id, auth_ctx=auth_ctx, db=db)
