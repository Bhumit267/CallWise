"""Tests for EmailProvider implementations and notification dispatch pipeline."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import uuid
import pytest
from sqlalchemy import select

from callwise.booking.service import book_appointment
from callwise.booking.verification import cancel_appointment, reschedule_appointment
from callwise.db.models import (
    Appointment,
    Business,
    Message,
    Notification,
    Service,
    Transfer,
)
from callwise.db.session import AsyncSessionLocal
from callwise.notifications.service import (
    dispatch_email,
    format_local_time,
    notify_booking,
    notify_cancellation,
    notify_message,
    notify_reschedule,
    notify_transfer,
)
from callwise.providers.email import (
    ConsoleEmailProvider,
    EmailMessage,
    SMTPEmailProvider,
    get_email_provider,
)


@pytest.mark.asyncio
async def test_console_email_provider():
    """Verify ConsoleEmailProvider outputs and collects sent messages."""
    provider = ConsoleEmailProvider()
    msg = EmailMessage(
        to="caller@example.com",
        subject="Appointment Confirmed",
        body_text="Your visit is booked for Monday at 10 AM.",
    )
    result = await provider.send_email(msg)
    assert result is True
    assert len(provider.sent_messages) == 1
    assert provider.sent_messages[0].to == "caller@example.com"
    assert provider.sent_messages[0].subject == "Appointment Confirmed"


@pytest.mark.asyncio
async def test_smtp_email_provider_mocked():
    """Verify SMTPEmailProvider properly connects, uses TLS, logs in, and sends message."""
    mock_server = MagicMock()
    with patch("smtplib.SMTP", return_value=mock_server):
        mock_server.__enter__.return_value = mock_server

        provider = SMTPEmailProvider(
            host="smtp.test.com",
            port=587,
            user="user@test.com",
            password="secretpassword",
            use_tls=True,
            default_from="noreply@test.com",
        )
        msg = EmailMessage(
            to="recipient@example.com",
            subject="Test Subject",
            body_text="Test email body",
        )
        success = await provider.send_email(msg)
        assert success is True

        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user@test.com", "secretpassword")
        mock_server.send_message.assert_called_once()


def test_format_local_time():
    """Verify formatting converts UTC to business local timezone."""
    dt_utc = datetime(2026, 11, 9, 15, 0, tzinfo=timezone.utc)
    formatted = format_local_time(dt_utc, "America/New_York")
    # 15:00 UTC = 10:00 AM EST (standard time in November)
    assert "Monday, November 09, 2026 at 10:00 AM EST" in formatted


@pytest.mark.asyncio
async def test_notify_booking_dispatches_customer_and_owner_notifications():
    """Verify booking dispatches both confirmation to customer and alert to business owner."""
    biz_id = uuid.uuid4()
    svc_id = uuid.uuid4()
    mock_email_provider = ConsoleEmailProvider()

    test_hours = {
        "monday": {"open": "08:00", "close": "17:00", "closed": False},
    }

    async with AsyncSessionLocal() as session:
        async with session.begin():
            biz = Business(
                id=biz_id,
                name="Email Test Dental",
                business_type="Dental Clinic",
                greeting="Welcome to Email Test Dental",
                timezone="America/New_York",
                hours=test_hours,
                transfer_number="+1-555-0199",
                notification_email="owner@testdental.com",
            )
            svc = Service(
                id=svc_id,
                business_id=biz_id,
                name="Routine Checkup",
                duration_minutes=45,
                price=125.0,
                is_active=True,
            )
            session.add_all([biz, svc])

    ref_now = datetime(2026, 11, 9, 10, 0, tzinfo=timezone.utc)
    start_time = datetime(2026, 11, 9, 15, 0, tzinfo=timezone.utc)  # 10:00 AM NY

    async with AsyncSessionLocal() as session:
        async with session.begin():
            res = await book_appointment(
                session=session,
                business_id=biz_id,
                service_id=svc_id,
                start_time=start_time,
                customer_name="Ellen Ripley",
                customer_phone="555-0144",
                customer_email="ripley@weyland.com",
                email_provider=mock_email_provider,
                reference_now=ref_now,
                min_notice_hours=2,
            )

    # Verify emails sent by mock provider
    assert len(mock_email_provider.sent_messages) == 2
    recipients = {m.to for m in mock_email_provider.sent_messages}
    assert "ripley@weyland.com" in recipients
    assert "owner@testdental.com" in recipients

    customer_msg = next(m for m in mock_email_provider.sent_messages if m.to == "ripley@weyland.com")
    assert res.booking_code in customer_msg.body_text
    assert "10:00 AM EST" in customer_msg.body_text
    assert "Routine Checkup" in customer_msg.subject

    owner_msg = next(m for m in mock_email_provider.sent_messages if m.to == "owner@testdental.com")
    assert "Ellen Ripley" in owner_msg.body_text
    assert "***-***-0144" in owner_msg.body_text

    # Verify notifications saved in DB
    async with AsyncSessionLocal() as session:
        stmt = select(Notification).where(Notification.business_id == biz_id)
        notifs = (await session.execute(stmt)).scalars().all()
        assert len(notifs) >= 2
        types = {n.type for n in notifs}
        assert "customer_booking_confirmation" in types
        assert "owner_new_booking" in types
        assert all(n.status == "sent" for n in notifs)


@pytest.mark.asyncio
async def test_notify_cancellation_and_reschedule():
    """Verify cancellation and rescheduling send updated notices to customer and owner."""
    biz_id = uuid.uuid4()
    svc_id = uuid.uuid4()
    mock_email_provider = ConsoleEmailProvider()

    test_hours = {
        "tuesday": {"open": "08:00", "close": "17:00", "closed": False},
    }

    async with AsyncSessionLocal() as session:
        async with session.begin():
            biz = Business(
                id=biz_id,
                name="Metro Wellness",
                business_type="Wellness Center",
                greeting="Welcome to Metro Wellness",
                timezone="America/New_York",
                hours=test_hours,
                transfer_number="+1-555-0122",
                notification_email="manager@metrowellness.com",
            )
            svc = Service(
                id=svc_id,
                business_id=biz_id,
                name="Acupuncture",
                duration_minutes=30,
                price=85.0,
                is_active=True,
            )
            session.add_all([biz, svc])

    ref_now = datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc)
    original_start = datetime(2026, 11, 10, 15, 0, tzinfo=timezone.utc)

    # 1. Book appointment
    async with AsyncSessionLocal() as session:
        async with session.begin():
            res = await book_appointment(
                session=session,
                business_id=biz_id,
                service_id=svc_id,
                start_time=original_start,
                customer_name="James Holden",
                customer_phone="555-0177",
                customer_email="holden@rocinante.org",
                email_provider=mock_email_provider,
                reference_now=ref_now,
                min_notice_hours=2,
            )
            booking_code = res.booking_code

    mock_email_provider.clear()

    # 2. Reschedule appointment
    new_start = datetime(2026, 11, 10, 17, 0, tzinfo=timezone.utc)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await reschedule_appointment(
                session=session,
                business_id=biz_id,
                booking_code=booking_code,
                new_start_time=new_start,
                caller_name="James Holden",
                email_provider=mock_email_provider,
                reference_now=ref_now,
                min_notice_hours=2,
            )

    assert len(mock_email_provider.sent_messages) == 2
    resched_customer = next(m for m in mock_email_provider.sent_messages if m.to == "holden@rocinante.org")
    assert "Appointment Rescheduled" in resched_customer.subject
    assert "12:00 PM EST" in resched_customer.body_text

    mock_email_provider.clear()

    # 3. Cancel appointment
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await cancel_appointment(
                session=session,
                business_id=biz_id,
                booking_code=booking_code,
                caller_name="Holden",
                email_provider=mock_email_provider,
            )

    assert len(mock_email_provider.sent_messages) == 2
    cancel_customer = next(m for m in mock_email_provider.sent_messages if m.to == "holden@rocinante.org")
    assert "Appointment Cancelled" in cancel_customer.subject


@pytest.mark.asyncio
async def test_notify_message_alert():
    """Verify leaving a message dispatches an email alert to the business owner."""
    biz_id = uuid.uuid4()
    mock_email_provider = ConsoleEmailProvider()

    async with AsyncSessionLocal() as session:
        async with session.begin():
            biz = Business(
                id=biz_id,
                name="Message Alert Dental",
                business_type="Dental Clinic",
                greeting="Welcome to Dental",
                timezone="America/New_York",
                hours={},
                notification_email="owner@messagedental.com",
            )
            msg = Message(
                business_id=biz_id,
                caller_name="Amos Burton",
                callback_number="555-0199",
                reason="Need to check if Dr. Sarah is accepting new patients",
            )
            session.add_all([biz, msg])
            await session.flush()

            await notify_message(
                session=session,
                business=biz,
                message=msg,
                email_provider=mock_email_provider,
            )

    assert len(mock_email_provider.sent_messages) == 1
    sent = mock_email_provider.sent_messages[0]
    assert sent.to == "owner@messagedental.com"
    assert "Amos Burton" in sent.subject
    assert "Dr. Sarah" in sent.body_text


@pytest.mark.asyncio
async def test_notification_delivery_failure_is_resilient():
    """Verify that an email delivery error sets notification status='failed' without raising."""
    biz_id = uuid.uuid4()

    class FailingEmailProvider(ConsoleEmailProvider):
        async def send_email(self, message: EmailMessage) -> bool:
            raise ConnectionError("SMTP Connection Refused")

    async with AsyncSessionLocal() as session:
        async with session.begin():
            biz = Business(
                id=biz_id,
                name="Failing Alert Dental",
                business_type="Dental Clinic",
                greeting="Hello",
                timezone="America/New_York",
                hours={},
            )
            session.add(biz)
            await session.flush()

            notif = await dispatch_email(
                session=session,
                business_id=biz_id,
                notification_type="owner_alert",
                recipient="test@example.com",
                subject="Test Alert",
                body_text="Testing resilience",
                email_provider=FailingEmailProvider(),
            )
            assert notif.status == "failed"
            assert "SMTP Connection Refused" in notif.error
