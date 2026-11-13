"""Unit and integration tests for Option 3: Instant WhatsApp / SMS Appointment Confirmations."""

from datetime import datetime, timedelta, timezone
import uuid
import pytest
import pytest_asyncio
from sqlalchemy import select

from callwise.booking.service import book_appointment
from callwise.booking.verification import cancel_appointment, reschedule_appointment
from callwise.db.models import Appointment, Business, Notification, Service
from callwise.db.session import async_engine, get_async_session, get_sync_session
from callwise.notifications.service import (
    format_currency,
    format_local_time,
    notify_booking,
    notify_cancellation,
    notify_reschedule,
)
from callwise.providers.email import ConsoleEmailProvider
from callwise.providers.messaging import (
    MockMessagingProvider,
    get_messaging_provider,
)


@pytest_asyncio.fixture(autouse=True)
async def cleanup_db_pool():
    """Ensure async engine pool is disposed within the running event loop."""
    yield
    await async_engine.dispose()


@pytest.fixture
def indian_clinic_and_service():
    """Seed an Indian dental clinic with Asia/Kolkata timezone and INR pricing."""
    biz_id = uuid.uuid4()
    svc_id = uuid.uuid4()
    with get_sync_session() as session:
        biz = Business(
            id=biz_id,
            name="Aarav Health & Dental Clinic",
            business_type="dental clinic",
            timezone="Asia/Kolkata",
            tone="warm, professional",
            greeting="Namaste, welcome to Aarav Dental.",
            transfer_number="+918025251122",
            notification_email="owner@aaravdental.in",
            hours={
                "monday": {"open": "10:00", "close": "20:00"},
                "tuesday": {"open": "10:00", "close": "20:00"},
                "wednesday": {"open": "10:00", "close": "20:00"},
                "thursday": {"open": "10:00", "close": "20:00"},
                "friday": {"open": "10:00", "close": "20:00"},
                "saturday": {"open": "10:00", "close": "20:00"},
                "sunday": {"closed": True},
            },
        )
        session.add(biz)
        svc = Service(
            id=svc_id,
            business_id=biz_id,
            name="Root Canal Treatment",
            duration_minutes=60,
            price=4500.0,
            description="Specialist rotary root canal treatment with digital imaging.",
            is_active=True,
        )
        session.add(svc)
        session.commit()

    return {"business_id": biz_id, "service_id": svc_id}


# ============================================================================
# 1. Unit Tests: Currency and Provider Direct Tests
# ============================================================================

def test_format_currency_localization():
    """Verify correct currency symbols for Indian (₹) and US ($) businesses."""
    assert format_currency(4500.0, "Asia/Kolkata") == "₹4,500"
    assert format_currency(1500.50, "Asia/Kolkata") == "₹1,500.50"
    assert format_currency(120.0, "America/New_York") == "$120.00"
    assert format_currency(85.50, "UTC") == "$85.50"


@pytest.mark.asyncio
async def test_mock_messaging_provider_dispatch():
    """Verify MockMessagingProvider records SMS and WhatsApp messages accurately."""
    provider = MockMessagingProvider()
    provider.clear()

    sms_res = await provider.send_sms(
        to_phone="+919876543210",
        body="Apex Dental: Your visit is confirmed for Monday at 10 AM.",
    )
    assert sms_res.success is True
    assert sms_res.channel == "sms"
    assert len(provider.recorded_messages) == 1
    assert provider.recorded_messages[0]["channel"] == "sms"
    assert provider.recorded_messages[0]["to_phone"] == "+919876543210"

    wa_res = await provider.send_whatsapp(
        to_phone="+919876543210",
        body="✅ *Appointment Confirmed!*\nDate: Monday 10 AM",
    )
    assert wa_res.success is True
    assert wa_res.channel == "whatsapp"
    assert len(provider.recorded_messages) == 2
    assert provider.recorded_messages[1]["channel"] == "whatsapp"


# ============================================================================
# 2. Notification Dispatch Tests: Booking, Cancellation, and Rescheduling
# ============================================================================

@pytest.mark.asyncio
async def test_notify_booking_dispatches_whatsapp_and_sms(indian_clinic_and_service):
    """Verify booking dispatches both WhatsApp and SMS to customer phone and records in DB."""
    biz_id = indian_clinic_and_service["business_id"]
    svc_id = indian_clinic_and_service["service_id"]
    mock_msg_provider = MockMessagingProvider()
    mock_email_provider = ConsoleEmailProvider()

    now_utc = datetime.now(timezone.utc)
    appt_start = now_utc + timedelta(days=2)

    async with get_async_session() as session:
        biz = await session.get(Business, biz_id)
        svc = await session.get(Service, svc_id)
        appt = Appointment(
            business_id=biz_id,
            service_id=svc_id,
            customer_name="Rohan Verma",
            customer_phone="+919876543210",
            customer_email="rohan@example.com",
            start_at=appt_start,
            end_at=appt_start + timedelta(minutes=60),
            status="booked",
            booking_code_hash="mock_hash_123",
        )
        session.add(appt)
        await session.flush()

        await notify_booking(
            session=session,
            business=biz,
            appointment=appt,
            service=svc,
            booking_code="BK-9Z4",
            email_provider=mock_email_provider,
            messaging_provider=mock_msg_provider,
        )
        await session.commit()

    # Check provider in-memory records
    assert len(mock_msg_provider.recorded_messages) == 2
    wa_msg = next(m for m in mock_msg_provider.recorded_messages if m["channel"] == "whatsapp")
    sms_msg = next(m for m in mock_msg_provider.recorded_messages if m["channel"] == "sms")

    assert "Rohan Verma" in wa_msg["body"]
    assert "₹4,500" in wa_msg["body"]
    assert "BK-9Z4" in wa_msg["body"]
    assert "Aarav Health & Dental Clinic" in wa_msg["body"]
    assert "widget-frame" in wa_msg["body"]

    assert "BK-9Z4" in sms_msg["body"]
    assert "₹4,500" in sms_msg["body"]

    # Check database persistence in notifications table
    async with get_async_session() as session:
        notifs = (
            await session.scalars(
                select(Notification).where(Notification.business_id == biz_id)
            )
        ).all()
        types = [n.type for n in notifs]
        assert "customer_booking_whatsapp" in types
        assert "customer_booking_sms" in types
        assert "customer_booking_confirmation" in types
        assert "owner_new_booking" in types

        wa_notif = next(n for n in notifs if n.type == "customer_booking_whatsapp")
        assert wa_notif.status == "sent"
        assert wa_notif.recipient == "+919876543210"
        assert wa_notif.sent_at is not None


@pytest.mark.asyncio
async def test_notify_cancellation_and_reschedule_messaging(indian_clinic_and_service):
    """Verify cancellation and rescheduling dispatch instant updates to customer phone."""
    biz_id = indian_clinic_and_service["business_id"]
    svc_id = indian_clinic_and_service["service_id"]
    mock_msg_provider = MockMessagingProvider()

    now_utc = datetime.now(timezone.utc)
    appt_start = now_utc + timedelta(days=3)
    new_start = now_utc + timedelta(days=4)

    async with get_async_session() as session:
        biz = await session.get(Business, biz_id)
        svc = await session.get(Service, svc_id)
        appt = Appointment(
            business_id=biz_id,
            service_id=svc_id,
            customer_name="Priya Patel",
            customer_phone="+919811122233",
            start_at=appt_start,
            end_at=appt_start + timedelta(minutes=60),
            status="booked",
            booking_code_hash="mock_hash_456",
        )
        session.add(appt)
        await session.flush()

        # 1. Test Reschedule
        await notify_reschedule(
            session=session,
            business=biz,
            appointment=appt,
            service=svc,
            old_start_utc=appt_start,
            new_start_utc=new_start,
            messaging_provider=mock_msg_provider,
        )

        # 2. Test Cancellation
        await notify_cancellation(
            session=session,
            business=biz,
            appointment=appt,
            service=svc,
            messaging_provider=mock_msg_provider,
        )
        await session.commit()

    # Check messaging records dispatched
    channels = [m["channel"] for m in mock_msg_provider.recorded_messages]
    assert channels.count("whatsapp") == 2  # 1 reschedule + 1 cancellation
    assert channels.count("sms") == 2       # 1 reschedule + 1 cancellation

    resched_wa = mock_msg_provider.recorded_messages[0]
    assert "Rescheduled" in resched_wa["body"]
    assert "Priya Patel" in resched_wa["body"]

    cancel_wa = mock_msg_provider.recorded_messages[2]
    assert "Cancelled" in cancel_wa["body"]
    assert "Priya Patel" in cancel_wa["body"]


# ============================================================================
# 3. End-to-End Booking Integration Test
# ============================================================================

@pytest.mark.asyncio
async def test_end_to_end_booking_dispatches_instant_messaging(indian_clinic_and_service):
    """Verify that calling book_appointment automatically creates WhatsApp & SMS notification rows."""
    biz_id = indian_clinic_and_service["business_id"]
    svc_id = indian_clinic_and_service["service_id"]

    # Target Tuesday 11:00 AM IST (5:30 AM UTC) 2 days ahead
    target_dt = datetime(2026, 11, 17, 5, 30, tzinfo=timezone.utc)
    ref_now = datetime(2026, 11, 15, 1, 0, tzinfo=timezone.utc)

    async with get_async_session() as session:
        result = await book_appointment(
            session=session,
            business_id=biz_id,
            service_id=svc_id,
            customer_name="Kavita Rao",
            customer_phone="+919845012345",
            customer_email="kavita@example.com",
            start_time=target_dt,
            reference_now=ref_now,
            send_notifications=True,
        )
        await session.commit()

    assert result.appointment.id is not None
    assert result.booking_code.startswith("BK-")

    # Verify notifications table contains the instant WhatsApp & SMS notifications
    async with get_async_session() as session:
        notifs = (
            await session.scalars(
                select(Notification)
                .where(Notification.business_id == biz_id, Notification.recipient == "+919845012345")
            )
        ).all()

        types = [n.type for n in notifs]
        assert "customer_booking_whatsapp" in types
        assert "customer_booking_sms" in types

        for n in notifs:
            assert n.status == "sent"
            assert n.sent_at is not None
