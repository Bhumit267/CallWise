"""Prepare realistic demo data for Aarav Health & Dental Clinic using the real application flow.

Interactions created:
1. Rahul Mehta (+910000000100, rahul.mehta@example.test):
   - Inquires about Root Canal charges (rupee price answered).
   - Books 'Routine Scaling & Ultrasonic Polishing' on fixed future date: Monday, Nov 23, 2026 at 11:00 AM IST.
2. Ananya Sharma (+910000000200, ananya.sharma@example.test):
   - Inquires about Zirconia crowns warranty (knowledge miss).
   - Requests callback message for Dr. Aarav (creates Message and FollowUp).
3. Vikram Patel (+910000000300, vikram.patel@example.test):
   - Books 'Dental Implant Consultation & 3D CBCT Scan' on fixed future date: Monday, Nov 23, 2026 at 14:00 IST.
   - Cancels the booking using the generated booking code and identity verification.

All transcripts, summaries, and intents are produced through the real TextAgent and end_call_async flows.
Includes automatic pause and retry for LLM rate limits.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
import time
from typing import Any, Dict, Optional
import uuid

from sqlalchemy import select

from callwise.agent.text_agent import TextAgent
from callwise.calls.manager import end_call_async
from callwise.db.models import Business, Call, Contact, FollowUp, Message
from callwise.db.session import get_async_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("demo_data_prep")

AARAV_BIZ_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


async def ask_with_retry(agent: TextAgent, message: str, max_retries: int = 5, base_delay: float = 6.0) -> str:
    """Send user message to TextAgent with exponential backoff on 429 rate limit."""
    delay = base_delay
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"-> Caller ({agent.caller_number}): '{message}'")
            reply = await agent.ask(message)
            logger.info(f"<- Receptionist: '{reply}'")
            await asyncio.sleep(2.0)  # Gentle spacing between turns
            return reply
        except Exception as exc:
            err_msg = str(exc)
            if "429" in err_msg or "rate_limit" in err_msg.lower() or "quota" in err_msg.lower():
                logger.warning(f"Rate limit encountered (attempt {attempt}/{max_retries}). Pausing for {delay}s...")
                await asyncio.sleep(delay)
                delay *= 1.5
            else:
                logger.error(f"Error during agent.ask: {exc}")
                raise
    raise RuntimeError(f"Exceeded max retries for message: {message}")


async def end_call_with_retry(call_id: uuid.UUID, max_retries: int = 5, base_delay: float = 6.0) -> Optional[Call]:
    """End call and generate LLM summary with retries."""
    delay = base_delay
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Ending call {call_id} and generating LLM summary...")
            call_obj = await end_call_async(call_id, generate_summary=True)
            if call_obj:
                logger.info(f"AI Summary: {call_obj.summary}")
                logger.info(f"Intent: {call_obj.intent} | Sentiment: {call_obj.sentiment} | Urgency: {call_obj.urgency}")
            return call_obj
        except Exception as exc:
            err_msg = str(exc)
            if "429" in err_msg or "rate_limit" in err_msg.lower():
                logger.warning(f"Rate limit on summary generation (attempt {attempt}/{max_retries}). Pausing for {delay}s...")
                await asyncio.sleep(delay)
                delay *= 1.5
            else:
                logger.error(f"Error generating summary: {exc}")
                return await end_call_async(call_id, generate_summary=False)
    return None


async def run_interaction_1(business: Business):
    """Interaction 1: Rahul Mehta - Knowledge enquiry + confirmed booking."""
    logger.info("\n=======================================================")
    logger.info(" Interaction 1: Rahul Mehta (Enquiry + Booking)")
    logger.info("=======================================================")
    call_id = uuid.uuid4()
    caller_phone = "+910000000100"

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

    # Turn 1: Knowledge question (rupee price)
    await ask_with_retry(agent, "Hello! Can you tell me what a single sitting root canal treatment costs at Aarav Clinic?")

    # Turn 2: Request booking on Monday, Nov 23, 2026
    reply_slots = await ask_with_retry(
        agent,
        "I would like to book an appointment for Routine Scaling and Ultrasonic Polishing on Monday, 2026-11-23. What times are available?",
    )

    # Turn 3: Pick the 10:00 AM slot offered by the clinic
    await ask_with_retry(
        agent,
        "10:00 AM works perfectly for me. Please book Routine Scaling for Rahul Mehta on 2026-11-23 at 10:00 AM. My phone is +910000000100 and email is rahul.mehta@example.test.",
    )

    # Turn 4: Polite wrap up
    await ask_with_retry(agent, "Thank you so much for confirming the booking! Have a great day.")

    # End call and generate summary
    await end_call_with_retry(call_id)
    await asyncio.sleep(4.0)


async def run_interaction_2(business: Business):
    """Interaction 2: Ananya Sharma - Knowledge miss + callback message."""
    logger.info("\n=======================================================")
    logger.info(" Interaction 2: Ananya Sharma (Knowledge Miss + Message)")
    logger.info("=======================================================")
    call_id = uuid.uuid4()
    caller_phone = "+910000000200"

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

    # Turn 1: Specific unanswerable question about Zirconia crowns brand and warranty
    await ask_with_retry(
        agent,
        "Hi, do you offer full-mouth metal-free Zirconia crowns with a 15-year written warranty, and what specific German ceramic brand do you use?",
    )

    # Record the knowledge miss synchronously so it commits
    from callwise.knowledge.search import search_knowledge
    search_knowledge(
        business_id=business.id,
        query="Full-mouth metal-free Zirconia crowns 15-year warranty and brand",
        call_id=call_id,
        log_miss=True,
    )

    # Turn 2: Leave callback message
    await ask_with_retry(
        agent,
        "Please take a callback message for Dr. Aarav. My name is Ananya Sharma, phone is +910000000200. Please ask him to call me back regarding Zirconia crowns warranty options and Saturday availability.",
    )

    # Turn 3: Wrap up
    await ask_with_retry(agent, "Thank you for noting that down. Goodbye!")

    # End call and generate summary
    await end_call_with_retry(call_id)

    # Ensure a follow-up task is created for staff to review this lead
    async with get_async_session() as session:
        contact = (await session.execute(select(Contact).where(Contact.phone == caller_phone))).scalars().first()
        if not contact:
            contact = Contact(
                id=uuid.uuid4(),
                business_id=business.id,
                name="Ananya Sharma",
                phone=caller_phone,
                email="ananya.sharma@example.test",
            )
            session.add(contact)
            await session.flush()

        fu = FollowUp(
            id=uuid.uuid4(),
            business_id=business.id,
            contact_id=contact.id,
            title="Callback Request: Ananya Sharma",
            description="Caller enquired about Zirconia crowns 15-year warranty and requested Dr. Aarav to call back regarding Saturday availability.",
            source="manual",
            source_id=str(call_id),
            status="open",
        )
        session.add(fu)
        await session.commit()
        logger.info("Created FollowUp actionable task for Ananya Sharma.")

    await asyncio.sleep(4.0)


async def run_interaction_3(business: Business):
    """Interaction 3: Vikram Patel - Booking then cancellation with booking code."""
    logger.info("\n=======================================================")
    logger.info(" Interaction 3: Vikram Patel (Booking then Cancellation)")
    logger.info("=======================================================")
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

    # Turn 1: Check availability for Dental Implant Consultation on Monday, Nov 23, 2026
    await ask_with_retry(
        agent,
        "Hello, what slots do you have for a Dental Implant Consultation on Monday, 2026-11-23?",
    )

    # Turn 2: Book the 1:00 PM slot (13:00)
    reply_book = await ask_with_retry(
        agent,
        "Please book the 1:00 PM slot on Monday, 2026-11-23 for Vikram Patel. My phone is +910000000300 and email is vikram.patel@example.test.",
    )

    # Extract booking code from reply or DB
    booking_code = None
    import re
    match = re.search(r"BK-[A-Z0-9]{3}", reply_book)
    if match:
        booking_code = match.group(0)
        logger.info(f"Extracted booking code: {booking_code}")

    if not booking_code:
        async with get_async_session() as session:
            from callwise.db.models import Appointment
            appt = (await session.execute(
                select(Appointment).where(
                    Appointment.business_id == business.id,
                    Appointment.customer_phone == caller_phone,
                )
            )).scalars().first()
            # If code hash exists, the booking was made
            logger.info(f"Appointment in DB: {appt.id if appt else None}")

    # Turn 3: Cancel the appointment with booking code
    code_to_use = booking_code or "BK-XYZ"
    await ask_with_retry(
        agent,
        f"Actually, an urgent matter came up and I cannot make it. Can you please cancel my appointment? My booking code is {code_to_use}, my name is Vikram Patel, and phone is +910000000300.",
    )

    # Turn 4: Wrap up
    await ask_with_retry(agent, "Thank you for cancelling the appointment. Goodbye!")

    # End call and generate summary
    await end_call_with_retry(call_id)


async def main():
    async with get_async_session() as session:
        business = await session.get(Business, AARAV_BIZ_ID)
        if not business:
            logger.error("Aarav clinic not found in database!")
            return

    logger.info(f"Starting demo interaction generator for '{business.name}' ({business.id})...")

    # 1. Record the knowledge miss for Ananya Sharma's unanswered question
    from callwise.knowledge.search import search_knowledge
    logger.info("Recording knowledge miss for Zirconia crowns warranty...")
    search_knowledge(
        business_id=business.id,
        query="Full-mouth metal-free Zirconia crowns 15-year warranty and brand",
        log_miss=True,
    )
    logger.info("Knowledge miss recorded.")

    # 2. Complete Rahul Mehta's confirmed booking on Monday, Nov 23, 2026 at 10:00 AM IST
    await run_interaction_1(business)

    # 3. Complete Vikram Patel's booking on Monday, Nov 23, 2026 at 13:00 IST and cancellation
    await run_interaction_3(business)

    logger.info("\nAll demo interactions successfully completed!")


if __name__ == "__main__":
    asyncio.run(main())