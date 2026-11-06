"""Tests for appointment reminder creation, updates, and idempotent scheduler execution."""

from datetime import datetime, timedelta, timezone
import uuid
import pytest
from sqlalchemy import select

from callwise.booking.service import book_appointment
from callwise.booking.verification import cancel_appointment, reschedule_appointment
from callwise.db.models import Appointment, Business, Notification, Reminder, Service
from callwise.db.session import AsyncSessionLocal
from callwise.providers.email import ConsoleEmailProvider
from callwise.reminders.scheduler import process_due_reminders, send_reminder_email, trigger_reminder_call


@pytest.mark.asyncio
async def test_booking_creates_24h_email_and_2h_call_reminders():
    """Verify booking with customer email schedules both 24h email and 2h call reminders."""
    biz_id = uuid.uuid4()
    svc_id = uuid.uuid4()
    mock_email = ConsoleEmailProvider()

    test_hours = {
        "wednesday": {"open": "08:00", "close": "17:00", "closed": False},
    }

    async with AsyncSessionLocal() as session:
        async with session.begin():
            biz = Business(
                id=biz_id,
                name="Reminder Clinic",
                business_type="Dental",
                greeting="Hello",
                timezone="America/New_York",
                hours=test_hours,
            )
            svc = Service(
                id=svc_id,
                business_id=biz_id,
                name="Checkup",
                duration_minutes=30,
                price=50.0,
                is_active=True,
            )
            session.add_all([biz, svc])

    ref_now = datetime(2026, 11, 9, 10, 0, tzinfo=timezone.utc)
    appt_time = datetime(2026, 11, 11, 15, 0, tzinfo=timezone.utc)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            res = await book_appointment(
                session=session,
                business_id=biz_id,
                service_id=svc_id,
                start_time=appt_time,
                customer_name="Dana Scully",
                customer_phone="555-0199",
                customer_email="scully@fbi.gov",
                email_provider=mock_email,
                reference_now=ref_now,
                min_notice_hours=2,
            )

    async with AsyncSessionLocal() as session:
        stmt = (
            select(Reminder)
            .where(Reminder.appointment_id == res.appointment.id)
            .order_by(Reminder.send_at.asc())
        )
        rems = (await session.execute(stmt)).scalars().all()
        assert len(rems) == 2

        # 24h advance email reminder
        email_rem = next(r for r in rems if r.channel == "email")
        assert email_rem.status == "pending"
        assert email_rem.send_at == appt_time - timedelta(hours=24)

        # 2h advance automated call reminder
        call_rem = next(r for r in rems if r.channel == "call")
        assert call_rem.status == "pending"
        assert call_rem.send_at == appt_time - timedelta(hours=2)


@pytest.mark.asyncio
async def test_cancellation_cancels_all_reminders():
    """Verify cancelling an appointment marks both email and call reminders as cancelled."""
    biz_id = uuid.uuid4()
    svc_id = uuid.uuid4()
    mock_email = ConsoleEmailProvider()

    test_hours = {
        "thursday": {"open": "08:00", "close": "17:00", "closed": False},
    }

    async with AsyncSessionLocal() as session:
        async with session.begin():
            biz = Business(
                id=biz_id,
                name="Cancel Reminder Clinic",
                business_type="Dental",
                greeting="Hello",
                timezone="America/New_York",
                hours=test_hours,
            )
            svc = Service(
                id=svc_id,
                business_id=biz_id,
                name="Cleaning",
                duration_minutes=45,
                price=90.0,
                is_active=True,
            )
            session.add_all([biz, svc])

    ref_now = datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc)
    appt_time = datetime(2026, 11, 12, 15, 0, tzinfo=timezone.utc)

    # 1. Book appointment
    async with AsyncSessionLocal() as session:
        async with session.begin():
            res = await book_appointment(
                session=session,
                business_id=biz_id,
                service_id=svc_id,
                start_time=appt_time,
                customer_name="Fox Mulder",
                customer_phone="555-0188",
                customer_email="mulder@fbi.gov",
                email_provider=mock_email,
                reference_now=ref_now,
                min_notice_hours=2,
            )
            booking_code = res.booking_code

    # 2. Cancel appointment
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await cancel_appointment(
                session=session,
                business_id=biz_id,
                booking_code=booking_code,
                caller_phone="555-0188",
                email_provider=mock_email,
            )

    # Verify both reminders are now cancelled
    async with AsyncSessionLocal() as session:
        stmt = select(Reminder).where(Reminder.appointment_id == res.appointment.id)
        rems = (await session.execute(stmt)).scalars().all()
        assert len(rems) == 2
        assert all(r.status == "cancelled" for r in rems)


@pytest.mark.asyncio
async def test_reschedule_updates_both_reminder_times():
    """Verify rescheduling an appointment recalculates 24h email and 2h call reminder send_at times."""
    biz_id = uuid.uuid4()
    svc_id = uuid.uuid4()
    mock_email = ConsoleEmailProvider()

    test_hours = {
        "friday": {"open": "08:00", "close": "17:00", "closed": False},
        "saturday": {"open": "08:00", "close": "17:00", "closed": False},
    }

    async with AsyncSessionLocal() as session:
        async with session.begin():
            biz = Business(
                id=biz_id,
                name="Reschedule Reminder Clinic",
                business_type="Dental",
                greeting="Hello",
                timezone="America/New_York",
                hours=test_hours,
            )
            svc = Service(
                id=svc_id,
                business_id=biz_id,
                name="Exam",
                duration_minutes=30,
                price=60.0,
                is_active=True,
            )
            session.add_all([biz, svc])

    ref_now = datetime(2026, 11, 11, 10, 0, tzinfo=timezone.utc)
    original_start = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            res = await book_appointment(
                session=session,
                business_id=biz_id,
                service_id=svc_id,
                start_time=original_start,
                customer_name="Luke Skywalker",
                customer_phone="555-0177",
                customer_email="luke@rebel.org",
                email_provider=mock_email,
                reference_now=ref_now,
                min_notice_hours=2,
            )
            booking_code = res.booking_code

    # Reschedule to Saturday 2026-11-14 at 16:00 UTC
    new_start = datetime(2026, 11, 14, 16, 0, tzinfo=timezone.utc)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await reschedule_appointment(
                session=session,
                business_id=biz_id,
                booking_code=booking_code,
                new_start_time=new_start,
                caller_name="Luke",
                email_provider=mock_email,
                reference_now=ref_now,
                min_notice_hours=2,
            )

    async with AsyncSessionLocal() as session:
        stmt = select(Reminder).where(Reminder.appointment_id == res.appointment.id)
        rems = (await session.execute(stmt)).scalars().all()
        assert len(rems) == 2

        email_rem = next(r for r in rems if r.channel == "email")
        assert email_rem.send_at == new_start - timedelta(hours=24)
        assert email_rem.status == "pending"

        call_rem = next(r for r in rems if r.channel == "call")
        assert call_rem.send_at == new_start - timedelta(hours=2)
        assert call_rem.status == "pending"


@pytest.mark.asyncio
async def test_process_due_reminders_and_automated_call_delivery():
    """
    CRITICAL IDEMPOTENCY & CALL TEST:
    Verify that due reminders (both email and automated 2-hour call) are delivered
    and consecutive runs never send duplicate reminders.
    """
    biz_id = uuid.uuid4()
    svc_id = uuid.uuid4()
    appt_id = uuid.uuid4()
    email_rem_id = uuid.uuid4()
    call_rem_id = uuid.uuid4()
    mock_email = ConsoleEmailProvider()

    appt_time = datetime(2026, 11, 15, 15, 0, tzinfo=timezone.utc)
    email_send_at = appt_time - timedelta(hours=24)
    call_send_at = appt_time - timedelta(hours=2)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            biz = Business(
                id=biz_id,
                name="Idempotent Reminder Dental",
                business_type="Dental",
                greeting="Hello",
                timezone="America/New_York",
                hours={},
                transfer_number="+1-555-0100",
            )
            svc = Service(
                id=svc_id,
                business_id=biz_id,
                name="Crown Fitting",
                duration_minutes=60,
                price=500.0,
                is_active=True,
            )
            appt = Appointment(
                id=appt_id,
                business_id=biz_id,
                service_id=svc_id,
                customer_name="Jean-Luc Picard",
                customer_phone="555-0111",
                customer_email="picard@enterprise.org",
                start_at=appt_time,
                end_at=appt_time + timedelta(minutes=60),
                status="booked",
                booking_code_hash="dummy_hash",
            )
            rem_email = Reminder(
                id=email_rem_id,
                business_id=biz_id,
                appointment_id=appt_id,
                send_at=email_send_at,
                channel="email",
                status="pending",
            )
            rem_call = Reminder(
                id=call_rem_id,
                business_id=biz_id,
                appointment_id=appt_id,
                send_at=call_send_at,
                channel="call",
                status="pending",
            )
            session.add_all([biz, svc, appt, rem_email, rem_call])

    # 1. 24h prior to appointment: email reminder is due, but 2h call reminder is NOT yet due
    time_24h_before = email_send_at + timedelta(minutes=5)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            count1 = await process_due_reminders(
                session=session,
                business_id=biz_id,
                reference_now=time_24h_before,
                email_provider=mock_email,
            )
    assert count1 == 1  # Only email was due
    assert len(mock_email.sent_messages) == 1
    assert mock_email.sent_messages[0].to == "picard@enterprise.org"

    # Verify email reminder is marked 'sent', while call reminder is still 'pending'
    async with AsyncSessionLocal() as session:
        saved_email_rem = await session.get(Reminder, email_rem_id)
        saved_call_rem = await session.get(Reminder, call_rem_id)
        assert saved_email_rem.status == "sent"
        assert saved_call_rem.status == "pending"

    # 2. 2h prior to appointment: automated reminder call is now due
    time_2h_before = call_send_at + timedelta(minutes=5)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            count2 = await process_due_reminders(
                session=session,
                business_id=biz_id,
                reference_now=time_2h_before,
                email_provider=mock_email,
            )
    assert count2 == 1  # The automated 2h call was processed

    # Verify both reminders are now 'sent'
    async with AsyncSessionLocal() as session:
        saved_call_rem = await session.get(Reminder, call_rem_id)
        assert saved_call_rem.status == "sent"

        # Verify automated call was audited in notifications table
        stmt = select(Notification).where(
            Notification.business_id == biz_id,
            Notification.type == "customer_reminder_call_2h",
        )
        call_notif = (await session.execute(stmt)).scalar_one_or_none()
        assert call_notif is not None
        assert call_notif.recipient == "555-0111"
        assert call_notif.status == "sent"

    # 3. IDEMPOTENT RE-RUN: Third run after both times processed must process 0 reminders and trigger 0 duplicates
    async with AsyncSessionLocal() as session:
        async with session.begin():
            count3 = await process_due_reminders(
                session=session,
                business_id=biz_id,
                reference_now=time_2h_before + timedelta(minutes=30),
                email_provider=mock_email,
            )
    assert count3 == 0
    # Sent emails remain strictly 1
    assert len(mock_email.sent_messages) == 1
