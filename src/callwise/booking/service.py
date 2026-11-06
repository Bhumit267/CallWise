"""Booking service: appointment reservation, double-booking prevention, and locking."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import logging
import secrets
from typing import List, Optional
import uuid
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from callwise.config import settings
from callwise.db.models import Appointment, Business, Reminder, Service
from callwise.providers.calendar import CalendarProvider, TimeSlot, get_calendar_provider
from callwise.providers.email import EmailProvider

logger = logging.getLogger(__name__)


class BookingError(Exception):
    """Base exception for all booking-related failures."""
    pass


class BusinessNotFoundError(BookingError):
    """Raised when the specified business does not exist."""
    pass


class ServiceNotFoundError(BookingError):
    """Raised when the requested service does not exist or does not belong to the business."""
    pass


class ServiceInactiveError(BookingError):
    """Raised when the requested service is marked inactive."""
    pass


class PastTimeError(BookingError):
    """Raised when attempting to book a slot in the past."""
    pass


class MinimumNoticeError(BookingError):
    """Raised when the requested time does not meet the minimum advance notice."""
    pass


class OutsideBusinessHoursError(BookingError):
    """Raised when the requested time falls outside operational hours or on a closed day."""
    pass


class DoubleBookingError(BookingError):
    """Raised when the requested slot overlaps with an existing appointment or busy calendar interval."""
    pass


@dataclass
class BookingResult:
    """Outcome of a successful appointment booking."""
    appointment: Appointment
    booking_code: str
    is_duplicate: bool = False


def normalize_booking_code(code: str) -> str:
    """Canonicalize a booking code by stripping spaces, hyphens, and converting to uppercase."""
    return code.strip().upper().replace(" ", "").replace("-", "")


def hash_booking_code(code: str) -> str:
    """Compute SHA-256 hash of the canonicalized booking code."""
    canonical = normalize_booking_code(code)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def generate_booking_code() -> str:
    """
    Generate an unambiguous 6-character booking code (e.g., BK-4X2).
    Uses unconfusable alphanumeric characters (no 0/O or 1/I).
    """
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    suffix = "".join(secrets.choice(alphabet) for _ in range(3))
    return f"BK-{suffix}"


def mask_phone_number(phone: str) -> str:
    """Mask phone number for safe logging (e.g., '***-***-0144')."""
    cleaned = "".join(ch for ch in phone if ch.isdigit())
    if len(cleaned) >= 4:
        return f"***-***-{cleaned[-4:]}"
    return "***"


async def book_appointment(
    session: AsyncSession,
    business_id: uuid.UUID,
    service_id: uuid.UUID,
    start_time: datetime,
    customer_name: str,
    customer_phone: str,
    customer_email: Optional[str] = None,
    call_id: Optional[uuid.UUID] = None,
    calendar_provider: Optional[CalendarProvider] = None,
    email_provider: Optional[EmailProvider] = None,
    reference_now: Optional[datetime] = None,
    min_notice_hours: Optional[int] = None,
    send_notifications: bool = True,
) -> BookingResult:
    """
    Book an appointment with row-level transaction locking to guarantee zero double-booking.

    Args:
        session: Active AsyncSession with an open transaction.
        business_id: UUID of the business tenant.
        service_id: UUID of the bookable service.
        start_time: Requested start datetime (UTC or local).
        customer_name: Full name of the customer.
        customer_phone: Contact phone number.
        customer_email: Optional email address.
        call_id: Optional call session UUID.
        calendar_provider: Optional custom CalendarProvider.
        reference_now: Optional reference current datetime for tests.
        min_notice_hours: Optional override for advance notice hours.

    Returns:
        BookingResult with Appointment record and plaintext booking code.

    Raises:
        BusinessNotFoundError
        ServiceNotFoundError
        ServiceInactiveError
        PastTimeError
        MinimumNoticeError
        OutsideBusinessHoursError
        DoubleBookingError
    """
    if not customer_name or not customer_name.strip():
        raise BookingError("Customer name is required.")
    if not customer_phone or not customer_phone.strip():
        raise BookingError("Customer phone number is required.")

    # 1. Acquire row lock on the business tenant to serialize concurrent booking operations
    biz_stmt = (
        select(Business)
        .where(Business.id == business_id)
        .with_for_update()
    )
    biz_res = await session.execute(biz_stmt)
    business = biz_res.scalar_one_or_none()
    if not business:
        raise BusinessNotFoundError(f"Business not found: {business_id}")

    # 2. Verify service existence and active status
    svc_stmt = (
        select(Service)
        .where(Service.id == service_id, Service.business_id == business_id)
    )
    svc_res = await session.execute(svc_stmt)
    service = svc_res.scalar_one_or_none()
    if not service:
        raise ServiceNotFoundError(f"Service not found: {service_id}")
    if not service.is_active:
        raise ServiceInactiveError(f"Service '{service.name}' is currently inactive.")

    # 3. Resolve timezone and normalize start_time to UTC
    try:
        biz_tz = ZoneInfo(business.timezone)
    except Exception:
        biz_tz = ZoneInfo("UTC")

    if start_time.tzinfo is None:
        start_local = start_time.replace(tzinfo=biz_tz)
        start_utc = start_local.astimezone(timezone.utc)
    else:
        start_utc = start_time.astimezone(timezone.utc)
        start_local = start_utc.astimezone(biz_tz)

    end_utc = start_utc + timedelta(minutes=service.duration_minutes)
    end_local = end_utc.astimezone(biz_tz)

    # 4. Advance notice and past time validation
    now_utc = reference_now if reference_now is not None else datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    if start_utc <= now_utc:
        raise PastTimeError("Cannot book appointments in the past.")

    notice_hours = (
        min_notice_hours
        if min_notice_hours is not None
        else settings.min_booking_notice_hours
    )
    earliest_allowed = now_utc + timedelta(hours=notice_hours)
    if start_utc < earliest_allowed:
        raise MinimumNoticeError(
            f"Appointments require at least {notice_hours} hours advance notice."
        )

    # 5. Business hours and open days validation
    target_date = start_local.date()
    weekday_key = target_date.strftime("%A").lower()
    day_cfg = (business.hours or {}).get(weekday_key)

    if not day_cfg or day_cfg.get("closed", False):
        raise OutsideBusinessHoursError(
            f"{business.name} is closed on {target_date.strftime('%A')}s."
        )

    open_str = day_cfg.get("open")
    close_str = day_cfg.get("close")
    if not open_str or not close_str:
        raise OutsideBusinessHoursError(
            f"No valid operating hours configured for {target_date.strftime('%A')}."
        )

    try:
        open_h, open_m = map(int, open_str.split(":"))
        close_h, close_m = map(int, close_str.split(":"))
    except ValueError:
        raise OutsideBusinessHoursError("Malformed operating hours configuration.")

    day_open_local = datetime(
        target_date.year, target_date.month, target_date.day, open_h, open_m, tzinfo=biz_tz
    )

    if (close_h == 0 and close_m == 0) or close_str == "24:00":
        day_close_local = datetime(
            target_date.year, target_date.month, target_date.day, 0, 0, tzinfo=biz_tz
        ) + timedelta(days=1)
    elif (close_h, close_m) < (open_h, open_m):
        day_close_local = datetime(
            target_date.year, target_date.month, target_date.day, close_h, close_m, tzinfo=biz_tz
        ) + timedelta(days=1)
    else:
        day_close_local = datetime(
            target_date.year, target_date.month, target_date.day, close_h, close_m, tzinfo=biz_tz
        )

    if start_local < day_open_local or end_local > day_close_local:
        raise OutsideBusinessHoursError(
            f"Requested slot {start_local.strftime('%H:%M')} - {end_local.strftime('%H:%M')} "
            f"is outside business hours ({open_str} - {close_str} {business.timezone})."
        )

    # 6. Idempotency check: if caller re-requests same appointment in the same call session
    if call_id is not None:
        idem_stmt = select(Appointment).where(
            Appointment.business_id == business_id,
            Appointment.call_id == call_id,
            Appointment.customer_phone == customer_phone.strip(),
            Appointment.start_at == start_utc,
            Appointment.status == "booked",
        )
        existing = (await session.execute(idem_stmt)).scalar_one_or_none()
        if existing:
            logger.info(
                f"Idempotent booking hit for call {call_id}, returning existing appointment {existing.id}"
            )
            return BookingResult(
                appointment=existing,
                booking_code="[EXISTING]",
                is_duplicate=True,
            )

    # 7. Check for overlapping booked appointments in database
    overlap_stmt = select(Appointment).where(
        Appointment.business_id == business_id,
        Appointment.status == "booked",
        Appointment.start_at < end_utc,
        Appointment.end_at > start_utc,
    )
    overlap_appts = (await session.execute(overlap_stmt)).scalars().all()
    if overlap_appts:
        raise DoubleBookingError(
            "Selected time slot is already booked. Please choose another time."
        )

    # 8. Check for overlapping busy intervals in CalendarProvider
    provider = calendar_provider or get_calendar_provider()
    busy_slots = provider.get_busy_times(business_id, start_utc, end_utc)
    candidate_slot = TimeSlot(start_at=start_utc, end_at=end_utc)
    if any(candidate_slot.overlaps(b) for b in busy_slots):
        raise DoubleBookingError(
            "Selected time slot conflicts with an existing calendar commitment."
        )

    # 9. Generate booking code and hash (never store plain code in DB)
    code = generate_booking_code()
    code_hash = hash_booking_code(code)

    # 10. Create event in calendar provider
    masked_phone = mask_phone_number(customer_phone)
    event_title = f"{service.name} - {customer_name.strip()}"
    event_desc = (
        f"Service: {service.name}\n"
        f"Customer: {customer_name.strip()}\n"
        f"Phone: {masked_phone}\n"
        f"Email: {customer_email.strip() if customer_email else 'N/A'}"
    )
    external_event_id = provider.create_event(
        business_id=business_id,
        title=event_title,
        start_time=start_utc,
        end_time=end_utc,
        description=event_desc,
    )

    # 11. Persist Appointment record
    appointment = Appointment(
        business_id=business_id,
        service_id=service_id,
        customer_name=customer_name.strip(),
        customer_phone=customer_phone.strip(),
        customer_email=customer_email.strip() if customer_email else None,
        start_at=start_utc,
        end_at=end_utc,
        status="booked",
        booking_code_hash=code_hash,
        external_event_id=external_event_id,
        call_id=call_id,
    )
    session.add(appointment)
    await session.flush()
    await session.refresh(appointment)

    # 12. Create scheduled reminders:
    # A. 24-hour advance email reminder (if customer email provided)
    if customer_email and customer_email.strip():
        email_reminder_time = start_utc - timedelta(hours=24)
        email_reminder = Reminder(
            business_id=business_id,
            appointment_id=appointment.id,
            send_at=email_reminder_time,
            channel="email",
            status="pending",
        )
        session.add(email_reminder)

    # B. 2-hour advance automated phone call reminder to customer_phone
    call_reminder_time = start_utc - timedelta(hours=2)
    call_reminder = Reminder(
        business_id=business_id,
        appointment_id=appointment.id,
        send_at=call_reminder_time,
        channel="call",
        status="pending",
    )
    session.add(call_reminder)
    await session.flush()

    logger.info(
        f"Booked appointment {appointment.id} for {customer_name.strip()} ({masked_phone}) "
        f"at {start_utc.isoformat()} [Code Hash: {code_hash[:8]}...]"
    )

    if send_notifications:
        try:
            from callwise.notifications.service import notify_booking
            await notify_booking(
                session=session,
                business=business,
                appointment=appointment,
                service=service,
                booking_code=code,
                email_provider=email_provider,
            )
        except Exception as exc:
            logger.error(f"Error dispatching booking notifications: {exc}")

    return BookingResult(
        appointment=appointment,
        booking_code=code,
        is_duplicate=False,
    )


async def list_appointments(
    session: AsyncSession,
    business_id: uuid.UUID,
    status: Optional[str] = None,
) -> List[Appointment]:
    """Retrieve appointments for a business tenant, optionally filtered by status."""
    stmt = (
        select(Appointment)
        .where(Appointment.business_id == business_id)
        .order_by(Appointment.start_at.asc())
    )
    if status:
        stmt = stmt.where(Appointment.status == status.strip().lower())

    result = await session.execute(stmt)
    return list(result.scalars().all())

