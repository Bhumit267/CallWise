"""Caller verification, cancellation, and rescheduling engine with strict 3-attempt lockout."""

from datetime import datetime, timedelta, timezone
import logging
from typing import Optional
import uuid
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from callwise.booking.service import (
    DoubleBookingError,
    MinimumNoticeError,
    OutsideBusinessHoursError,
    PastTimeError,
    hash_booking_code,
    mask_phone_number,
)
from callwise.config import settings
from callwise.db.models import Appointment, Business, Service, VerificationAttempt
from callwise.providers.calendar import CalendarProvider, TimeSlot, get_calendar_provider
from callwise.providers.email import EmailProvider

logger = logging.getLogger(__name__)


class VerificationError(Exception):
    """Base exception for appointment verification and modification failures."""
    pass


class AppointmentNotFoundError(VerificationError):
    """Raised when an appointment matching the booking code does not exist."""
    pass


class VerificationFailedError(VerificationError):
    """Raised when caller identity (phone or name) does not match the appointment."""

    def __init__(self, message: str, remaining_attempts: int = 0):
        super().__init__(message)
        self.remaining_attempts = remaining_attempts


class VerificationLockoutError(VerificationError):
    """Raised when 3 failed verification attempts occur in the same call session."""
    pass


class AppointmentAlreadyCancelledError(VerificationError):
    """Raised when attempting to cancel or reschedule an already cancelled appointment."""
    pass


def normalize_phone(phone: str) -> str:
    """Extract digits only for canonical phone number comparison."""
    return "".join(ch for ch in phone if ch.isdigit())


def phone_matches(phone1: Optional[str], phone2: Optional[str]) -> bool:
    """
    Compare two phone numbers by normalized digits.
    Matches if exact, or if the last 10 digits match, or if the last 7 digits match.
    """
    if not phone1 or not phone2:
        return False
    p1 = normalize_phone(phone1)
    p2 = normalize_phone(phone2)
    if not p1 or not p2:
        return False
    if p1 == p2:
        return True
    if len(p1) >= 10 and len(p2) >= 10 and p1[-10:] == p2[-10:]:
        return True
    if len(p1) >= 7 and len(p2) >= 7 and p1[-7:] == p2[-7:]:
        return True
    return False


def name_matches(name1: Optional[str], name2: Optional[str]) -> bool:
    """
    Compare two names case-insensitively, allowing token overlap or substring match.
    """
    if not name1 or not name2:
        return False
    n1 = name1.strip().lower()
    n2 = name2.strip().lower()
    if not n1 or not n2:
        return False
    if n1 == n2:
        return True
    tokens1 = set(n1.split())
    tokens2 = set(n2.split())
    if tokens1 & tokens2:
        return True
    return n1 in n2 or n2 in n1


async def verify_caller(
    session: AsyncSession,
    business_id: uuid.UUID,
    booking_code: str,
    caller_name: Optional[str] = None,
    caller_phone: Optional[str] = None,
    call_id: Optional[uuid.UUID] = None,
) -> Appointment:
    """
    Verify caller identity against an appointment using booking code hash + name or phone.
    Enforces a strict 3-attempt lockout per call session.

    Args:
        session: Active AsyncSession.
        business_id: Business tenant UUID.
        booking_code: Plaintext booking code provided by caller (e.g. 'BK-4X2').
        caller_name: Caller full or partial name.
        caller_phone: Caller phone number.
        call_id: Optional active call session UUID for lockout auditing.

    Returns:
        Verified Appointment record.

    Raises:
        VerificationLockoutError: If 3 failed attempts have occurred in this call.
        AppointmentNotFoundError: If code does not match any appointment for this business.
        VerificationFailedError: If phone and name do not match appointment.
    """
    # 1. Check for lockout in the current call session
    failed_count = 0
    if call_id is not None:
        failed_count_stmt = select(func.count(VerificationAttempt.id)).where(
            VerificationAttempt.business_id == business_id,
            VerificationAttempt.call_id == call_id,
            VerificationAttempt.success.is_(False),
        )
        failed_count = (await session.execute(failed_count_stmt)).scalar() or 0
        if failed_count >= 3:
            raise VerificationLockoutError(
                "This call has exceeded the maximum of 3 failed verification attempts. "
                "For your security, modifications are locked for this call. "
                "Please speak with staff or call back."
            )

    code_hash = hash_booking_code(booking_code)

    # 2. Look up appointment by business_id and booking_code_hash
    stmt = select(Appointment).where(
        Appointment.business_id == business_id,
        Appointment.booking_code_hash == code_hash,
    )
    appointment = (await session.execute(stmt)).scalar_one_or_none()

    # 3. Evaluate identity match (booking code + caller phone OR caller name)
    is_valid = False
    if appointment is not None:
        has_phone_match = phone_matches(caller_phone, appointment.customer_phone)
        has_name_match = name_matches(caller_name, appointment.customer_name)
        if has_phone_match or has_name_match:
            is_valid = True

    # 4. Handle failure and record failed attempt
    if not is_valid:
        attempt = VerificationAttempt(
            business_id=business_id,
            appointment_id=appointment.id if appointment else None,
            phone=caller_phone,
            call_id=call_id,
            success=False,
        )
        session.add(attempt)
        await session.flush()

        new_failed = failed_count + 1
        remaining = max(0, 3 - new_failed)

        if new_failed >= 3 and call_id is not None:
            logger.warning(
                f"Call {call_id} locked out after 3 failed verification attempts for business {business_id}."
            )
            raise VerificationLockoutError(
                "Verification failed. Maximum of 3 attempts exceeded. "
                "Modifications are locked for this call. Please speak with staff."
            )

        if appointment is None:
            raise AppointmentNotFoundError(
                f"No appointment found with that booking code. ({remaining} attempt(s) remaining)."
            )

        raise VerificationFailedError(
            f"Verification details did not match the appointment on file. ({remaining} attempt(s) remaining).",
            remaining_attempts=remaining,
        )

    # 5. Success: record verified attempt
    attempt = VerificationAttempt(
        business_id=business_id,
        appointment_id=appointment.id,
        phone=caller_phone,
        call_id=call_id,
        success=True,
    )
    session.add(attempt)
    await session.flush()

    logger.info(
        f"Verified caller for appointment {appointment.id} ({mask_phone_number(appointment.customer_phone)})"
    )
    return appointment


async def cancel_appointment(
    session: AsyncSession,
    business_id: uuid.UUID,
    booking_code: str,
    caller_name: Optional[str] = None,
    caller_phone: Optional[str] = None,
    call_id: Optional[uuid.UUID] = None,
    calendar_provider: Optional[CalendarProvider] = None,
    email_provider: Optional[EmailProvider] = None,
    send_notifications: bool = True,
) -> Appointment:
    """
    Cancel an appointment after successful caller verification.
    Updates status to 'cancelled' and removes the event from CalendarProvider.

    Args:
        session: Active AsyncSession.
        business_id: Business tenant UUID.
        booking_code: Plaintext booking code.
        caller_name: Caller name for verification.
        caller_phone: Caller phone for verification.
        call_id: Call session UUID.
        calendar_provider: Optional CalendarProvider.
        email_provider: Optional EmailProvider for dispatching cancel alerts.
        send_notifications: Whether to dispatch cancellation emails.

    Returns:
        Updated Appointment record with status='cancelled'.
    """
    # Verify caller and retrieve appointment
    appointment = await verify_caller(
        session=session,
        business_id=business_id,
        booking_code=booking_code,
        caller_name=caller_name,
        caller_phone=caller_phone,
        call_id=call_id,
    )

    if appointment.status == "cancelled":
        raise AppointmentAlreadyCancelledError("This appointment is already cancelled.")

    appointment.status = "cancelled"

    # Remove event from external / local calendar
    if appointment.external_event_id:
        provider = calendar_provider or get_calendar_provider()
        try:
            provider.delete_event(
                business_id=business_id,
                event_id=appointment.external_event_id,
            )
        except Exception as exc:
            logger.warning(
                f"Failed to delete calendar event {appointment.external_event_id}: {exc}"
            )

    await session.flush()
    await session.refresh(appointment)

    logger.info(
        f"Cancelled appointment {appointment.id} for {appointment.customer_name} "
        f"({mask_phone_number(appointment.customer_phone)})"
    )

    if send_notifications:
        try:
            biz_stmt = select(Business).where(Business.id == business_id)
            biz = (await session.execute(biz_stmt)).scalar_one_or_none()
            svc_stmt = select(Service).where(Service.id == appointment.service_id)
            svc = (await session.execute(svc_stmt)).scalar_one_or_none()
            if biz and svc:
                from callwise.notifications.service import notify_cancellation
                await notify_cancellation(
                    session=session,
                    business=biz,
                    appointment=appointment,
                    service=svc,
                    email_provider=email_provider,
                )
        except Exception as exc:
            logger.error(f"Error dispatching cancellation notifications: {exc}")

    return appointment


async def reschedule_appointment(
    session: AsyncSession,
    business_id: uuid.UUID,
    booking_code: str,
    new_start_time: datetime,
    caller_name: Optional[str] = None,
    caller_phone: Optional[str] = None,
    call_id: Optional[uuid.UUID] = None,
    calendar_provider: Optional[CalendarProvider] = None,
    email_provider: Optional[EmailProvider] = None,
    reference_now: Optional[datetime] = None,
    min_notice_hours: Optional[int] = None,
    send_notifications: bool = True,
) -> Appointment:
    """
    Reschedule an appointment to a new verified time slot after caller verification.
    Guarantees no double-booking using row-level locking on the business tenant.

    Args:
        session: Active AsyncSession.
        business_id: Business tenant UUID.
        booking_code: Plaintext booking code.
        new_start_time: Requested new start datetime.
        caller_name: Caller name for verification.
        caller_phone: Caller phone for verification.
        call_id: Call session UUID.
        calendar_provider: Optional CalendarProvider.
        reference_now: Optional reference now datetime for tests.
        min_notice_hours: Optional advance notice override.

    Returns:
        Updated Appointment with new start_at and end_at.
    """
    # 1. Lock business tenant to serialize concurrent modifications
    biz_stmt = select(Business).where(Business.id == business_id).with_for_update()
    business = (await session.execute(biz_stmt)).scalar_one_or_none()
    if not business:
        raise VerificationError(f"Business not found: {business_id}")

    # 2. Verify caller identity
    appointment = await verify_caller(
        session=session,
        business_id=business_id,
        booking_code=booking_code,
        caller_name=caller_name,
        caller_phone=caller_phone,
        call_id=call_id,
    )

    if appointment.status == "cancelled":
        raise AppointmentAlreadyCancelledError("Cannot reschedule a cancelled appointment.")

    # 3. Retrieve service duration
    svc_stmt = select(Service).where(Service.id == appointment.service_id)
    service = (await session.execute(svc_stmt)).scalar_one_or_none()
    if not service:
        raise VerificationError(f"Service not found for appointment {appointment.id}")

    # 4. Resolve timezone and normalize new_start_time to UTC
    try:
        biz_tz = ZoneInfo(business.timezone)
    except Exception:
        biz_tz = ZoneInfo("UTC")

    if new_start_time.tzinfo is None:
        start_local = new_start_time.replace(tzinfo=biz_tz)
        new_start_utc = start_local.astimezone(timezone.utc)
    else:
        new_start_utc = new_start_time.astimezone(timezone.utc)
        start_local = new_start_utc.astimezone(biz_tz)

    new_end_utc = new_start_utc + timedelta(minutes=service.duration_minutes)
    end_local = new_end_utc.astimezone(biz_tz)

    # 5. Advance notice and past time validation
    now_utc = reference_now if reference_now is not None else datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    if new_start_utc <= now_utc:
        raise PastTimeError("Cannot reschedule an appointment to the past.")

    notice_hours = (
        min_notice_hours
        if min_notice_hours is not None
        else settings.min_booking_notice_hours
    )
    earliest_allowed = now_utc + timedelta(hours=notice_hours)
    if new_start_utc < earliest_allowed:
        raise MinimumNoticeError(
            f"Rescheduled appointments require at least {notice_hours} hours advance notice."
        )

    # 6. Operating hours validation
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

    # 7. Check for overlapping booked appointments (excluding this appointment itself)
    overlap_stmt = select(Appointment).where(
        Appointment.business_id == business_id,
        Appointment.status == "booked",
        Appointment.id != appointment.id,
        Appointment.start_at < new_end_utc,
        Appointment.end_at > new_start_utc,
    )
    overlap_appts = (await session.execute(overlap_stmt)).scalars().all()
    if overlap_appts:
        raise DoubleBookingError(
            "Selected new time slot is already booked. Please choose another time."
        )

    # 8. Check calendar provider busy slots
    provider = calendar_provider or get_calendar_provider()
    busy_slots = provider.get_busy_times(business_id, new_start_utc, new_end_utc)
    candidate_slot = TimeSlot(start_at=new_start_utc, end_at=new_end_utc)
    # Check if busy slots conflict (ignore overlap if it matches this appointment's current slot)
    for b in busy_slots:
        if candidate_slot.overlaps(b):
            if b.start_at == appointment.start_at and b.end_at == appointment.end_at:
                continue
            raise DoubleBookingError(
                "Selected new time slot conflicts with an existing calendar commitment."
            )

    # 9. Update calendar provider event
    if appointment.external_event_id:
        try:
            provider.update_event(
                business_id=business_id,
                event_id=appointment.external_event_id,
                start_time=new_start_utc,
                end_time=new_end_utc,
                title=f"{service.name} - {appointment.customer_name}",
            )
        except Exception as exc:
            logger.warning(
                f"Failed to update calendar event {appointment.external_event_id}: {exc}"
            )

    # 10. Update appointment record
    old_start_utc = appointment.start_at
    appointment.start_at = new_start_utc
    appointment.end_at = new_end_utc
    appointment.status = "booked"

    await session.flush()
    await session.refresh(appointment)

    logger.info(
        f"Rescheduled appointment {appointment.id} for {appointment.customer_name} "
        f"to {new_start_utc.isoformat()} (UTC)"
    )

    if send_notifications:
        try:
            from callwise.notifications.service import notify_reschedule
            await notify_reschedule(
                session=session,
                business=business,
                appointment=appointment,
                service=service,
                old_start_utc=old_start_utc,
                new_start_utc=new_start_utc,
                email_provider=email_provider,
            )
        except Exception as exc:
            logger.error(f"Error dispatching reschedule notifications: {exc}")

    return appointment

