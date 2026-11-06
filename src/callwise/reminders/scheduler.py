"""Reminder processing engine and scheduler daemon for customer appointment reminders."""

import asyncio
from datetime import datetime, timezone
import logging
import signal
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from callwise.booking.service import mask_phone_number
from callwise.db.models import Appointment, Business, Notification, Reminder, Service
from callwise.db.session import AsyncSessionLocal
from callwise.notifications.service import format_local_time
from callwise.providers.email import EmailMessage, EmailProvider, get_email_provider

logger = logging.getLogger(__name__)


async def trigger_reminder_call(
    session: AsyncSession,
    reminder: Reminder,
    appointment: Appointment,
    business: Business,
    service: Service,
) -> bool:
    """
    Trigger an automated 2-hour advance reminder phone call to the customer.
    Simulates / delivers the automated outbound voice message and audits in notifications table.
    """
    if not appointment.customer_phone:
        return False

    local_time = format_local_time(appointment.start_at, business.timezone)
    masked_phone = mask_phone_number(appointment.customer_phone)

    spoken_script = (
        f"Hello {appointment.customer_name}, this is an automated reminder from {business.name}. "
        f"You have an upcoming appointment for {service.name} today at {local_time}. "
        f"If you need to reach us or make any changes, please call {business.transfer_number or 'our office'}. "
        f"We look forward to seeing you soon!"
    )

    call_banner = [
        "\n" + "=" * 60,
        " [AUTOMATED REMINDER CALL: 2 HOURS PRIOR TO APPOINTMENT]",
        "=" * 60,
        f"To:       {appointment.customer_phone} ({masked_phone})",
        f"Customer: {appointment.customer_name}",
        f"Business: {business.name}",
        f"Service:  {service.name}",
        f"Time:     {local_time}",
        "-" * 60,
        f"Spoken Voice Message:\n\"{spoken_script}\"",
        "=" * 60 + "\n",
    ]
    print("\n".join(call_banner))
    logger.info(
        f"[Automated Reminder Call] Placed to {masked_phone} for appointment {appointment.id}"
    )

    notif = Notification(
        business_id=business.id,
        type="customer_reminder_call_2h",
        recipient=appointment.customer_phone,
        status="sent",
        sent_at=datetime.now(timezone.utc),
    )
    session.add(notif)
    await session.flush()
    return True


async def send_reminder_email(
    session: AsyncSession,
    reminder: Reminder,
    appointment: Appointment,
    business: Business,
    service: Service,
    email_provider: Optional[EmailProvider] = None,
) -> bool:
    """
    Deliver 24-hour appointment reminder email to customer and track in notifications table.
    """
    if not appointment.customer_email:
        return False

    provider = email_provider or get_email_provider()
    local_time = format_local_time(appointment.start_at, business.timezone)

    subject = f"Reminder: Upcoming {service.name} tomorrow at {business.name}"
    body = (
        f"Hello {appointment.customer_name},\n\n"
        f"This is a friendly reminder that you have an upcoming appointment scheduled for tomorrow:\n\n"
        f"Service:      {service.name}\n"
        f"Scheduled:    {local_time}\n"
        f"Duration:     {service.duration_minutes} minutes\n"
        f"Provider:     {business.name}\n"
        f"Phone/Office: {business.transfer_number or 'Contact clinic'}\n\n"
        f"If you need to reschedule or cancel, please contact us promptly or provide your booking code "
        f"over the phone.\n\n"
        f"We look forward to seeing you tomorrow!\n\n"
        f"— {business.name}"
    )

    msg = EmailMessage(
        to=appointment.customer_email,
        subject=subject,
        body_text=body,
    )

    notif = Notification(
        business_id=business.id,
        type="customer_reminder_24h",
        recipient=appointment.customer_email,
        status="pending",
    )
    session.add(notif)
    await session.flush()

    try:
        sent = await provider.send_email(msg)
        if sent:
            notif.status = "sent"
            notif.sent_at = datetime.now(timezone.utc)
            logger.info(
                f"Reminder email sent to {appointment.customer_email} for appointment {appointment.id}"
            )
            return True
        else:
            notif.status = "failed"
            notif.error = "Email provider returned False"
            logger.warning(f"Reminder delivery failed for {appointment.id}")
            return False
    except Exception as exc:
        notif.status = "failed"
        notif.error = str(exc)
        logger.error(f"Error sending reminder email for appointment {appointment.id}: {exc}")
        return False


async def process_due_reminders(
    session: AsyncSession,
    business_id: Optional[uuid.UUID] = None,
    reference_now: Optional[datetime] = None,
    email_provider: Optional[EmailProvider] = None,
) -> int:
    """
    Find and deliver all due appointment reminders (send_at <= now).
    Handles both 24-hour advance emails and 2-hour advance automated phone calls.
    Uses 'SELECT ... FOR UPDATE SKIP LOCKED' to guarantee zero duplicate delivery.

    Args:
        session: Active AsyncSession within a transaction.
        business_id: Optional UUID to scope reminders to a specific business.
        reference_now: Optional reference current datetime (defaults to UTC now).
        email_provider: Optional EmailProvider.

    Returns:
        Count of successfully processed and delivered reminders.
    """
    now_utc = reference_now if reference_now is not None else datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    # Lock due reminders and skip any currently being processed by another worker
    stmt = (
        select(Reminder)
        .where(
            Reminder.status == "pending",
            Reminder.send_at <= now_utc,
        )
    )
    if business_id is not None:
        stmt = stmt.where(Reminder.business_id == business_id)

    stmt = stmt.with_for_update(skip_locked=True)
    reminders = (await session.execute(stmt)).scalars().all()

    if not reminders:
        return 0

    processed = 0
    for rem in reminders:
        # Load appointment
        appt = await session.get(Appointment, rem.appointment_id)
        if not appt:
            rem.status = "cancelled"
            continue

        # If appointment was cancelled or is no longer booked, mark reminder cancelled
        if appt.status != "booked":
            logger.info(
                f"Skipping reminder {rem.id} because appointment {appt.id} is {appt.status}"
            )
            rem.status = "cancelled"
            continue

        # Load business & service
        biz = await session.get(Business, rem.business_id)
        svc = await session.get(Service, appt.service_id)
        if not biz or not svc:
            logger.warning(f"Missing business or service for reminder {rem.id}")
            rem.status = "failed"
            continue

        # Dispatch based on reminder channel
        if rem.channel == "call":
            # Automated 2-hour reminder call
            success = await trigger_reminder_call(
                session=session,
                reminder=rem,
                appointment=appt,
                business=biz,
                service=svc,
            )
        else:
            # 24-hour advance email reminder
            if not appt.customer_email:
                logger.info(f"Skipping email reminder {rem.id}: no customer email on file")
                rem.status = "skipped"
                continue

            success = await send_reminder_email(
                session=session,
                reminder=rem,
                appointment=appt,
                business=biz,
                service=svc,
                email_provider=email_provider,
            )

        if success:
            rem.status = "sent"
            processed += 1
        else:
            rem.status = "failed"

    await session.flush()
    return processed


async def run_scheduler(
    poll_interval: int = 60,
    run_once: bool = False,
    business_id: Optional[uuid.UUID] = None,
    email_provider: Optional[EmailProvider] = None,
) -> None:
    """
    Scheduler process loop that wakes up periodically to dispatch due reminders.
    """
    logger.info(
        f"Callwise Scheduler started (Interval: {poll_interval}s, Run-once: {run_once}, Business: {business_id or 'all'})"
    )

    stop_event = asyncio.Event()

    def _handle_exit():
        logger.info("Shutdown signal received for Callwise Scheduler.")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_exit)
        except (NotImplementedError, RuntimeError):
            # Windows signal handlers
            pass

    while not stop_event.is_set():
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    count = await process_due_reminders(
                        session=session,
                        business_id=business_id,
                        email_provider=email_provider,
                    )
                    if count > 0:
                        logger.info(f"[Scheduler] Dispatched {count} due reminder(s)")
        except Exception as exc:
            logger.error(f"[Scheduler Error] Exception during reminder cycle: {exc}")

        if run_once:
            break

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=poll_interval)
        except asyncio.TimeoutError:
            pass

    logger.info("Callwise Scheduler stopped gracefully.")
