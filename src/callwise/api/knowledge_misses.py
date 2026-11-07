"""Knowledge Misses API router: list unanswered questions and grouped frequency analytics."""

from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from callwise.api.deps import get_tenant_db
from callwise.api.permissions import require_staff
from callwise.api.schemas import (
    KnowledgeMissGroupItem,
    KnowledgeMissListItem,
    PaginatedResponse,
)
from callwise.db.models import Business, KnowledgeMiss, Session as UserSession, User

router = APIRouter(prefix="/knowledge-misses", tags=["Knowledge Misses"])


@router.get("", response_model=PaginatedResponse[KnowledgeMissListItem])
async def list_knowledge_misses(
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (unresolved, resolved, ignored)"),
    search: Optional[str] = Query(None, description="Search query text"),
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> PaginatedResponse[KnowledgeMissListItem]:
    """List knowledge misses with pagination and status filters."""
    _, business, _, _ = auth_ctx

    conditions = [KnowledgeMiss.business_id == business.id]

    if status_filter:
        conditions.append(KnowledgeMiss.status == status_filter.strip())

    if search:
        conditions.append(KnowledgeMiss.query.ilike(f"%{search.strip()}%"))

    count_stmt = select(func.count(KnowledgeMiss.id)).where(*conditions)
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(KnowledgeMiss)
        .where(*conditions)
        .order_by(KnowledgeMiss.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    records = (await db.execute(stmt)).scalars().all()

    items = [
        KnowledgeMissListItem(
            id=km.id,
            call_id=km.call_id,
            query=km.query,
            status=km.status,
            resolved_at=km.resolved_at,
            resolved_answer=km.resolved_answer,
            created_at=km.created_at,
        )
        for km in records
    ]

    return PaginatedResponse.create(items=items, total=total, page=page, page_size=page_size)


@router.get("/grouped", response_model=List[KnowledgeMissGroupItem])
async def get_grouped_knowledge_misses(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (unresolved, resolved, etc.)"),
    limit: int = Query(50, ge=1, le=200, description="Max groups to return"),
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> List[KnowledgeMissGroupItem]:
    """Return knowledge misses grouped by question similarity and frequency."""
    _, business, _, _ = auth_ctx

    conditions = [KnowledgeMiss.business_id == business.id]
    if status_filter:
        conditions.append(KnowledgeMiss.status == status_filter.strip())

    # Group by lowercase query and status, ordered by count descending
    stmt = (
        select(
            func.min(KnowledgeMiss.query).label("query"),
            func.count(KnowledgeMiss.id).label("count"),
            KnowledgeMiss.status.label("status"),
            func.max(KnowledgeMiss.created_at).label("last_asked_at"),
            func.max(cast(KnowledgeMiss.id, String)).label("sample_miss_id_str"),
        )
        .where(*conditions)
        .group_by(func.lower(KnowledgeMiss.query), KnowledgeMiss.status)
        .order_by(func.count(KnowledgeMiss.id).desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()

    return [
        KnowledgeMissGroupItem(
            query=row.query,
            count=row.count,
            status=row.status,
            last_asked_at=row.last_asked_at,
            sample_miss_id=uuid.UUID(row.sample_miss_id_str),
        )
        for row in rows
    ]
