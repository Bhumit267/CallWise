"""Telephony routing: Map dialed phone numbers to business tenants and resolve caller identity."""

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import re
from typing import Optional, Tuple
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from callwise.db.models import BlocklistEntry, Business, Call, Contact, PhoneNumber
from callwise.db.session import get_async_session

logger = logging.getLogger(__name__)


def normalize_e164(phone: str) -> str:
    """Normalize phone number to standardized E.164 string format (e.g. +15551234567)."""
    if not phone:
        return ""
    digits = re.sub(r"[^\d+]", "", phone.strip())
    if not digits.startswith("+"):
        # Assume US +1 if 10 digits
        if len(digits) == 10:
            digits = "+1" + digits
        else:
            digits = "+" + digits
    return digits


@dataclass
class InboundRouteResult:
    """Result of resolving an incoming telephone call."""
    matched: bool
    business: Optional[Business] = None
    phone_number: Optional[PhoneNumber] = None
    contact: Optional[Contact] = None
    is_blocked: bool = False
    reject_reason: Optional[str] = None
    reply_message: Optional[str] = None


async def resolve_inbound_call_async(
    dialed_number: str,
    caller_number: Optional[str] = None,
    caller_name: Optional[str] = None,
) -> InboundRouteResult:
    """
    Route an inbound phone call:
    1. Normalize numbers.
    2. Lookup dialed number in `phone_numbers` table.
    3. Check `blocklist` for caller number abuse.
    4. Match or create caller Contact record.
    5. Fallback gracefully with polite message if number is unknown.
    """
    norm_dialed = normalize_e164(dialed_number)
    norm_caller = normalize_e164(caller_number) if caller_number else ""

    async with get_async_session() as session:
        # 1. Resolve business from dialed number
        phone_stmt = (
            select(PhoneNumber)
            .where(PhoneNumber.e164_number == norm_dialed, PhoneNumber.is_active.is_(True))
            .options(selectinload(PhoneNumber.business))
        )
        phone_record = (await session.execute(phone_stmt)).scalar_one_or_none()

        if not phone_record or not phone_record.business:
            logger.info(f"[Inbound Router] Unknown dialed number: {norm_dialed}. Returning polite hangup.")
            return InboundRouteResult(
                matched=False,
                reply_message="Thank you for calling. This number is not currently in service or configured. Goodbye.",
                reject_reason="unknown_dialed_number",
            )

        business = phone_record.business

        # 2. Check tenant blocklist
        if norm_caller:
            now_utc = datetime.now(timezone.utc)
            block_stmt = select(BlocklistEntry).where(
                BlocklistEntry.business_id == business.id,
                BlocklistEntry.identifier_type == "phone",
                BlocklistEntry.identifier_value == norm_caller,
            )
            blocked_entry = (await session.execute(block_stmt)).scalar_one_or_none()
            if blocked_entry:
                # Check expiration
                if blocked_entry.blocked_until is None or blocked_entry.blocked_until > now_utc:
                    logger.warning(
                        f"[Inbound Router] Blocked caller {norm_caller} attempted call to business {business.id}"
                    )
                    return InboundRouteResult(
                        matched=True,
                        business=business,
                        phone_number=phone_record,
                        is_blocked=True,
                        reject_reason="caller_in_blocklist",
                        reply_message="We are unable to connect your call at this time. Goodbye.",
                    )

        # 3. Match or create contact from caller ID
        # NOTE: Caller ID can be spoofed; contacts matched via caller ID are not verified for bookings.
        contact_record = None
        if norm_caller:
            contact_stmt = select(Contact).where(
                Contact.business_id == business.id,
                Contact.phone == norm_caller,
            )
            contact_record = (await session.execute(contact_stmt)).scalar_one_or_none()

            if not contact_record and caller_name:
                contact_record = Contact(
                    id=uuid.uuid4(),
                    business_id=business.id,
                    name=caller_name.strip() or "Caller",
                    phone=norm_caller,
                )
                session.add(contact_record)
                await session.commit()
            elif not contact_record:
                contact_record = Contact(
                    id=uuid.uuid4(),
                    business_id=business.id,
                    name="Caller " + norm_caller[-4:],
                    phone=norm_caller,
                )
                session.add(contact_record)
                await session.commit()

        return InboundRouteResult(
            matched=True,
            business=business,
            phone_number=phone_record,
            contact=contact_record,
            is_blocked=False,
        )


async def create_inbound_call_record_async(
    route: InboundRouteResult,
    caller_number: Optional[str] = None,
    call_id: Optional[uuid.UUID] = None,
) -> Call:
    """Create initial Call session database record for an incoming phone call."""
    cid = call_id or uuid.uuid4()
    norm_caller = normalize_e164(caller_number) if caller_number else "unknown"

    async with get_async_session() as session:
        call = Call(
            id=cid,
            business_id=route.business.id if route.business else uuid.uuid4(),
            contact_id=route.contact.id if route.contact else None,
            caller_number=norm_caller,
            started_at=datetime.now(timezone.utc),
            summary="Inbound telephony call",
        )
        session.add(call)
        await session.commit()
        return call
