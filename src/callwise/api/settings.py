"""Settings API router: business profile, hours, services CRUD, safe provider status, and audit trails."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from callwise.api.audit import record_audit_log
from callwise.api.deps import get_tenant_db
from callwise.api.permissions import require_manager, require_staff
from callwise.config import settings
from callwise.db.models import Appointment, Business, Service, Session as UserSession, User

router = APIRouter(prefix="/settings", tags=["Settings"])


# ============================================================================
# Schemas
# ============================================================================

class BusinessProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    business_type: Optional[str] = Field(None, min_length=1, max_length=100)
    greeting: Optional[str] = Field(None, min_length=1)
    tone: Optional[str] = Field(None, min_length=1, max_length=100)
    timezone: Optional[str] = Field(None, min_length=1, max_length=100)
    transfer_number: Optional[str] = Field(None, max_length=100)
    notification_email: Optional[EmailStr] = None
    retention_days: Optional[int] = Field(None, ge=1, le=3650)
    website_url: Optional[str] = Field(None, max_length=500)


class BusinessHoursUpdate(BaseModel):
    hours: Dict[str, Any] = Field(..., description="Structured weekly schedule and holiday overrides")


class ServiceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    duration_minutes: int = Field(..., gt=0, le=1440)
    price: float = Field(..., ge=0.0)
    description: Optional[str] = None
    is_active: bool = True


class ServiceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    duration_minutes: Optional[int] = Field(None, gt=0, le=1440)
    price: Optional[float] = Field(None, ge=0.0)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class ServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    duration_minutes: int
    price: float
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BusinessSettingsResponse(BaseModel):
    id: uuid.UUID
    name: str
    business_type: str
    greeting: str
    tone: str
    timezone: str
    transfer_number: Optional[str] = None
    notification_email: Optional[str] = None
    retention_days: Optional[int] = 90
    website_url: Optional[str] = None
    hours: Dict[str, Any]
    providers: Dict[str, Any]


# ============================================================================
# Endpoints
# ============================================================================

@router.get("", response_model=BusinessSettingsResponse)
async def get_settings(
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
) -> BusinessSettingsResponse:
    """Retrieve business profile settings, hours, and safe active provider statuses."""
    _, business, _, _ = auth_ctx

    safe_providers = {
        "llm_provider": settings.llm_provider,
        "tts_provider": settings.tts_provider,
        "stt_provider": settings.stt_provider,
        "embedding_provider": settings.embedding_provider,
        "email_notifications_enabled": bool(settings.smtp_host or settings.sendgrid_api_key),
        "google_calendar_enabled": bool(settings.google_calendar_credentials_file),
    }

    return BusinessSettingsResponse(
        id=business.id,
        name=business.name,
        business_type=business.business_type,
        greeting=business.greeting,
        tone=business.tone,
        timezone=business.timezone,
        transfer_number=business.transfer_number,
        notification_email=business.notification_email,
        retention_days=business.retention_days,
        website_url=business.website_url,
        hours=business.hours or {},
        providers=safe_providers,
    )


@router.put("/profile", response_model=BusinessSettingsResponse)
async def update_profile(
    payload: BusinessProfileUpdate,
    request: Request,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> BusinessSettingsResponse:
    """Update tenant business profile and record audit trail."""
    user, business, _, _ = auth_ctx

    changes = {}
    for field, val in payload.model_dump(exclude_unset=True).items():
        old_val = getattr(business, field)
        if old_val != val:
            changes[field] = {"old": old_val, "new": val}
            setattr(business, field, val)

    if changes:
        business.updated_at = datetime.now(timezone.utc)
        await record_audit_log(
            db=db,
            business_id=business.id,
            user_id=user.id,
            action="update_profile",
            resource_type="business",
            resource_id=str(business.id),
            changes=changes,
            ip_address=request.client.host if request.client else None,
        )
        await db.flush()

    return await get_settings(auth_ctx=auth_ctx)


@router.put("/hours", response_model=BusinessSettingsResponse)
async def update_hours(
    payload: BusinessHoursUpdate,
    request: Request,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> BusinessSettingsResponse:
    """Update operating hours schedule and holiday overrides."""
    user, business, _, _ = auth_ctx

    old_hours = business.hours or {}
    business.hours = payload.hours
    business.updated_at = datetime.now(timezone.utc)

    await record_audit_log(
        db=db,
        business_id=business.id,
        user_id=user.id,
        action="update_hours",
        resource_type="business",
        resource_id=str(business.id),
        changes={"hours": {"old": old_hours, "new": payload.hours}},
        ip_address=request.client.host if request.client else None,
    )
    await db.flush()

    return await get_settings(auth_ctx=auth_ctx)


@router.get("/services", response_model=List[ServiceResponse])
async def list_services(
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> List[ServiceResponse]:
    """List all services offered by the business tenant."""
    _, business, _, _ = auth_ctx

    stmt = (
        select(Service)
        .where(Service.business_id == business.id)
        .order_by(Service.name.asc())
    )
    services = (await db.execute(stmt)).scalars().all()
    return [ServiceResponse.model_validate(s) for s in services]


@router.post("/services", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_service(
    payload: ServiceCreate,
    request: Request,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> ServiceResponse:
    """Create a new service offering."""
    user, business, _, _ = auth_ctx

    svc = Service(
        id=uuid.uuid4(),
        business_id=business.id,
        name=payload.name,
        duration_minutes=payload.duration_minutes,
        price=payload.price,
        description=payload.description,
        is_active=payload.is_active,
    )
    db.add(svc)
    await db.flush()

    await record_audit_log(
        db=db,
        business_id=business.id,
        user_id=user.id,
        action="create_service",
        resource_type="service",
        resource_id=str(svc.id),
        changes=payload.model_dump(),
        ip_address=request.client.host if request.client else None,
    )

    return ServiceResponse.model_validate(svc)


@router.put("/services/{service_id}", response_model=ServiceResponse)
async def update_service(
    service_id: uuid.UUID,
    payload: ServiceUpdate,
    request: Request,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> ServiceResponse:
    """Update an existing service offering."""
    user, business, _, _ = auth_ctx

    stmt = select(Service).where(Service.id == service_id, Service.business_id == business.id)
    svc = (await db.execute(stmt)).scalar_one_or_none()

    if not svc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_id}' not found.",
        )

    changes = {}
    for field, val in payload.model_dump(exclude_unset=True).items():
        old_val = getattr(svc, field)
        if old_val != val:
            changes[field] = {"old": old_val, "new": val}
            setattr(svc, field, val)

    if changes:
        svc.updated_at = datetime.now(timezone.utc)
        await record_audit_log(
            db=db,
            business_id=business.id,
            user_id=user.id,
            action="update_service",
            resource_type="service",
            resource_id=str(svc.id),
            changes=changes,
            ip_address=request.client.host if request.client else None,
        )
        await db.flush()

    return ServiceResponse.model_validate(svc)


@router.delete("/services/{service_id}")
async def delete_service(
    service_id: uuid.UUID,
    request: Request,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> Dict[str, Any]:
    """Delete a service offering, or soft-deactivate if past appointments exist."""
    user, business, _, _ = auth_ctx

    stmt = select(Service).where(Service.id == service_id, Service.business_id == business.id)
    svc = (await db.execute(stmt)).scalar_one_or_none()

    if not svc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_id}' not found.",
        )

    # Check for linked appointments
    count_stmt = select(func.count(Appointment.id)).where(Appointment.service_id == service_id)
    appointment_count = (await db.execute(count_stmt)).scalar() or 0

    if appointment_count > 0:
        # Soft-delete to preserve historical integrity
        svc.is_active = False
        svc.updated_at = datetime.now(timezone.utc)
        action = "deactivate_service"
        message = "Service has existing appointments; it has been deactivated rather than deleted."
    else:
        await db.delete(svc)
        action = "delete_service"
        message = "Service successfully deleted."

    await record_audit_log(
        db=db,
        business_id=business.id,
        user_id=user.id,
        action=action,
        resource_type="service",
        resource_id=str(service_id),
        changes={"name": svc.name, "had_appointments": appointment_count},
        ip_address=request.client.host if request.client else None,
    )
    await db.flush()

    return {"status": "ok", "message": message, "service_id": str(service_id)}
