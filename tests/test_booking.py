"""Tests for appointment booking service, validation rules, and concurrency protection."""

import asyncio
from datetime import datetime, timedelta, timezone
import uuid
import pytest
from sqlalchemy import select

from callwise.booking.service import (
    BookingError,
    DoubleBookingError,
    MinimumNoticeError,
    OutsideBusinessHoursError,
    PastTimeError,
    ServiceInactiveError,
    ServiceNotFoundError,
    book_appointment,
    generate_booking_code,
    hash_booking_code,
    list_appointments,
    mask_phone_number,
    normalize_booking_code,
)
from callwise.db.models import Appointment, Business, Call, Service
from callwise.db.session import AsyncSessionLocal


def test_booking_code_helpers():
    """Verify booking code formatting, canonicalization, and SHA-256 hashing."""
    code = generate_booking_code()
    assert code.startswith("BK-")
    assert len(code) == 6

    # Verify normalization handles case, hyphens, and spaces
    assert normalize_booking_code("BK-4X2") == "BK4X2"
    assert normalize_booking_code("bk-4x2") == "BK4X2"
    assert normalize_booking_code("bk 4x2") == "BK4X2"
    assert normalize_booking_code("bk4x2") == "BK4X2"

    # Hashes must match across equivalent caller representations
    h1 = hash_booking_code("BK-4X2")
    h2 = hash_booking_code("bk4x2")
    h3 = hash_booking_code("BK 4X2")
    assert h1 == h2 == h3
    assert len(h1) == 64  # SHA-256 hex length


def test_mask_phone_number():
    """Verify phone masking never logs the full phone number."""
    assert mask_phone_number("555-0144") == "***-***-0144"
    assert mask_phone_number("+1 (555) 234-5678") == "***-***-5678"
    assert mask_phone_number("12") == "***"


@pytest.mark.asyncio
async def test_book_appointment_success():
    """Verify successful appointment booking with valid future slot, calendar event, and code hash."""
    biz_id = uuid.uuid4()
    svc_id = uuid.uuid4()
    test_hours = {
        "wednesday": {"open": "08:00", "close": "17:00", "closed": False},
    }

    async with AsyncSessionLocal() as session:
        async with session.begin():
            biz = Business(
                id=biz_id,
                name="Test Apex Dental",
                business_type="Dental",
                greeting="Welcome to Test Apex Dental",
                timezone="America/New_York",
                hours=test_hours,
            )
            svc = Service(
                id=svc_id,
                business_id=biz_id,
                name="Routine Checkup",
                duration_minutes=45,
                price=110.0,
                is_active=True,
            )
            session.add_all([biz, svc])

    # Reference time: Wednesday 2026-11-18 at 08:00 UTC (03:00 AM NY)
    ref_now = datetime(2026, 11, 18, 8, 0, tzinfo=timezone.utc)
    # Requested booking time: Wednesday 2026-11-18 at 15:00 UTC (10:00 AM NY - within 8am-5pm hours)
    start_time = datetime(2026, 11, 18, 15, 0, tzinfo=timezone.utc)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await book_appointment(
                session=session,
                business_id=biz_id,
                service_id=svc_id,
                start_time=start_time,
                customer_name="Alice Smith",
                customer_phone="555-0199",
                customer_email="alice@example.com",
                reference_now=ref_now,
                min_notice_hours=2,
            )

    assert result.appointment is not None
    assert result.appointment.status == "booked"
    assert result.appointment.customer_name == "Alice Smith"
    assert result.appointment.customer_phone == "555-0199"
    assert result.appointment.customer_email == "alice@example.com"
    assert result.appointment.start_at == start_time
    assert result.appointment.end_at == start_time + timedelta(minutes=45)
    assert result.booking_code.startswith("BK-")
    assert result.is_duplicate is False

    # Check hash stored in DB matches the plaintext booking code
    assert result.appointment.booking_code_hash == hash_booking_code(result.booking_code)
    assert result.appointment.external_event_id is not None
    assert result.appointment.external_event_id.startswith("local_")


@pytest.mark.asyncio
async def test_book_appointment_rejections():
    """Verify rejections for past times, minimum notice, closed days, and out-of-hours."""
    biz_id = uuid.uuid4()
    svc_id = uuid.uuid4()
    test_hours = {
        "monday": {"open": "09:00", "close": "17:00", "closed": False},
        "sunday": {"closed": True},
    }

    async with AsyncSessionLocal() as session:
        async with session.begin():
            biz = Business(
                id=biz_id,
                name="Strict Dental",
                business_type="Dental",
                greeting="Welcome to Strict Dental",
                timezone="America/New_York",
                hours=test_hours,
            )
            svc = Service(
                id=svc_id,
                business_id=biz_id,
                name="Cleaning",
                duration_minutes=60,
                price=95.0,
                is_active=True,
            )
            session.add_all([biz, svc])

    ref_now = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)  # Monday 07:00 AM NY

    # 1. Past time rejection
    past_time = ref_now - timedelta(hours=1)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            with pytest.raises(PastTimeError):
                await book_appointment(
                    session=session,
                    business_id=biz_id,
                    service_id=svc_id,
                    start_time=past_time,
                    customer_name="Bob",
                    customer_phone="555-0101",
                    reference_now=ref_now,
                    min_notice_hours=2,
                )

    # 2. Minimum notice rejection (1 hour ahead when min notice is 2 hours)
    short_notice_time = ref_now + timedelta(hours=1)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            with pytest.raises(MinimumNoticeError):
                await book_appointment(
                    session=session,
                    business_id=biz_id,
                    service_id=svc_id,
                    start_time=short_notice_time,
                    customer_name="Bob",
                    customer_phone="555-0101",
                    reference_now=ref_now,
                    min_notice_hours=2,
                )

    # 3. Closed day rejection (Sunday)
    sunday_time = datetime(2026, 11, 22, 16, 0, tzinfo=timezone.utc)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            with pytest.raises(OutsideBusinessHoursError, match="closed on Sundays"):
                await book_appointment(
                    session=session,
                    business_id=biz_id,
                    service_id=svc_id,
                    start_time=sunday_time,
                    customer_name="Bob",
                    customer_phone="555-0101",
                    reference_now=ref_now,
                    min_notice_hours=2,
                )

    # 4. Outside business hours (Monday evening at 23:00 UTC = 18:00 NY, after 17:00 close)
    late_monday = datetime(2026, 11, 16, 23, 0, tzinfo=timezone.utc)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            with pytest.raises(OutsideBusinessHoursError, match="outside business hours"):
                await book_appointment(
                    session=session,
                    business_id=biz_id,
                    service_id=svc_id,
                    start_time=late_monday,
                    customer_name="Bob",
                    customer_phone="555-0101",
                    reference_now=ref_now,
                    min_notice_hours=2,
                )


@pytest.mark.asyncio
async def test_book_appointment_double_booking_rejection():
    """Verify that a second booking overlapping an existing booking is strictly rejected."""
    biz_id = uuid.uuid4()
    svc_id = uuid.uuid4()
    test_hours = {
        "thursday": {"open": "09:00", "close": "17:00", "closed": False},
    }

    async with AsyncSessionLocal() as session:
        async with session.begin():
            biz = Business(
                id=biz_id,
                name="Booking Conflict Dental",
                business_type="Dental",
                greeting="Welcome to Conflict Dental",
                timezone="America/New_York",
                hours=test_hours,
            )
            svc = Service(
                id=svc_id,
                business_id=biz_id,
                name="Exam",
                duration_minutes=30,
                price=80.0,
                is_active=True,
            )
            session.add_all([biz, svc])

    ref_now = datetime(2026, 11, 19, 10, 0, tzinfo=timezone.utc)  # Thursday 05:00 AM NY
    # Slot 1: Thursday 15:00 UTC (10:00 AM NY) to 15:30 UTC
    slot1_start = datetime(2026, 11, 19, 15, 0, tzinfo=timezone.utc)

    # Book slot 1
    async with AsyncSessionLocal() as session:
        async with session.begin():
            res1 = await book_appointment(
                session=session,
                business_id=biz_id,
                service_id=svc_id,
                start_time=slot1_start,
                customer_name="First Caller",
                customer_phone="555-0111",
                reference_now=ref_now,
                min_notice_hours=2,
            )
            assert res1.appointment.status == "booked"

    # Attempt to book overlapping slot (exact duplicate: 15:00 UTC)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            with pytest.raises(DoubleBookingError, match="already booked"):
                await book_appointment(
                    session=session,
                    business_id=biz_id,
                    service_id=svc_id,
                    start_time=slot1_start,
                    customer_name="Second Caller",
                    customer_phone="555-0222",
                    reference_now=ref_now,
                    min_notice_hours=2,
                )

    # Attempt to book partial overlapping slot (15:15 UTC - overlaps 15:00-15:30)
    slot_overlap = datetime(2026, 11, 19, 15, 15, tzinfo=timezone.utc)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            with pytest.raises(DoubleBookingError, match="already booked"):
                await book_appointment(
                    session=session,
                    business_id=biz_id,
                    service_id=svc_id,
                    start_time=slot_overlap,
                    customer_name="Third Caller",
                    customer_phone="555-0333",
                    reference_now=ref_now,
                    min_notice_hours=2,
                )


@pytest.mark.asyncio
async def test_book_appointment_idempotency_same_call():
    """Verify that an identical booking retry within the same call session returns the existing booking."""
    biz_id = uuid.uuid4()
    svc_id = uuid.uuid4()
    call_id = uuid.uuid4()
    test_hours = {
        "friday": {"open": "09:00", "close": "17:00", "closed": False},
    }

    async with AsyncSessionLocal() as session:
        async with session.begin():
            biz = Business(
                id=biz_id,
                name="Idempotent Dental",
                business_type="Dental",
                greeting="Welcome to Idempotent Dental",
                timezone="America/New_York",
                hours=test_hours,
            )
            svc = Service(
                id=svc_id,
                business_id=biz_id,
                name="Whitening",
                duration_minutes=60,
                price=300.0,
                is_active=True,
            )
            call = Call(
                id=call_id,
                business_id=biz_id,
                caller_number="555-0155",
            )
            session.add_all([biz, svc, call])

    ref_now = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)
    start_time = datetime(2026, 11, 20, 16, 0, tzinfo=timezone.utc)

    # First booking attempt
    async with AsyncSessionLocal() as session:
        async with session.begin():
            res1 = await book_appointment(
                session=session,
                business_id=biz_id,
                service_id=svc_id,
                start_time=start_time,
                customer_name="Sam Smith",
                customer_phone="555-0155",
                call_id=call_id,
                reference_now=ref_now,
                min_notice_hours=2,
            )
            assert res1.is_duplicate is False

    # Second booking attempt in the exact same call session with same customer phone and time
    async with AsyncSessionLocal() as session:
        async with session.begin():
            res2 = await book_appointment(
                session=session,
                business_id=biz_id,
                service_id=svc_id,
                start_time=start_time,
                customer_name="Sam Smith",
                customer_phone="555-0155",
                call_id=call_id,
                reference_now=ref_now,
                min_notice_hours=2,
            )
            assert res2.is_duplicate is True
            assert res2.appointment.id == res1.appointment.id


@pytest.mark.asyncio
async def test_concurrent_booking_double_booking_protection():
    """
    CRITICAL CONCURRENCY TEST:
    Trigger two concurrent booking requests for the exact same slot across two separate
    database sessions using asyncio.gather.
    Verify that exactly one succeeds and the other fails with DoubleBookingError.
    """
    biz_id = uuid.uuid4()
    svc_id = uuid.uuid4()
    test_hours = {
        "tuesday": {"open": "09:00", "close": "17:00", "closed": False},
    }

    async with AsyncSessionLocal() as session:
        async with session.begin():
            biz = Business(
                id=biz_id,
                name="Concurrent Race Dental",
                business_type="Dental",
                greeting="Welcome to Concurrent Dental",
                timezone="America/New_York",
                hours=test_hours,
            )
            svc = Service(
                id=svc_id,
                business_id=biz_id,
                name="Checkup",
                duration_minutes=30,
                price=100.0,
                is_active=True,
            )
            session.add_all([biz, svc])

    ref_now = datetime(2026, 11, 24, 10, 0, tzinfo=timezone.utc)
    target_slot = datetime(2026, 11, 24, 15, 0, tzinfo=timezone.utc)  # 10:00 AM NY

    async def _attempt_booking(caller_name: str, phone: str):
        async with AsyncSessionLocal() as s:
            async with s.begin():
                return await book_appointment(
                    session=s,
                    business_id=biz_id,
                    service_id=svc_id,
                    start_time=target_slot,
                    customer_name=caller_name,
                    customer_phone=phone,
                    reference_now=ref_now,
                    min_notice_hours=2,
                )

    # Launch both concurrent requests simultaneously
    results = await asyncio.gather(
        _attempt_booking("Caller A", "555-0111"),
        _attempt_booking("Caller B", "555-0222"),
        return_exceptions=True,
    )

    successes = [r for r in results if isinstance(r, object) and not isinstance(r, Exception)]
    errors = [r for r in results if isinstance(r, Exception)]

    # Strictly verify 1 success and 1 DoubleBookingError
    assert len(successes) == 1, f"Expected 1 success, got {len(successes)}: {results}"
    assert len(errors) == 1, f"Expected 1 error, got {len(errors)}: {results}"
    assert isinstance(errors[0], DoubleBookingError), f"Expected DoubleBookingError, got {type(errors[0])}: {errors[0]}"

    # Verify database contains exactly 1 appointment record for this business
    async with AsyncSessionLocal() as session:
        appts = await list_appointments(session, biz_id)
        assert len(appts) == 1
        assert appts[0].start_at == target_slot
