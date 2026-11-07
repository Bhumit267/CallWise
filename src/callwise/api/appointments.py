"""Appointments API router: list appointments, calendar range fetch, full detail view, manual booking, cancel, and reschedule."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from callwise.api.audit import record_audit_log
from callwise.api.deps import get_tenant_db
from callwise.api.permissions import require_staff
from callwise.api.schemas import (
    AppointmentCalendarItem,
    AppointmentDetail,
    AppointmentListItem,
    PaginatedResponse,
    mask_phone_number,
    parse_query_datetime,
)
from callwise.booking.service import BookingError, book_appointment
from callwise.db.models import (
    Appointment,
    Business,
    Contact,
    Reminder,
    Service,
    Session as UserSession,
    User,
    VerificationAttempt,
)

router = APIRouter(prefix="/appointments", tags=["Appointments"])


# ============================================================================
# Schemas
# ============================================================================

class AppointmentCreateRequest(BaseModel):
    service_id: uuid.UUID
    customer_name: str = Field(..., min_length=1, max_length=255)
    customer_phone: str = Field(..., min_length=3, max_length=100)
    customer_email: Optional[EmailStr] = None
    start_time: str = Field(..., description="Desired appointment start time (ISO-8601, e.g. 2026-11-10T14:00:00Z)")


class AppointmentRescheduleRequest(BaseModel):
    new_start_time: str = Field(..., description="New appointment start time in ISO-8601")


# ============================================================================
# Endpoints
# ============================================================================

@router.get("", response_model=PaginatedResponse[AppointmentListItem])
async def list_appointments(
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (booked, cancelled, etc.)"),
    start_date: Optional[str] = Query(None, description="Filter appointments starting after date (ISO-8601)"),
    end_date: Optional[str] = Query(None, description="Filter appointments ending before date (ISO-8601)"),
    search: Optional[str] = Query(None, description="Search customer name, phone, or service"),
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> PaginatedResponse[AppointmentListItem]:
    """List appointments for the tenant business with masked customer phone numbers."""
    _, business, _, _ = auth_ctx

    conditions = [Appointment.business_id == business.id]

    if status_filter:
        conditions.append(Appointment.status == status_filter.strip())

    parsed_start = parse_query_datetime(start_date)
    parsed_end = parse_query_datetime(end_date)

    if parsed_start:
        conditions.append(Appointment.start_at >= parsed_start)
    if parsed_end:
        conditions.append(Appointment.end_at <= parsed_end)

    if search:
        search_filter = f"%{search.strip()}%"
        conditions.append(
            or_(
                Appointment.customer_name.ilike(search_filter),
                Appointment.customer_phone.ilike(search_filter),
                Appointment.service.has(Service.name.ilike(search_filter)),
            )
        )

    count_stmt = select(func.count(Appointment.id)).where(*conditions)
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(Appointment)
        .options(selectinload(Appointment.service))
        .where(*conditions)
        .order_by(Appointment.start_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    records = (await db.execute(stmt)).scalars().all()

    items = [
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
        for a in records
    ]

    return PaginatedResponse.create(items=items, total=total, page=page, page_size=page_size)


@router.get("/calendar", response_model=List[AppointmentCalendarItem])
async def get_calendar_appointments(
    start_date: str = Query(..., description="Range start in ISO-8601"),
    end_date: str = Query(..., description="Range end in ISO-8601"),
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> List[AppointmentCalendarItem]:
    """Retrieve appointments for a given date range for calendar views."""
    _, business, _, _ = auth_ctx

    parsed_start = parse_query_datetime(start_date)
    parsed_end = parse_query_datetime(end_date)

    if not parsed_start or not parsed_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid ISO-8601 start_date and end_date are required.",
        )

    stmt = (
        select(Appointment)
        .options(selectinload(Appointment.service))
        .where(
            Appointment.business_id == business.id,
            Appointment.start_at >= parsed_start,
            Appointment.end_at <= parsed_end,
        )
        .order_by(Appointment.start_at.asc())
    )
    records = (await db.execute(stmt)).scalars().all()

    return [
        AppointmentCalendarItem(
            id=a.id,
            service_id=a.service_id,
            service_name=a.service.name if a.service else "Unknown Service",
            customer_name=a.customer_name,
            customer_phone=mask_phone_number(a.customer_phone) or a.customer_phone,
            start_at=a.start_at,
            end_at=a.end_at,
            status=a.status,
        )
        for a in records
    ]


@router.get("/{appointment_id}", response_model=AppointmentDetail)
async def get_appointment_detail(
    appointment_id: uuid.UUID,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> AppointmentDetail:
    """Retrieve full appointment detail with unmasked phone number and verification history."""
    _, business, _, _ = auth_ctx

    stmt = (
        select(Appointment)
        .options(
            selectinload(Appointment.service),
            selectinload(Appointment.reminders),
            selectinload(Appointment.verification_attempts),
        )
        .where(Appointment.id == appointment_id, Appointment.business_id == business.id)
    )
    appointment = (await db.execute(stmt)).scalar_one_or_none()

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment '{appointment_id}' not found.",
        )

    return _build_appointment_detail(appointment)


@router.post("", response_model=AppointmentDetail, status_code=status.HTTP_201_CREATED)
async def create_manual_appointment(
    payload: AppointmentCreateRequest,
    request: Request,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> AppointmentDetail:
    """Manually book an appointment using the shared service-layer validation."""
    user, business, _, _ = auth_ctx

    parsed_start = parse_query_datetime(payload.start_time)
    if not parsed_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ISO-8601 start time format.",
        )

    try:
        booking_result = await book_appointment(
            session=db,
            business_id=business.id,
            service_id=payload.service_id,
            start_time=parsed_start,
            customer_name=payload.customer_name,
            customer_phone=payload.customer_phone,
            customer_email=str(payload.customer_email) if payload.customer_email else None,
        )
    except BookingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    appointment = booking_result.appointment

    # Auto-link or create contact record
    clean_phone = payload.customer_phone.strip()
    contact_stmt = select(Contact).where(
        Contact.business_id == business.id,
        Contact.phone == clean_phone,
    )
    contact = (await db.execute(contact_stmt)).scalar_one_or_none()
    if not contact:
        contact = Contact(
            id=uuid.uuid4(),
            business_id=business.id,
            name=payload.customer_name.strip(),
            phone=clean_phone,
            email=str(payload.customer_email).strip() if payload.customer_email else None,
        )
        db.add(contact)
        await db.flush()

    appointment.contact_id = contact.id

    await record_audit_log(
        db=db,
        business_id=business.id,
        user_id=user.id,
        action="manual_book_appointment",
        resource_type="appointment",
        resource_id=str(appointment.id),
        changes={
            "service_id": str(payload.service_id),
            "customer_name": payload.customer_name,
            "start_at": appointment.start_at.isoformat(),
        },
        ip_address=request.client.host if request.client else None,
    )
    await db.flush()

    # Re-fetch with loaded relationships
    reload_stmt = (
        select(Appointment)
        .options(
            selectinload(Appointment.service),
            selectinload(Appointment.reminders),
            selectinload(Appointment.verification_attempts),
        )
        .where(Appointment.id == appointment.id)
    )
    reloaded = (await db.execute(reload_stmt)).scalar_one()
    return _build_appointment_detail(reloaded)


@router.post("/{appointment_id}/cancel", response_model=AppointmentDetail)
async def cancel_appointment_endpoint(
    appointment_id: uuid.UUID,
    request: Request,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> AppointmentDetail:
    """Manually cancel an appointment and cancel scheduled reminders."""
    user, business, _, _ = auth_ctx

    stmt = (
        select(Appointment)
        .options(
            selectinload(Appointment.service),
            selectinload(Appointment.reminders),
            selectinload(Appointment.verification_attempts),
        )
        .where(Appointment.id == appointment_id, Appointment.business_id == business.id)
    )
    appointment = (await db.execute(stmt)).scalar_one_or_none()

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment '{appointment_id}' not found.",
        )

    old_status = appointment.status
    appointment.status = "cancelled"
    appointment.updated_at = datetime.now(timezone.utc)

    # Cancel pending reminders
    for r in appointment.reminders:
        if r.status == "pending":
            r.status = "cancelled"

    await record_audit_log(
        db=db,
        business_id=business.id,
        user_id=user.id,
        action="cancel_appointment",
        resource_type="appointment",
        resource_id=str(appointment.id),
        changes={"status": {"old": old_status, "new": "cancelled"}},
        ip_address=request.client.host if request.client else None,
    )
    await db.flush()

    return _build_appointment_detail(appointment)


@router.post("/{appointment_id}/reschedule", response_model=AppointmentDetail)
async def reschedule_appointment_endpoint(
    appointment_id: uuid.UUID,
    payload: AppointmentRescheduleRequest,
    request: Request,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> AppointmentDetail:
    """Reschedule an appointment with double-booking validation."""
    user, business, _, _ = auth_ctx

    stmt = (
        select(Appointment)
        .options(
            selectinload(Appointment.service),
            selectinload(Appointment.reminders),
            selectinload(Appointment.verification_attempts),
        )
        .where(Appointment.id == appointment_id, Appointment.business_id == business.id)
    )
    appointment = (await db.execute(stmt)).scalar_one_or_none()

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment '{appointment_id}' not found.",
        )

    new_start_utc = parse_query_datetime(payload.new_start_time)
    if not new_start_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ISO-8601 new start time format.",
        )

    duration = appointment.service.duration_minutes if appointment.service else 30
    new_end_utc = new_start_utc + timedelta(minutes=duration)

    # Double-booking check: ensure no overlapping active appointments
    overlap_stmt = select(Appointment).where(
        Appointment.business_id == business.id,
        Appointment.id != appointment_id,
        Appointment.status == "booked",
        Appointment.start_at < new_end_utc,
        Appointment.end_at > new_start_utc,
    )
    overlap = (await db.execute(overlap_stmt)).scalars().first()
    if overlap:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Requested time slot is already booked. Please choose another time.",
        )

    old_start = appointment.start_at
    appointment.start_at = new_start_utc
    appointment.end_at = new_end_utc
    appointment.status = "booked"
    appointment.updated_at = datetime.now(timezone.utc)

    # Update reminder send times
    for r in appointment.reminders:
        if r.channel == "email" and r.status in ("pending", "cancelled"):
            r.send_at = new_start_utc - timedelta(hours=24)
            r.status = "pending"

    await record_audit_log(
        db=db,
        business_id=business.id,
        user_id=user.id,
        action="reschedule_appointment",
        resource_type="appointment",
        resource_id=str(appointment.id),
        changes={
            "start_at": {"old": old_start.isoformat(), "new": new_start_utc.isoformat()},
        },
        ip_address=request.client.host if request.client else None,
    )
    await db.flush()

    return _build_appointment_detail(appointment)


def _build_appointment_detail(appointment: Appointment) -> AppointmentDetail:
    """Format an Appointment entity into the AppointmentDetail response model."""
    return AppointmentDetail(
        id=appointment.id,
        service_id=appointment.service_id,
        service_name=appointment.service.name if appointment.service else "Unknown Service",
        service_price=appointment.service.price if appointment.service else 0.0,
        service_duration_minutes=appointment.service.duration_minutes if appointment.service else 0,
        customer_name=appointment.customer_name,
        customer_phone=appointment.customer_phone,
        customer_email=appointment.customer_email,
        start_at=appointment.start_at,
        end_at=appointment.end_at,
        status=appointment.status,
        external_event_id=appointment.external_event_id,
        contact_id=appointment.contact_id,
        call_id=appointment.call_id,
        created_at=appointment.created_at,
        updated_at=appointment.updated_at,
        verification_attempts=[
            {
                "id": str(v.id),
                "phone": v.phone,
                "success": v.success,
                "timestamp": v.timestamp.isoformat(),
            }
            for v in appointment.verification_attempts
        ],
        reminders=[
            {
                "id": str(r.id),
                "send_at": r.send_at.isoformat(),
                "channel": r.channel,
                "status": r.status,
            }
            for r in appointment.reminders
        ],
    )
