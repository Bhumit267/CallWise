"""Audit Logs API router: list paginated audit log entries with user identities and change diffs."""

from datetime import datetime
from typing import Any, Dict, Optional
import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from callwise.api.deps import get_tenant_db
from callwise.api.permissions import require_manager
from callwise.api.schemas import PaginatedResponse, parse_query_datetime
from callwise.db.models import AuditLog, Business, Session as UserSession, User

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


class AuditLogItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    changes: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    created_at: datetime


@router.get("", response_model=PaginatedResponse[AuditLogItem])
async def list_audit_logs(
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    action: Optional[str] = Query(None, description="Filter by action name"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    start_date: Optional[str] = Query(None, description="Filter logs after date (ISO-8601)"),
    end_date: Optional[str] = Query(None, description="Filter logs before date (ISO-8601)"),
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> PaginatedResponse[AuditLogItem]:
    """Retrieve paginated audit log records for the business tenant."""
    _, business, _, _ = auth_ctx

    conditions = [AuditLog.business_id == business.id]

    if action:
        conditions.append(AuditLog.action == action.strip())

    if resource_type:
        conditions.append(AuditLog.resource_type == resource_type.strip())

    parsed_start = parse_query_datetime(start_date)
    parsed_end = parse_query_datetime(end_date)

    if parsed_start:
        conditions.append(AuditLog.created_at >= parsed_start)
    if parsed_end:
        conditions.append(AuditLog.created_at <= parsed_end)

    count_stmt = select(func.count(AuditLog.id)).where(*conditions)
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(AuditLog)
        .options(selectinload(AuditLog.user))
        .where(*conditions)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    records = (await db.execute(stmt)).scalars().all()

    items = [
        AuditLogItem(
            id=l.id,
            user_id=l.user_id,
            user_name=l.user.name if l.user else "System",
            user_email=l.user.email if l.user else None,
            action=l.action,
            resource_type=l.resource_type,
            resource_id=l.resource_id,
            changes=l.changes,
            ip_address=l.ip_address,
            created_at=l.created_at,
        )
        for l in records
    ]

    return PaginatedResponse.create(items=items, total=total, page=page, page_size=page_size)
