"""Appointments API router: list appointments, calendar range fetch, and full detail view."""

from datetime import datetime
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
from callwise.db.models import (
    Appointment,
    Business,
    Reminder,
    Service,
    Session as UserSession,
    User,
    VerificationAttempt,
)

router = APIRouter(prefix="/appointments", tags=["Appointments"])


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

    return AppointmentDetail(
        id=appointment.id,
        service_id=appointment.service_id,
        service_name=appointment.service.name if appointment.service else "Unknown Service",
        service_price=appointment.service.price if appointment.service else 0.0,
        service_duration_minutes=appointment.service.duration_minutes if appointment.service else 0,
        customer_name=appointment.customer_name,
        customer_phone=appointment.customer_phone,  # Unmasked in detail view
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
