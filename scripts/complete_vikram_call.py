"""Execute Vikram Patel's complete booking and cancellation interaction through the live app flow."""

import asyncio
from datetime import datetime, timezone
import json
import logging
import re
import uuid

from sqlalchemy import select

from callwise.agent.text_agent import TextAgent
from callwise.calls.manager import end_call_async
from callwise.db.models import Appointment, Business, Call, VerificationAttempt
from callwise.db.session import get_async_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("vikram_cancellation")

AARAV_BIZ_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


async def ask_with_retry(agent: TextAgent, message: str, max_retries: int = 5, base_delay: float = 6.0) -> str:
    """Send caller message to TextAgent with exponential backoff on 429 rate limit."""
    delay = base_delay
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"-> Caller ({agent.caller_number}): '{message}'")
            reply = await agent.ask(message)
            logger.info(f"<- Receptionist: '{reply}'")
            await asyncio.sleep(2.0)
            return reply
        except Exception as exc:
            err_msg = str(exc)
            if "429" in err_msg or "rate" in err_msg.lower() or "too many requests" in err_msg.lower():
                logger.warning(f"Rate limited (attempt {attempt}/{max_retries}). Retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)
                delay *= 1.5
            else:
                logger.error(f"Error on turn: {exc}")
                raise


async def main():
    async with get_async_session() as session:
        business = await session.get(Business, AARAV_BIZ_ID)
        if not business:
            logger.error("Aarav clinic not found!")
            return

    logger.info(f"Initiating Vikram Patel call for {business.name}...")

    call_id = uuid.uuid4()
    caller_phone = "+910000000300"

    async with get_async_session() as session:
        call = Call(
            id=call_id,
            business_id=business.id,
            caller_number=caller_phone,
            started_at=datetime.now(timezone.utc),
        )
        session.add(call)
        await session.commit()

    agent = TextAgent(business=business, call_id=call_id, caller_number=caller_phone)

    # Turn 1: Availability query
    reply1 = await ask_with_retry(
        agent,
        "Hello, what slots do you have available for a Dental Implant Consultation on Monday, 2026-11-23?",
    )

    # Pick an offered slot
    chosen_slot = "12:00 PM"
    if "12:00" in reply1:
        chosen_slot = "12:00 PM"
    elif "2:30" in reply1:
        chosen_slot = "2:30 PM"
    elif "5:00" in reply1:
        chosen_slot = "5:00 PM"
    elif "11:00" in reply1:
        chosen_slot = "11:00 AM"
    elif "1:30" in reply1:
        chosen_slot = "1:30 PM"

    # Turn 2: Request booking for the chosen available slot
    reply2 = await ask_with_retry(
        agent,
        f"{chosen_slot} works for me. Please book the Dental Implant Consultation on Monday, 2026-11-23 at {chosen_slot} for Vikram Patel. My phone is +910000000300 and email is vikram.patel@example.test.",
    )

    # If receptionist asks for explicit confirmation before booking, confirm it
    if "confirm" in reply2.lower() or "correct" in reply2.lower() or "is that right" in reply2.lower():
        reply2 = await ask_with_retry(
            agent,
            "Yes, that is completely correct. Please confirm and book the appointment now.",
        )

    # Extract the actual booking code ONLY from the successful book_appointment tool execution
    booking_code = None
    booked_appointment_id = None
    for msg in agent.conversation_history:
        if msg.get("role") == "tool" and msg.get("name") == "book_appointment":
            content = msg.get("content", "")
            m = re.search(r"BK-[A-Z0-9]{3}", content, re.IGNORECASE)
            if m:
                booking_code = m.group(0).upper()
                logger.info(f"Successfully extracted real booking code from book_appointment tool execution: {booking_code}")
                break

    if not booking_code:
        # Fallback to direct text search on reply2 if tool content wasn't in history
        m = re.search(r"BK-[A-Z0-9]{3}", reply2, re.IGNORECASE)
        if m:
            booking_code = m.group(0).upper()

    logger.info(f"Booking code to use for cancellation: {booking_code}")
    if not booking_code:
        logger.error("Failed to obtain booking code from agent! Halting to show real failure as requested.")
        return

    # Turn 3: Cancel appointment by providing real booking code and identity verification
    reply_cancel = await ask_with_retry(
        agent,
        f"Actually, a scheduling conflict came up with my schedule and I will not be able to make it. "
        f"Can you please cancel my appointment? My booking code is {booking_code}, my name is Vikram Patel, "
        f"and my phone number is +910000000300.",
    )

    # Turn 4: Wrap up
    await ask_with_retry(agent, "Thank you very much for cancelling it for me. Have a great day!")

    # End call and generate summary
    logger.info("Ending call and generating LLM call summary...")
    await end_call_async(call_id, generate_summary=True)

    # Report final results
    async with get_async_session() as session:
        call_rec = await session.get(Call, call_id)
        appt_stmt = select(Appointment).where(
            Appointment.business_id == business.id,
            Appointment.customer_phone == caller_phone,
        ).order_by(Appointment.created_at.desc())
        appt_rec = (await session.execute(appt_stmt)).scalars().first()

        va_stmt = select(VerificationAttempt).where(
            VerificationAttempt.business_id == business.id,
            VerificationAttempt.call_id == call_id,
        ).order_by(VerificationAttempt.timestamp.desc())
        va_rec = (await session.execute(va_stmt)).scalars().first()

        print("\n" + "=" * 60)
        print("VIKRAM PATEL CALL EXECUTION RESULTS")
        print("=" * 60)
        print(f"Call ID:           {call_id}")
        print(f"Duration:          {call_rec.duration_seconds}s")
        print(f"AI Summary:        {call_rec.summary}")
        print(f"Intent:            {call_rec.intent}")
        print(f"Sentiment:         {call_rec.sentiment}")
        print(f"Urgency:           {call_rec.urgency}")
        print(f"Tags:              {call_rec.tags}")
        print("-" * 60)
        if appt_rec:
            print(f"Appointment ID:    {appt_rec.id}")
            print(f"Service:           Dental Implant Consultation & 3D CBCT Scan")
            print(f"Customer Name:     {appt_rec.customer_name}")
            print(f"Scheduled Start:   {appt_rec.start_at} UTC")
            print(f"Status:            {appt_rec.status}")
        else:
            print("Appointment:       None found in DB")
        print("-" * 60)
        if va_rec:
            print(f"Verification ID:   {va_rec.id}")
            print(f"Verified Phone:    {va_rec.phone}")
            print(f"Success:           {va_rec.success}")
            print(f"Timestamp:         {va_rec.timestamp}")
        else:
            print("Verification Attempt: None found in DB")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
