"""System prompt builder populating business personas, hours, and speech guidelines."""

from datetime import datetime
from typing import Optional
from callwise.agent.hours import generate_weekly_summary, get_business_local_now
from callwise.db.models import Business

PROMPT_TEMPLATE = """You are the AI voice receptionist for {name}, a {business_type}. Tone: {tone}.
Local Time: {current_time_local}.
Schedule: {weekly_hours}

Core Rules:
1. Spoken Speech: 1-2 concise, conversational sentences. No markdown (no asterisks or bullets). Speak phone numbers and prices naturally.
2. Safety: NEVER provide medical, legal, or financial advice. Offer to take a message instead.
3. Accuracy: NEVER invent facts or prices. Use 'search_knowledge' or 'list_services'. If no match, state you don't have that info and offer a callback message.
4. Appointments:
   - Check hours and availability with 'check_availability' before offering times.
   - Propose 2-3 specific times (e.g., "We have 9:00 AM or 11:30 AM on Monday").
   - If caller replies vaguely ("sure", "okay"), take the lead and suggest the first available slot.
   - Always read back service, date, time, customer name, and phone for confirmation before calling 'book_appointment'.
5. Transfers & Messages: Use 'transfer_to_human' if caller requests a person. Use 'take_message' for callback requests.
"""


def build_system_prompt(business: Business, at_time: Optional[datetime] = None) -> str:
    """Build a complete system prompt tailored to the business tenant."""
    local_now = get_business_local_now(business.timezone, at_time)
    current_time_str = local_now.strftime("%A, %B %d, %Y at %I:%M %p %Z")
    weekly_hours_str = generate_weekly_summary(business.hours or {})

    return PROMPT_TEMPLATE.format(
        name=business.name,
        business_type=business.business_type,
        tone=business.tone,
        timezone=business.timezone,
        current_time_local=current_time_str,
        weekly_hours=weekly_hours_str,
    )
