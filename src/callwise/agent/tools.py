"""LLM tool definitions: hours, knowledge search, messages, and appointment scheduling."""

from datetime import date, datetime, timedelta
import logging
from typing import Any, Callable, Dict, List, Optional
import uuid
from zoneinfo import ZoneInfo

from livekit.agents import function_tool
from sqlalchemy import select

from callwise.agent.hours import get_business_hours_status
from callwise.booking.availability import (
    format_spoken_availability,
    get_available_slots,
)
from callwise.booking.service import (
    BookingError,
    DoubleBookingError,
    MinimumNoticeError,
    OutsideBusinessHoursError,
    PastTimeError,
    book_appointment as book_appointment_svc,
)
from callwise.booking.transfer import execute_transfer
from callwise.booking.verification import (
    AppointmentAlreadyCancelledError,
    AppointmentNotFoundError,
    VerificationError,
    VerificationFailedError,
    VerificationLockoutError,
    cancel_appointment as cancel_appointment_svc,
    reschedule_appointment as reschedule_appointment_svc,
)
from callwise.db.models import Business, Call, Message, Service
from callwise.db.session import get_async_session
from callwise.knowledge.search import search_knowledge_async
from callwise.notifications.service import format_local_time

logger = logging.getLogger(__name__)


def parse_spoken_date(val: str, tz_name: str) -> date:
    """Parse relative or formatted date string to a date object in business timezone."""
    clean = val.strip().lower()
    now = datetime.now(ZoneInfo(tz_name))
    if clean in ("today", "now"):
        return now.date()
    elif clean in ("tomorrow",):
        return (now + timedelta(days=1)).date()

    try:
        return datetime.fromisoformat(clean).date()
    except Exception:
        pass

    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(clean, fmt).date()
        except Exception:
            pass
    return now.date()


def parse_spoken_datetime(val: str, tz_name: str) -> datetime:
    """Parse ISO or spoken datetime into timezone-aware datetime."""
    clean = val.strip()
    tz = ZoneInfo(tz_name)
    try:
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=tz)
        return dt.astimezone(tz)
    except Exception:
        pass

    for fmt in (
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %I:%M %p",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y %I:%M %p",
    ):
        try:
            dt = datetime.strptime(clean, fmt)
            return dt.replace(tzinfo=tz)
        except Exception:
            pass
    raise ValueError(f"Could not parse appointment time '{val}'. Please specify in YYYY-MM-DD HH:MM format.")


class CallwiseToolset:
    """Encapsulates the full suite of voice tools bound to a specific business tenant and call."""

    def __init__(
        self,
        business: Business,
        call_id: Optional[uuid.UUID] = None,
    ):
        self.business = business
        self.business_id = business.id
        self.call_id = call_id

    # 1. Business Hours
    def get_business_hours(self, day: Optional[str] = None) -> str:
        """
        Check whether the business is currently open or get opening hours for today or a specific day.

        Args:
            day: Optional day of the week (e.g. 'Monday', 'Friday', 'Saturday') to check.
        """
        status = get_business_hours_status(self.business)

        if day and str(day).strip().lower() not in ("null", "none"):
            day_clean = str(day).strip().lower()
            day_cfg = (self.business.hours or {}).get(day_clean)
            if not day_cfg or day_cfg.get("closed", False) or not day_cfg.get("open"):
                return f"On {day.capitalize()}, {self.business.name} is closed."
            open_t = day_cfg.get("open")
            close_t = day_cfg.get("close")
            return f"On {day.capitalize()}, {self.business.name} is open from {open_t} to {close_t} {self.business.timezone}."

        return f"{status.spoken_summary} Full weekly schedule: {status.weekly_schedule_summary}."

    # 2. Knowledge Retrieval
    async def search_knowledge(self, query: str) -> str:
        """
        Search the business's official documents, pricing, and services to answer caller questions.

        Args:
            query: The specific question or search keywords to look up in the business knowledge base.
        """
        result = await search_knowledge_async(
            business_id=self.business_id,
            query=query,
            call_id=self.call_id,
            log_miss=True,
        )

        if result.is_match and result.matches:
            top_match = result.matches[0]
            context_text = "\n\n".join(m.content for m in result.matches)
            return (
                f"Information found in '{top_match.source_title}':\n"
                f"{context_text}\n\n"
                "Instruction: Answer the caller's question concisely using ONLY this information. "
                "Keep your answer short for speech."
            )

        return (
            "NO MATCH: No relevant information was found in the official records. "
            "STRICT INSTRUCTION: Do NOT invent or speculate. Tell the caller you do not have "
            "that specific information in your records, and offer to take a message for the team."
        )

    # 3. Message Taking
    async def take_message(
        self,
        caller_name: str,
        callback_number: str,
        reason: str,
    ) -> str:
        """
        Take a message from the caller to request a callback or when an answer is not known.

        Args:
            caller_name: The full name of the caller.
            callback_number: The best phone number to reach the caller.
            reason: The reason for the call or inquiry details.
        """
        cleaned_name = caller_name.strip()
        cleaned_phone = callback_number.strip()
        cleaned_reason = reason.strip()

        async with get_async_session() as session:
            valid_call_id = None
            if self.call_id:
                call_obj = await session.get(Call, self.call_id)
                if not call_obj:
                    call_obj = Call(
                        id=self.call_id,
                        business_id=self.business_id,
                        caller_number="console",
                    )
                    session.add(call_obj)
                    await session.flush()
                valid_call_id = self.call_id

            msg = Message(
                business_id=self.business_id,
                call_id=valid_call_id,
                caller_name=cleaned_name,
                callback_number=cleaned_phone,
                reason=cleaned_reason,
            )
            session.add(msg)
            await session.flush()

            try:
                from callwise.notifications.service import notify_message
                await notify_message(session=session, business=self.business, message=msg)
            except Exception as exc:
                logger.error(f"Error dispatching message notification: {exc}")

        return (
            f"Message recorded successfully for {cleaned_name} at {cleaned_phone} regarding '{cleaned_reason}'. "
            "Confirm to the caller that their message has been passed to the team and thank them."
        )

    # 4. List Services
    async def list_services(self) -> str:
        """List all available bookable services, their duration in minutes, and pricing."""
        async with get_async_session() as session:
            stmt = select(Service).where(
                Service.business_id == self.business_id,
                Service.is_active == True,
            ).order_by(Service.price.asc())
            services = (await session.execute(stmt)).scalars().all()

            if not services:
                return f"There are currently no active bookable services listed for {self.business.name}."

            items = [
                f"{s.name} ({s.duration_minutes} minutes, ${s.price:.0f})"
                for s in services
            ]
            return f"We offer the following bookable services: {', '.join(items)}."

    # 5. Check Availability
    async def check_availability(self, service_name: str, date_str: str) -> str:
        """
        Check available appointment slots for a service on a given date.

        Args:
            service_name: Name of the service to check (e.g. 'Routine Dental Cleaning').
            date_str: Target date ('today', 'tomorrow', or 'YYYY-MM-DD').
        """
        target_date = parse_spoken_date(date_str, self.business.timezone)

        async with get_async_session() as session:
            stmt = select(Service).where(
                Service.business_id == self.business_id,
                Service.is_active == True,
            )
            services = (await session.execute(stmt)).scalars().all()

            matched_service = None
            for s in services:
                if (
                    service_name.lower().strip() in s.name.lower()
                    or s.name.lower() in service_name.lower().strip()
                ):
                    matched_service = s
                    break

            if not matched_service:
                avail_names = [s.name for s in services]
                return (
                    f"I could not find a service matching '{service_name}'. "
                    f"Our bookable services are: {', '.join(avail_names)}."
                )

            slots = get_available_slots(
                business=self.business,
                service=matched_service,
                target_date=target_date,
            )

            date_formatted = target_date.strftime("%A, %B %d")
            if not slots:
                return (
                    f"I checked our schedule for {matched_service.name} on {date_formatted}, "
                    f"but there are no available openings on that day. Would you like to check another date?"
                )

            return format_spoken_availability(
                available_slots=slots,
                business=self.business,
                service=matched_service,
                target_date=target_date,
            )

    # 6. Book Appointment
    async def book_appointment(
        self,
        service_name: str,
        start_time: str,
        customer_name: str,
        customer_phone: str,
        customer_email: Optional[str] = None,
    ) -> str:
        """
        Book an appointment. STRICT: Read back full details and get caller confirmation before calling this.

        Args:
            service_name: Name of the service.
            start_time: Start time in ISO format or YYYY-MM-DD HH:MM.
            customer_name: Full name of the customer.
            customer_phone: Customer's contact phone number.
            customer_email: Optional email for calendar invite and confirmation.
        """
        try:
            start_dt = parse_spoken_datetime(start_time, self.business.timezone)
        except Exception as e:
            return f"Error parsing requested start time: {e}. Please provide in format YYYY-MM-DD HH:MM."

        async with get_async_session() as session:
            stmt = select(Service).where(
                Service.business_id == self.business_id,
                Service.is_active == True,
            )
            services = (await session.execute(stmt)).scalars().all()

            matched_service = None
            for s in services:
                if (
                    service_name.lower().strip() in s.name.lower()
                    or s.name.lower() in service_name.lower().strip()
                ):
                    matched_service = s
                    break

            if not matched_service:
                avail_names = [s.name for s in services]
                return (
                    f"I could not find a service matching '{service_name}'. "
                    f"Our services are: {', '.join(avail_names)}."
                )

            valid_call_id = None
            if self.call_id:
                call_obj = await session.get(Call, self.call_id)
                if not call_obj:
                    call_obj = Call(
                        id=self.call_id,
                        business_id=self.business_id,
                        caller_number="console",
                    )
                    session.add(call_obj)
                    await session.flush()
                valid_call_id = self.call_id

            try:
                res = await book_appointment_svc(
                    session=session,
                    business_id=self.business_id,
                    service_id=matched_service.id,
                    start_time=start_dt,
                    customer_name=customer_name,
                    customer_phone=customer_phone,
                    customer_email=customer_email,
                    call_id=valid_call_id,
                )
            except DoubleBookingError:
                slots = get_available_slots(
                    business=self.business,
                    service=matched_service,
                    target_date=start_dt.date(),
                )
                if slots:
                    avail_txt = format_spoken_availability(
                        slots, self.business, matched_service, start_dt.date()
                    )
                    return f"I apologize, but {start_dt.strftime('%I:%M %p').lstrip('0')} is already booked. {avail_txt}"
                return (
                    f"I apologize, but {start_dt.strftime('%I:%M %p').lstrip('0')} is already booked, "
                    f"and there are no other openings on {start_dt.strftime('%A, %B %d')}. Would you like to check another date?"
                )
            except OutsideBusinessHoursError:
                slots = get_available_slots(
                    business=self.business,
                    service=matched_service,
                    target_date=start_dt.date(),
                )
                if slots:
                    avail_txt = format_spoken_availability(
                        slots, self.business, matched_service, start_dt.date()
                    )
                    return (
                        f"The requested time of {start_dt.strftime('%I:%M %p').lstrip('0')} is outside our office operating hours or ends after closing time. "
                        f"{avail_txt}"
                    )
                return (
                    f"The requested time is outside our office operating hours, and we are closed or have no openings on {start_dt.strftime('%A, %B %d')}. "
                    "Would you like to check our hours or look at another date?"
                )
            except (PastTimeError, MinimumNoticeError) as e:
                return f"I cannot book that slot: {e}. Please choose a time further in advance."
            except BookingError as e:
                return f"Unable to complete booking: {e}."

            local_str = format_local_time(res.appointment.start_at, self.business.timezone)
            email_note = (
                f" A confirmation email and calendar invitation have been sent to {customer_email}."
                if customer_email
                else ""
            )
            return (
                f"Your appointment for {matched_service.name} is successfully confirmed for {local_str}! "
                f"Your booking reference code is {res.booking_code}.{email_note} "
                f"We look forward to seeing you then."
            )

    # 7. Cancel Appointment
    async def cancel_appointment(
        self,
        booking_code: str,
        caller_name: Optional[str] = None,
        caller_phone: Optional[str] = None,
    ) -> str:
        """
        Cancel an existing appointment. Always ask for booking code and verify name/phone first.

        Args:
            booking_code: 6-character booking code (e.g. 'BK-4X2').
            caller_name: Customer's full name for identity verification.
            caller_phone: Customer's phone number for identity verification.
        """
        async with get_async_session() as session:
            try:
                appt = await cancel_appointment_svc(
                    session=session,
                    business_id=self.business_id,
                    booking_code=booking_code,
                    caller_name=caller_name,
                    caller_phone=caller_phone,
                    call_id=self.call_id,
                )
            except VerificationLockoutError as e:
                return (
                    f"Verification lockout: {e}. "
                    "For security reasons, this appointment cannot be modified via phone right now. "
                    "Please contact our office staff directly."
                )
            except VerificationFailedError as e:
                return (
                    f"Verification failed: {e}. "
                    "Please double-check the booking code, or provide the exact name or phone number "
                    "used when booking."
                )
            except AppointmentAlreadyCancelledError:
                return f"Appointment {booking_code.upper()} has already been cancelled."
            except AppointmentNotFoundError:
                return f"I could not find an active appointment with booking code {booking_code.upper()}."
            except VerificationError as e:
                return f"Cancellation could not be completed: {e}."

            time_str = format_local_time(appt.start_at, self.business.timezone)
            return (
                f"Your appointment for {time_str} (booking code {booking_code.upper()}) "
                f"has been successfully cancelled. A cancellation confirmation has been sent to your email. "
                f"Please let us know if you need to schedule a new visit in the future."
            )

    # 8. Reschedule Appointment
    async def reschedule_appointment(
        self,
        booking_code: str,
        new_time: str,
        caller_name: Optional[str] = None,
        caller_phone: Optional[str] = None,
    ) -> str:
        """
        Reschedule an existing appointment to a new date and time.

        Args:
            booking_code: 6-character booking code (e.g. 'BK-4X2').
            new_time: Desired new appointment start time (e.g. '2026-11-12 14:00').
            caller_name: Customer's full name for identity verification.
            caller_phone: Customer's phone number for identity verification.
        """
        try:
            new_dt = parse_spoken_datetime(new_time, self.business.timezone)
        except Exception as e:
            return f"Error parsing new time: {e}. Please provide in format YYYY-MM-DD HH:MM."

        async with get_async_session() as session:
            try:
                appt = await reschedule_appointment_svc(
                    session=session,
                    business_id=self.business_id,
                    booking_code=booking_code,
                    new_start_time=new_dt,
                    caller_name=caller_name,
                    caller_phone=caller_phone,
                    call_id=self.call_id,
                )
            except VerificationLockoutError as e:
                return f"Verification lockout: {e}. Please contact our office staff directly."
            except VerificationFailedError as e:
                return f"Verification failed: {e}. Please verify your booking code and name or phone."
            except (DoubleBookingError, OutsideBusinessHoursError, BookingError) as e:
                return f"Cannot reschedule to that slot: {e}."
            except VerificationError as e:
                return f"Rescheduling error: {e}."

            time_str = format_local_time(appt.start_at, self.business.timezone)
            return (
                f"Your appointment has been successfully rescheduled to {time_str}! "
                f"Your booking code remains {booking_code.upper()}. "
                f"Updated confirmation details have been sent to your email."
            )

    # 9. Live Transfer to Human
    async def transfer_to_human(self, reason: str) -> str:
        """
        Transfer the caller to human staff.

        Args:
            reason: Specific reason the caller requested human escalation.
        """
        async with get_async_session() as session:
            result = await execute_transfer(
                session=session,
                business_id=self.business_id,
                reason=reason,
                call_id=self.call_id,
            )
            return result.message

    def get_livekit_tools(self) -> List[Any]:
        """Wrap all 9 tool methods with LiveKit's @function_tool decorator."""
        toolset = self

        @function_tool
        def get_business_hours(day: Optional[str] = None) -> str:
            """Check whether the business is currently open or get operating hours for today or a specific day."""
            return toolset.get_business_hours(day=day)

        @function_tool
        async def search_knowledge(query: str) -> str:
            """Search official business documents, pricing, and services to answer caller questions."""
            return await toolset.search_knowledge(query=query)

        @function_tool
        async def take_message(caller_name: str, callback_number: str, reason: str) -> str:
            """Take a message and callback request from the caller."""
            return await toolset.take_message(
                caller_name=caller_name,
                callback_number=callback_number,
                reason=reason,
            )

        @function_tool
        async def list_services() -> str:
            """List all bookable services, durations, and pricing."""
            return await toolset.list_services()

        @function_tool
        async def check_availability(service_name: str, date: str) -> str:
            """Check open appointment slots for a service on a given date (e.g. 'today', 'tomorrow', 'YYYY-MM-DD')."""
            return await toolset.check_availability(service_name=service_name, date_str=date)

        @function_tool
        async def book_appointment(
            service_name: str,
            start_time: str,
            customer_name: str,
            customer_phone: str,
            customer_email: Optional[str] = None,
        ) -> str:
            """Book an appointment for a caller. Must confirm details with caller before calling this."""
            return await toolset.book_appointment(
                service_name=service_name,
                start_time=start_time,
                customer_name=customer_name,
                customer_phone=customer_phone,
                customer_email=customer_email,
            )

        @function_tool
        async def cancel_appointment(
            booking_code: str,
            caller_name: Optional[str] = None,
            caller_phone: Optional[str] = None,
        ) -> str:
            """Cancel an existing appointment with booking code and verified name/phone."""
            return await toolset.cancel_appointment(
                booking_code=booking_code,
                caller_name=caller_name,
                caller_phone=caller_phone,
            )

        @function_tool
        async def reschedule_appointment(
            booking_code: str,
            new_time: str,
            caller_name: Optional[str] = None,
            caller_phone: Optional[str] = None,
        ) -> str:
            """Reschedule an existing appointment to a new date and time with verification."""
            return await toolset.reschedule_appointment(
                booking_code=booking_code,
                new_time=new_time,
                caller_name=caller_name,
                caller_phone=caller_phone,
            )

        @function_tool
        async def transfer_to_human(reason: str) -> str:
            """Transfer the caller to a human staff representative or team member."""
            return await toolset.transfer_to_human(reason=reason)

        return [
            get_business_hours,
            search_knowledge,
            take_message,
            list_services,
            check_availability,
            book_appointment,
            cancel_appointment,
            reschedule_appointment,
            transfer_to_human,
        ]
