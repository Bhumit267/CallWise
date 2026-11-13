"""Notification dispatch service for customer confirmations and business owner alerts."""

from datetime import datetime, timezone
import logging
from typing import Optional
import uuid
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from callwise.booking.service import mask_phone_number
from callwise.config import settings
from callwise.db.models import (
    Appointment,
    Business,
    Message,
    Notification,
    Service,
    Transfer,
)
from callwise.providers.email import EmailMessage, EmailProvider, get_email_provider
from callwise.providers.messaging import MessagingProvider, get_messaging_provider

logger = logging.getLogger(__name__)


def format_currency(amount: float, tz_name: str) -> str:
    """Format price using Indian Rupee (₹) for IST or US Dollar ($) for default."""
    if tz_name and "kolkata" in tz_name.lower():
        if float(amount).is_integer():
            return f"₹{int(amount):,}"
        return f"₹{amount:,.2f}"
    return f"${amount:,.2f}"


def format_local_time(dt_utc: datetime, tz_name: str) -> str:
    """Format UTC datetime into readable local business time."""
    try:
        biz_tz = ZoneInfo(tz_name)
    except Exception:
        biz_tz = ZoneInfo("UTC")

    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    local_dt = dt_utc.astimezone(biz_tz)
    return local_dt.strftime("%A, %B %d, %Y at %I:%M %p %Z")


async def dispatch_messaging(
    session: AsyncSession,
    business_id: uuid.UUID,
    notification_type: str,
    recipient: str,
    body: str,
    channel: str = "whatsapp",
    messaging_provider: Optional[MessagingProvider] = None,
) -> Notification:
    """
    Persist notification record and deliver via MessagingProvider (WhatsApp or SMS).
    """
    provider = messaging_provider or get_messaging_provider()
    notif = Notification(
        business_id=business_id,
        type=notification_type,
        recipient=recipient,
        status="pending",
    )
    session.add(notif)
    await session.flush()

    try:
        if channel == "whatsapp":
            res = await provider.send_whatsapp(to_phone=recipient, body=body)
        else:
            res = await provider.send_sms(to_phone=recipient, body=body)

        if res.success:
            notif.status = "sent"
            notif.sent_at = datetime.now(timezone.utc)
            logger.info(f"Notification {notif.id} ({notification_type}) sent to {recipient} via {channel}")
        else:
            notif.status = "failed"
            notif.error = res.error or f"{channel.upper()} delivery failed"
            logger.warning(f"Notification {notif.id} ({notification_type}) delivery failed: {res.error}")
    except Exception as exc:
        notif.status = "failed"
        notif.error = str(exc)
        logger.error(f"Notification {notif.id} error delivering {channel} to {recipient}: {exc}")

    await session.flush()
    return notif


async def dispatch_email(
    session: AsyncSession,
    business_id: uuid.UUID,
    notification_type: str,
    recipient: str,
    subject: str,
    body_text: str,
    email_provider: Optional[EmailProvider] = None,
) -> Notification:
    """
    Persist an outgoing notification record and deliver via EmailProvider.
    Captures errors gracefully in the database without raising.
    """
    provider = email_provider or get_email_provider()
    notif = Notification(
        business_id=business_id,
        type=notification_type,
        recipient=recipient,
        status="pending",
    )
    session.add(notif)
    await session.flush()

    msg = EmailMessage(
        to=recipient,
        subject=subject,
        body_text=body_text,
    )

    try:
        success = await provider.send_email(msg)
        if success:
            notif.status = "sent"
            notif.sent_at = datetime.now(timezone.utc)
            logger.info(f"Notification {notif.id} ({notification_type}) sent to {recipient}")
        else:
            notif.status = "failed"
            notif.error = "Email provider returned False"
            logger.warning(f"Notification {notif.id} ({notification_type}) delivery failed")
    except Exception as exc:
        notif.status = "failed"
        notif.error = str(exc)
        logger.error(f"Notification {notif.id} error delivering to {recipient}: {exc}")

    await session.flush()
    return notif


async def notify_booking(
    session: AsyncSession,
    business: Business,
    appointment: Appointment,
    service: Service,
    booking_code: str,
    email_provider: Optional[EmailProvider] = None,
    messaging_provider: Optional[MessagingProvider] = None,
) -> None:
    """Send confirmation email to customer, instant WhatsApp/SMS, and alert to owner."""
    local_time = format_local_time(appointment.start_at, business.timezone)

    # 1. Customer confirmation email (if email was provided)
    if appointment.customer_email:
        currency_price = format_currency(service.price, business.timezone)
        subj = f"Appointment Confirmed: {service.name} at {business.name}"
        body = (
            f"Hello {appointment.customer_name},\n\n"
            f"Your appointment for {service.name} has been successfully booked.\n\n"
            f"Date & Time:  {local_time}\n"
            f"Duration:     {service.duration_minutes} minutes\n"
            f"Price:        {currency_price}\n\n"
            f"Your Booking Code: {booking_code}\n"
            f"(Please keep this code handy if you ever need to reschedule or cancel your visit).\n\n"
            f"Location: {business.name}\n"
            f"Contact:  {business.transfer_number or 'N/A'}\n\n"
            f"Thank you for choosing {business.name}!"
        )
        await dispatch_email(
            session=session,
            business_id=business.id,
            notification_type="customer_booking_confirmation",
            recipient=appointment.customer_email,
            subject=subj,
            body_text=body,
            email_provider=email_provider,
        )

    # 2. Instant WhatsApp & SMS to customer's mobile phone
    if appointment.customer_phone:
        currency_price = format_currency(service.price, business.timezone)
        contact_num = business.transfer_number or "our office"
        manage_link = f"{settings.app_url}/widget-frame/{business.id}?code={booking_code}"

        wa_body = (
            f"✅ *Appointment Confirmed!*\n"
            f"Hello *{appointment.customer_name}*, your visit at *{business.name}* is booked.\n\n"
            f"🗓 *Date & Time:* {local_time}\n"
            f"🩺 *Service:* {service.name} ({service.duration_minutes} mins)\n"
            f"💵 *Fee:* {currency_price}\n"
            f"🔖 *Booking Code:* `{booking_code}`\n\n"
            f"📍 *Location:* {business.name}\n"
            f"📞 *Clinic Contact:* {contact_num}\n\n"
            f"Need to reschedule or cancel? Manage your visit here:\n"
            f"{manage_link}"
        )
        await dispatch_messaging(
            session=session,
            business_id=business.id,
            notification_type="customer_booking_whatsapp",
            recipient=appointment.customer_phone,
            body=wa_body,
            channel="whatsapp",
            messaging_provider=messaging_provider,
        )

        sms_body = (
            f"{business.name}: Confirmed for {service.name} on {local_time}. "
            f"Code: {booking_code}. Fee: {currency_price}. Manage or cancel at {manage_link}"
        )
        await dispatch_messaging(
            session=session,
            business_id=business.id,
            notification_type="customer_booking_sms",
            recipient=appointment.customer_phone,
            body=sms_body,
            channel="sms",
            messaging_provider=messaging_provider,
        )

    # 3. Business owner alert email
    if business.notification_email:
        masked_phone = mask_phone_number(appointment.customer_phone)
        subj = f"New Booking: {appointment.customer_name} - {service.name}"
        body = (
            f"A new appointment has been booked via Callwise Voice Receptionist.\n\n"
            f"Customer:  {appointment.customer_name}\n"
            f"Phone:     {masked_phone}\n"
            f"Email:     {appointment.customer_email or 'Not provided'}\n"
            f"Service:   {service.name} ({service.duration_minutes}m, ${service.price:.2f})\n"
            f"Scheduled: {local_time}\n\n"
            f"Appointment ID: {appointment.id}"
        )
        await dispatch_email(
            session=session,
            business_id=business.id,
            notification_type="owner_new_booking",
            recipient=business.notification_email,
            subject=subj,
            body_text=body,
            email_provider=email_provider,
        )


async def notify_cancellation(
    session: AsyncSession,
    business: Business,
    appointment: Appointment,
    service: Service,
    email_provider: Optional[EmailProvider] = None,
    messaging_provider: Optional[MessagingProvider] = None,
) -> None:
    """Send cancellation notice to customer via Email, WhatsApp/SMS and alert owner."""
    local_time = format_local_time(appointment.start_at, business.timezone)

    # Customer email
    if appointment.customer_email:
        subj = f"Appointment Cancelled: {service.name} at {business.name}"
        body = (
            f"Hello {appointment.customer_name},\n\n"
            f"Your appointment for {service.name} on {local_time} has been cancelled.\n\n"
            f"If you did not request this cancellation or would like to rebook, please call us at "
            f"{business.transfer_number or 'our office'}.\n\n"
            f"{business.name}"
        )
        await dispatch_email(
            session=session,
            business_id=business.id,
            notification_type="customer_cancellation",
            recipient=appointment.customer_email,
            subject=subj,
            body_text=body,
            email_provider=email_provider,
        )

    # Instant WhatsApp & SMS Cancellation
    if appointment.customer_phone:
        contact_num = business.transfer_number or "our office"
        wa_body = (
            f"⚠️ *Appointment Cancelled*\n"
            f"Hello *{appointment.customer_name}*, your appointment for *{service.name}* on {local_time} has been cancelled.\n\n"
            f"If you did not request this cancellation or wish to rebook, please call {contact_num}.\n\n"
            f"*{business.name}*"
        )
        await dispatch_messaging(
            session=session,
            business_id=business.id,
            notification_type="customer_cancellation_whatsapp",
            recipient=appointment.customer_phone,
            body=wa_body,
            channel="whatsapp",
            messaging_provider=messaging_provider,
        )

        sms_body = (
            f"{business.name}: Your appointment for {service.name} on {local_time} has been cancelled. "
            f"Call {contact_num} to rebook."
        )
        await dispatch_messaging(
            session=session,
            business_id=business.id,
            notification_type="customer_cancellation_sms",
            recipient=appointment.customer_phone,
            body=sms_body,
            channel="sms",
            messaging_provider=messaging_provider,
        )

    # Owner notification
    if business.notification_email:
        subj = f"Booking Cancelled: {appointment.customer_name} - {service.name}"
        body = (
            f"An appointment has been cancelled.\n\n"
            f"Customer:  {appointment.customer_name}\n"
            f"Service:   {service.name}\n"
            f"Slot Was:  {local_time}\n\n"
            f"Appointment ID: {appointment.id}"
        )
        await dispatch_email(
            session=session,
            business_id=business.id,
            notification_type="owner_cancellation",
            recipient=business.notification_email,
            subject=subj,
            body_text=body,
            email_provider=email_provider,
        )


async def notify_reschedule(
    session: AsyncSession,
    business: Business,
    appointment: Appointment,
    service: Service,
    old_start_utc: datetime,
    new_start_utc: datetime,
    email_provider: Optional[EmailProvider] = None,
    messaging_provider: Optional[MessagingProvider] = None,
) -> None:
    """Send reschedule confirmation to customer via Email, WhatsApp/SMS and alert owner."""
    old_time = format_local_time(old_start_utc, business.timezone)
    new_time = format_local_time(new_start_utc, business.timezone)

    # Customer email
    if appointment.customer_email:
        subj = f"Appointment Rescheduled: {service.name} at {business.name}"
        body = (
            f"Hello {appointment.customer_name},\n\n"
            f"Your appointment for {service.name} has been rescheduled.\n\n"
            f"Previous Time: {old_time}\n"
            f"New Time:      {new_time}\n"
            f"Duration:      {service.duration_minutes} minutes\n\n"
            f"Location: {business.name}\n"
            f"Contact:  {business.transfer_number or 'N/A'}\n\n"
            f"Thank you!"
        )
        await dispatch_email(
            session=session,
            business_id=business.id,
            notification_type="customer_reschedule",
            recipient=appointment.customer_email,
            subject=subj,
            body_text=body,
            email_provider=email_provider,
        )

    # Instant WhatsApp & SMS Reschedule
    if appointment.customer_phone:
        contact_num = business.transfer_number or "our office"
        wa_body = (
            f"🗓 *Appointment Rescheduled!*\n"
            f"Hello *{appointment.customer_name}*, your appointment for *{service.name}* at *{business.name}* has been updated.\n\n"
            f"Previous Time: {old_time}\n"
            f"New Slot: *{new_time}*\n"
            f"Duration: {service.duration_minutes} mins\n"
            f"Contact: {contact_num}"
        )
        await dispatch_messaging(
            session=session,
            business_id=business.id,
            notification_type="customer_reschedule_whatsapp",
            recipient=appointment.customer_phone,
            body=wa_body,
            channel="whatsapp",
            messaging_provider=messaging_provider,
        )

        sms_body = (
            f"{business.name}: Your appointment for {service.name} has been rescheduled to {new_time}. "
            f"Call {contact_num} with any questions."
        )
        await dispatch_messaging(
            session=session,
            business_id=business.id,
            notification_type="customer_reschedule_sms",
            recipient=appointment.customer_phone,
            body=sms_body,
            channel="sms",
            messaging_provider=messaging_provider,
        )

    # Owner notification
    if business.notification_email:
        subj = f"Booking Rescheduled: {appointment.customer_name} - {service.name}"
        body = (
            f"An appointment was rescheduled.\n\n"
            f"Customer:      {appointment.customer_name}\n"
            f"Service:       {service.name}\n"
            f"Previous Slot: {old_time}\n"
            f"New Slot:      {new_time}\n\n"
            f"Appointment ID: {appointment.id}"
        )
        await dispatch_email(
            session=session,
            business_id=business.id,
            notification_type="owner_reschedule",
            recipient=business.notification_email,
            subject=subj,
            body_text=body,
            email_provider=email_provider,
        )


async def notify_message(
    session: AsyncSession,
    business: Business,
    message: Message,
    email_provider: Optional[EmailProvider] = None,
) -> None:
    """Notify business owner of a new recorded callback message."""
    if not business.notification_email:
        return

    time_str = format_local_time(message.created_at, business.timezone)
    subj = f"New Callback Message from {message.caller_name}"
    body = (
        f"A caller has left a message with your Callwise Voice Receptionist.\n\n"
        f"Caller Name:     {message.caller_name}\n"
        f"Callback Number: {message.callback_number}\n"
        f"Time:            {time_str}\n\n"
        f"Message / Reason:\n"
        f"{message.reason}\n\n"
        f"Message ID: {message.id}"
    )
    await dispatch_email(
        session=session,
        business_id=business.id,
        notification_type="owner_new_message",
        recipient=business.notification_email,
        subject=subj,
        body_text=body,
        email_provider=email_provider,
    )


async def notify_transfer(
    session: AsyncSession,
    business: Business,
    transfer: Transfer,
    caller_phone: Optional[str] = None,
    email_provider: Optional[EmailProvider] = None,
) -> None:
    """Notify business owner of a live call transfer escalation."""
    if not business.notification_email:
        return

    time_str = format_local_time(transfer.timestamp, business.timezone)
    masked_phone = mask_phone_number(caller_phone) if caller_phone else "Unknown"
    subj = f"Call Transfer Alert: {transfer.reason[:40]}"
    body = (
        f"A live call escalation was triggered.\n\n"
        f"Transfer Status: {transfer.status}\n"
        f"Caller Phone:    {masked_phone}\n"
        f"Time:            {time_str}\n"
        f"Reason:\n"
        f"{transfer.reason}\n\n"
        f"Transfer ID: {transfer.id}"
    )
    await dispatch_email(
        session=session,
        business_id=business.id,
        notification_type="owner_transfer_alert",
        recipient=business.notification_email,
        subject=subj,
        body_text=body,
        email_provider=email_provider,
    )


async def notify_usage_limit_reached(
    session: AsyncSession,
    business: Business,
    limit_type: str,
    current_value: float,
    limit_value: float,
    email_provider: Optional[EmailProvider] = None,
) -> None:
    """Notify business owner when a usage quota limit has been reached."""
    if not business.notification_email:
        return

    readable_type = limit_type.replace("_", " ").title()
    subj = f"Usage Limit Alert: {readable_type} Limit Reached"
    body = (
        f"Hello {business.name},\n\n"
        f"Your Callwise account has reached its monthly {readable_type} allocation.\n\n"
        f"Limit Type:     {readable_type}\n"
        f"Current Usage:  {current_value}\n"
        f"Monthly Limit:  {limit_value}\n\n"
        f"To protect your service, subsequent calls or chat inquiries will gracefully "
        f"offer to take a message until your quota resets next month or is increased by support.\n\n"
        f"Best regards,\nThe Callwise Team"
    )
    await dispatch_email(
        session=session,
        business_id=business.id,
        notification_type="owner_limit_reached",
        recipient=business.notification_email,
        subject=subj,
        body_text=body,
        email_provider=email_provider,
    )


async def notify_circuit_breaker_tripped(
    session: AsyncSession,
    business: Business,
    provider: str,
    failure_count: int,
    email_provider: Optional[EmailProvider] = None,
) -> None:
    """Notify business owner when an AI provider circuit trips and fails over."""
    if not business.notification_email:
        return

    subj = f"Alert: AI Provider '{provider.upper()}' Circuit Breaker Tripped"
    body = (
        f"Hello {business.name},\n\n"
        f"The AI provider '{provider.upper()}' has failed {failure_count} consecutive requests and its circuit has been opened.\n\n"
        f"Callwise has automatically failed over to your secondary AI provider ({settings.fallback_llm_provider.upper()}).\n"
        f"Normal operations will automatically probe and resume when the provider recovers.\n\n"
        f"Best regards,\nThe Callwise Team"
    )
    await dispatch_email(
        session=session,
        business_id=business.id,
        notification_type="owner_circuit_breaker_tripped",
        recipient=business.notification_email,
        subject=subj,
        body_text=body,
        email_provider=email_provider,
    )


async def notify_abuse_detected(
    session: AsyncSession,
    business: Business,
    caller_number: str,
    reason: str,
    email_provider: Optional[EmailProvider] = None,
) -> None:
    """Notify business owner when caller abuse or flood calls are blocked."""
    if not business.notification_email:
        return

    subj = f"Security Alert: Caller Abuse Detected ({caller_number})"
    body = (
        f"Hello {business.name},\n\n"
        f"Suspicious or abusive calling activity was detected on your reception line.\n\n"
        f"Caller Number: {caller_number}\n"
        f"Reason:        {reason}\n\n"
        f"This caller has been restricted according to your abuse protection settings.\n\n"
        f"Best regards,\nThe Callwise Team"
    )
    await dispatch_email(
        session=session,
        business_id=business.id,
        notification_type="owner_abuse_detected",
        recipient=business.notification_email,
        subject=subj,
        body_text=body,
        email_provider=email_provider,
    )


async def notify_abuse_detected_async(
    business_id: uuid.UUID,
    caller_number: str,
    reason: str,
) -> None:
    """Convenience helper to dispatch abuse detection alert asynchronously."""
    from callwise.db.session import get_async_session
    try:
        async with get_async_session() as session:
            stmt = select(Business).where(Business.id == business_id)
            biz = (await session.execute(stmt)).scalar_one_or_none()
            if biz:
                await notify_abuse_detected(
                    session=session,
                    business=biz,
                    caller_number=caller_number,
                    reason=reason,
                )
    except Exception as exc:
        logger.error(f"Failed to dispatch abuse detected notification: {exc}")


async def notify_circuit_breaker_tripped_async(
    business_id: uuid.UUID,
    provider: str,
    failure_count: int,
) -> None:
    """Convenience helper to dispatch circuit breaker tripped alert asynchronously."""
    from callwise.db.session import get_async_session
    try:
        async with get_async_session() as session:
            stmt = select(Business).where(Business.id == business_id)
            biz = (await session.execute(stmt)).scalar_one_or_none()
            if biz:
                await notify_circuit_breaker_tripped(
                    session=session,
                    business=biz,
                    provider=provider,
                    failure_count=failure_count,
                )
    except Exception as exc:
        logger.error(f"Failed to dispatch circuit breaker notification: {exc}")



