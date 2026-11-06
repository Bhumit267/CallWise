"""Tests for caller verification, appointment cancellation, rescheduling, and lockout."""

from datetime import datetime, timedelta, timezone
import uuid
import pytest
from sqlalchemy import select

from callwise.booking.service import (
    DoubleBookingError,
    MinimumNoticeError,
    OutsideBusinessHoursError,
    PastTimeError,
    book_appointment,
)
from callwise.booking.verification import (
    AppointmentAlreadyCancelledError,
    AppointmentNotFoundError,
    VerificationFailedError,
    VerificationLockoutError,
    cancel_appointment,
    name_matches,
    normalize_phone,
    phone_matches,
    reschedule_appointment,
    verify_caller,
)
from callwise.db.models import Appointment, Business, Call, Service, VerificationAttempt
from callwise.db.session import AsyncSessionLocal


def test_phone_and_name_matching():
    """Verify robust phone and name comparison functions."""
    assert normalize_phone("+1 (555) 234-5678") == "15552345678"
    assert normalize_phone("555-0144") == "5550144"

    # Phone matches
    assert phone_matches("555-0144", "555-0144") is True
    assert phone_matches("(555) 0144", "555-0144") is True
    assert phone_matches("+15550144", "555-0144") is True
    assert phone_matches("555-0144", "555-9999") is False
    assert phone_matches(None, "555-0144") is False

    # Name matches
    assert name_matches("Sarah Connor", "Sarah Connor") is True
    assert name_matches("sarah", "Sarah Connor") is True
    assert name_matches("Connor", "Sarah Connor") is True
    assert name_matches("Sarah Jane Connor", "Sarah Connor") is True
    assert name_matches("Kyle Reese", "Sarah Connor") is False
    assert name_matches(None, "Sarah Connor") is False


@pytest.mark.asyncio
async def test_caller_verification_success_and_audit():
    """Verify caller with correct booking code and phone/name records success in audit table."""
    biz_id = uuid.uuid4()
    svc_id = uuid.uuid4()
    call_id = uuid.uuid4()
    test_hours = {
        "monday": {"open": "09:00", "close": "17:00", "closed": False},
    }

    async with AsyncSessionLocal() as session:
        async with session.begin():
            biz = Business(
                id=biz_id,
                name="Verify Dental",
                business_type="Dental",
                greeting="Welcome to Verify Dental",
                timezone="America/New_York",
                hours=test_hours,
            )
            svc = Service(
                id=svc_id,
                business_id=biz_id,
                name="Consult",
                duration_minutes=30,
                price=50.0,
                is_active=True,
            )
            call = Call(id=call_id, business_id=biz_id, caller_number="555-0123")
            session.add_all([biz, svc, call])

    ref_now = datetime(2026, 11, 16, 10, 0, tzinfo=timezone.utc)
    start_time = datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)

    # 1. Book initial appointment
    async with AsyncSessionLocal() as session:
        async with session.begin():
            res = await book_appointment(
                session=session,
                business_id=biz_id,
                service_id=svc_id,
                start_time=start_time,
                customer_name="John Matrix",
                customer_phone="555-0123",
                call_id=call_id,
                reference_now=ref_now,
                min_notice_hours=2,
            )
            booking_code = res.booking_code

    # 2. Verify with matching phone
    async with AsyncSessionLocal() as session:
        async with session.begin():
            verified = await verify_caller(
                session=session,
                business_id=biz_id,
                booking_code=booking_code,
                caller_phone="555-0123",
                call_id=call_id,
            )
            assert verified.id == res.appointment.id

    # 3. Verify with matching name
    async with AsyncSessionLocal() as session:
        async with session.begin():
            verified2 = await verify_caller(
                session=session,
                business_id=biz_id,
                booking_code=booking_code.lower(),  # test lowercase normalization
                caller_name="Matrix",
                call_id=call_id,
            )
            assert verified2.id == res.appointment.id

    # Verify audit attempts in DB
    async with AsyncSessionLocal() as session:
        stmt = select(VerificationAttempt).where(
            VerificationAttempt.business_id == biz_id,
            VerificationAttempt.appointment_id == res.appointment.id,
        )
        attempts = (await session.execute(stmt)).scalars().all()
        assert len(attempts) == 2
        assert all(a.success is True for a in attempts)


@pytest.mark.asyncio
async def test_verification_lockout_after_three_failures():
    """Verify that 3 failed attempts in the same call session trigger a strict security lockout."""
    biz_id = uuid.uuid4()
    svc_id = uuid.uuid4()
    call_id = uuid.uuid4()
    test_hours = {
        "monday": {"open": "09:00", "close": "17:00", "closed": False},
    }

    async with AsyncSessionLocal() as session:
        async with session.begin():
            biz = Business(
                id=biz_id,
                name="Security Dental",
                business_type="Dental",
                greeting="Welcome to Security Dental",
                timezone="America/New_York",
                hours=test_hours,
            )
            svc = Service(
                id=svc_id,
                business_id=biz_id,
                name="Consult",
                duration_minutes=30,
                price=50.0,
                is_active=True,
            )
            call = Call(id=call_id, business_id=biz_id, caller_number="555-0199")
            session.add_all([biz, svc, call])

    ref_now = datetime(2026, 11, 16, 10, 0, tzinfo=timezone.utc)
    start_time = datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)

    # Book appointment
    async with AsyncSessionLocal() as session:
        async with session.begin():
            res = await book_appointment(
                session=session,
                business_id=biz_id,
                service_id=svc_id,
                start_time=start_time,
                customer_name="Dana Scully",
                customer_phone="555-0199",
                call_id=call_id,
                reference_now=ref_now,
                min_notice_hours=2,
            )
            booking_code = res.booking_code

    # Attempt 1: Wrong booking code -> AppointmentNotFoundError (2 attempts remaining)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            with pytest.raises(AppointmentNotFoundError, match="2 attempt"):
                await verify_caller(
                    session=session,
                    business_id=biz_id,
                    booking_code="BK-999",
                    caller_phone="555-0199",
                    call_id=call_id,
                )

    # Attempt 2: Correct code, but wrong name & wrong phone -> VerificationFailedError (1 attempt remaining)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            with pytest.raises(VerificationFailedError, match="1 attempt"):
                await verify_caller(
                    session=session,
                    business_id=biz_id,
                    booking_code=booking_code,
                    caller_name="Impostor",
                    caller_phone="555-0000",
                    call_id=call_id,
                )

    # Attempt 3: Wrong details again -> Triggers VerificationLockoutError!
    async with AsyncSessionLocal() as session:
        async with session.begin():
            with pytest.raises(VerificationLockoutError, match="Maximum of 3 attempts exceeded"):
                await verify_caller(
                    session=session,
                    business_id=biz_id,
                    booking_code=booking_code,
                    caller_name="Wrong Person",
                    call_id=call_id,
                )

    # Attempt 4: Even with CORRECT credentials, the call is now locked out!
    async with AsyncSessionLocal() as session:
        async with session.begin():
            with pytest.raises(VerificationLockoutError, match="exceeded the maximum of 3 failed verification attempts"):
                await verify_caller(
                    session=session,
                    business_id=biz_id,
                    booking_code=booking_code,
                    caller_name="Dana Scully",
                    caller_phone="555-0199",
                    call_id=call_id,
                )


@pytest.mark.asyncio
async def test_cancel_appointment_workflow():
    """Verify successful appointment cancellation and rejection of duplicate cancellation."""
    biz_id = uuid.uuid4()
    svc_id = uuid.uuid4()
    test_hours = {
        "tuesday": {"open": "09:00", "close": "17:00", "closed": False},
    }

    async with AsyncSessionLocal() as session:
        async with session.begin():
            biz = Business(
                id=biz_id,
                name="Cancellation Dental",
                business_type="Dental",
                greeting="Welcome to Dental",
                timezone="America/New_York",
                hours=test_hours,
            )
            svc = Service(
                id=svc_id,
                business_id=biz_id,
                name="Checkup",
                duration_minutes=30,
                price=75.0,
                is_active=True,
            )
            session.add_all([biz, svc])

    ref_now = datetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc)
    start_time = datetime(2026, 11, 17, 15, 0, tzinfo=timezone.utc)

    # Book appointment
    async with AsyncSessionLocal() as session:
        async with session.begin():
            res = await book_appointment(
                session=session,
                business_id=biz_id,
                service_id=svc_id,
                start_time=start_time,
                customer_name="Fox Mulder",
                customer_phone="555-0188",
                reference_now=ref_now,
                min_notice_hours=2,
            )
            booking_code = res.booking_code

    # Cancel appointment
    async with AsyncSessionLocal() as session:
        async with session.begin():
            cancelled = await cancel_appointment(
                session=session,
                business_id=biz_id,
                booking_code=booking_code,
                caller_phone="555-0188",
            )
            assert cancelled.status == "cancelled"

    # Verify status in database
    async with AsyncSessionLocal() as session:
        db_appt = await session.get(Appointment, res.appointment.id)
        assert db_appt.status == "cancelled"

    # Attempt to cancel again -> AppointmentAlreadyCancelledError
    async with AsyncSessionLocal() as session:
        async with session.begin():
            with pytest.raises(AppointmentAlreadyCancelledError):
                await cancel_appointment(
                    session=session,
                    business_id=biz_id,
                    booking_code=booking_code,
                    caller_name="Fox Mulder",
                )


@pytest.mark.asyncio
async def test_reschedule_appointment_workflow():
    """Verify appointment rescheduling updates start/end time and prevents conflicts."""
    biz_id = uuid.uuid4()
    svc_id = uuid.uuid4()
    test_hours = {
        "wednesday": {"open": "09:00", "close": "17:00", "closed": False},
    }

    async with AsyncSessionLocal() as session:
        async with session.begin():
            biz = Business(
                id=biz_id,
                name="Reschedule Dental",
                business_type="Dental",
                greeting="Welcome to Reschedule Dental",
                timezone="America/New_York",
                hours=test_hours,
            )
            svc = Service(
                id=svc_id,
                business_id=biz_id,
                name="Cleaning",
                duration_minutes=60,
                price=120.0,
                is_active=True,
            )
            session.add_all([biz, svc])

    ref_now = datetime(2026, 11, 18, 10, 0, tzinfo=timezone.utc)
    original_start = datetime(2026, 11, 18, 15, 0, tzinfo=timezone.utc)

    # Book appointment
    async with AsyncSessionLocal() as session:
        async with session.begin():
            res = await book_appointment(
                session=session,
                business_id=biz_id,
                service_id=svc_id,
                start_time=original_start,
                customer_name="Luke Skywalker",
                customer_phone="555-0177",
                reference_now=ref_now,
                min_notice_hours=2,
            )
            booking_code = res.booking_code

    # Reschedule to 17:00 UTC (12:00 PM NY)
    new_start = datetime(2026, 11, 18, 17, 0, tzinfo=timezone.utc)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            rescheduled = await reschedule_appointment(
                session=session,
                business_id=biz_id,
                booking_code=booking_code,
                new_start_time=new_start,
                caller_name="Luke",
                reference_now=ref_now,
                min_notice_hours=2,
            )
            assert rescheduled.start_at == new_start
            assert rescheduled.end_at == new_start + timedelta(minutes=60)
            assert rescheduled.status == "booked"

    # Verify the old time slot (15:00 UTC) is now freed up for another booking!
    async with AsyncSessionLocal() as session:
        async with session.begin():
            rebook = await book_appointment(
                session=session,
                business_id=biz_id,
                service_id=svc_id,
                start_time=original_start,
                customer_name="Leia Organa",
                customer_phone="555-0166",
                reference_now=ref_now,
                min_notice_hours=2,
            )
            assert rebook.appointment.status == "booked"
            assert rebook.appointment.customer_name == "Leia Organa"

