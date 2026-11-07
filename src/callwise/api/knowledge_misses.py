"""Knowledge Misses API router: list unanswered questions, grouped frequency analytics, and one-click resolution."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import String, cast, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from callwise.api.audit import record_audit_log
from callwise.api.deps import get_tenant_db
from callwise.api.permissions import require_manager, require_staff
from callwise.api.schemas import (
    KnowledgeMissGroupItem,
    KnowledgeMissListItem,
    PaginatedResponse,
)
from callwise.db.models import Business, KnowledgeMiss, Session as UserSession, User
from callwise.knowledge.ingest import ingest_text_snippet

router = APIRouter(prefix="/knowledge-misses", tags=["Knowledge Misses"])


class ResolveMissRequest(BaseModel):
    answer: str = Field(..., min_length=1, description="Direct answer to add to knowledge base")


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


@router.post("/{miss_id}/resolve")
async def resolve_knowledge_miss(
    miss_id: uuid.UUID,
    payload: ResolveMissRequest,
    request: Request,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> Dict[str, Any]:
    """
    Resolve a knowledge miss by creating an ingested Q&A text snippet and marking
    all matching unresolved questions as resolved.
    """
    user, business, _, _ = auth_ctx

    stmt = select(KnowledgeMiss).where(
        KnowledgeMiss.id == miss_id,
        KnowledgeMiss.business_id == business.id,
    )
    miss = (await db.execute(stmt)).scalar_one_or_none()

    if not miss:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge miss '{miss_id}' not found.",
        )

    # 1. Ingest new Q&A snippet into knowledge vector base
    title = f"Q&A: {miss.query}"
    doc = ingest_text_snippet(
        business_id=business.id,
        title=title,
        content=f"Question: {miss.query}\nAnswer: {payload.answer}",
    )

    # 2. Mark this miss and any identical queries as resolved
    now = datetime.now(timezone.utc)
    miss.status = "resolved"
    miss.resolved_at = now
    miss.resolved_answer = payload.answer

    # Bulk update matching unresolved misses
    bulk_update_stmt = (
        update(KnowledgeMiss)
        .where(
            KnowledgeMiss.business_id == business.id,
            KnowledgeMiss.status == "unresolved",
            func.lower(KnowledgeMiss.query) == miss.query.lower().strip(),
        )
        .values(
            status="resolved",
            resolved_at=now,
            resolved_answer=payload.answer,
        )
    )
    res = await db.execute(bulk_update_stmt)
    resolved_count = res.rowcount or 1

    # 3. Audit log
    await record_audit_log(
        db=db,
        business_id=business.id,
        user_id=user.id,
        action="resolve_knowledge_miss",
        resource_type="knowledge_miss",
        resource_id=str(miss_id),
        changes={"query": miss.query, "answer": payload.answer, "document_id": str(doc.id), "resolved_count": resolved_count},
        ip_address=request.client.host if request.client else None,
    )
    await db.flush()

    return {
        "status": "ok",
        "message": f"Added answer and resolved {resolved_count} question instance(s).",
        "document_id": str(doc.id),
        "resolved_count": resolved_count,
    }


@router.post("/{miss_id}/ignore")
async def ignore_knowledge_miss(
    miss_id: uuid.UUID,
    request: Request,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> Dict[str, Any]:
    """Ignore a knowledge miss."""
    user, business, _, _ = auth_ctx

    stmt = select(KnowledgeMiss).where(
        KnowledgeMiss.id == miss_id,
        KnowledgeMiss.business_id == business.id,
    )
    miss = (await db.execute(stmt)).scalar_one_or_none()

    if not miss:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge miss '{miss_id}' not found.",
        )

    miss.status = "ignored"
    await record_audit_log(
        db=db,
        business_id=business.id,
        user_id=user.id,
        action="ignore_knowledge_miss",
        resource_type="knowledge_miss",
        resource_id=str(miss_id),
        changes={"query": miss.query, "status": "ignored"},
        ip_address=request.client.host if request.client else None,
    )
    await db.flush()

    return {"status": "ok", "message": "Knowledge miss ignored.", "miss_id": str(miss_id)}
