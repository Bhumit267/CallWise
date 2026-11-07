"""Audit logging helper for security, settings, knowledge, and appointment operations."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from callwise.db.models import AuditLog


async def record_audit_log(
    db: AsyncSession,
    business_id: uuid.UUID,
    user_id: Optional[uuid.UUID],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    changes: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    """Persist an audit trail record for compliance and change tracking."""
    log = AuditLog(
        id=uuid.uuid4(),
        business_id=business_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        changes=changes,
        ip_address=ip_address,
        created_at=datetime.now(timezone.utc),
    )
    db.add(log)
    await db.flush()
    return log
