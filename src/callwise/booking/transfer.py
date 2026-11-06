"""Live call transfer orchestration, business hours gating, and fallback message handling."""

from datetime import datetime
import logging
from typing import Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from callwise.agent.hours import get_business_hours_status
from callwise.db.models import Business, Call, Transfer
from callwise.notifications.service import notify_transfer
from callwise.providers.email import EmailProvider
from callwise.providers.telephony import (
    TelephonyProvider,
    TransferResult,
    get_telephony_provider,
)

logger = logging.getLogger(__name__)


async def execute_transfer(
    session: AsyncSession,
    business_id: uuid.UUID,
    reason: str,
    call_id: Optional[uuid.UUID] = None,
    telephony_provider: Optional[TelephonyProvider] = None,
    email_provider: Optional[EmailProvider] = None,
    reference_now: Optional[datetime] = None,
) -> TransferResult:
    """
    Orchestrate a live call transfer to human staff.

    1. Validates that the business exists.
    2. Checks whether the business is currently open using timezone-aware business hours.
       If closed, records a transfer attempt with status 'fallback_message' and prompts the caller to leave a message.
    3. Verifies that the business has configured a human transfer phone number.
       If missing, falls back to message recording.
    4. Gated by business hours and destination number, invokes TelephonyProvider.transfer_call.
    5. Records the outcome ('completed', 'failed', or 'fallback_message') in the transfers audit table.
    6. Dispatches an alert email to the business owner if notification_email is set.
    """
    business = await session.get(Business, business_id)
    if not business:
        raise ValueError(f"Business not found: {business_id}")

    # 1. Check business hours
    hours_status = get_business_hours_status(business, at_time=reference_now)
    if not hours_status.is_open:
        transfer_record = Transfer(
            business_id=business.id,
            call_id=call_id,
            reason=reason,
            status="fallback_message",
        )
        session.add(transfer_record)
        await session.flush()
        await session.refresh(transfer_record)

        caller_phone = None
        if call_id:
            call = await session.get(Call, call_id)
            if call:
                caller_phone = call.caller_number

        try:
            await notify_transfer(
                session=session,
                business=business,
                transfer=transfer_record,
                caller_phone=caller_phone,
                email_provider=email_provider,
            )
        except Exception as e:
            logger.warning(f"Failed to dispatch transfer notification email: {e}")

        return TransferResult(
            success=False,
            status="fallback_message",
            message=(
                f"Our office is currently closed right now. {hours_status.spoken_summary} "
                f"Would you like to leave a message for our team to call you back?"
            ),
            target_phone=business.transfer_number,
        )

    # 2. Check transfer number configuration
    if not business.transfer_number:
        transfer_record = Transfer(
            business_id=business.id,
            call_id=call_id,
            reason=reason,
            status="fallback_message",
        )
        session.add(transfer_record)
        await session.flush()
        await session.refresh(transfer_record)

        caller_phone = None
        if call_id:
            call = await session.get(Call, call_id)
            if call:
                caller_phone = call.caller_number

        try:
            await notify_transfer(
                session=session,
                business=business,
                transfer=transfer_record,
                caller_phone=caller_phone,
                email_provider=email_provider,
            )
        except Exception as e:
            logger.warning(f"Failed to dispatch transfer notification email: {e}")

        return TransferResult(
            success=False,
            status="fallback_message",
            message=(
                "A transfer phone number is not currently configured for this office. "
                "Would you like to leave a message so our staff can call you back?"
            ),
            target_phone=None,
        )

    # 3. Open and destination configured: Attempt live transfer via telephony provider
    provider = telephony_provider or get_telephony_provider()
    call_result = await provider.transfer_call(
        call_id=call_id,
        target_number=business.transfer_number,
        reason=reason,
    )

    final_status = "completed" if call_result.success else "failed"

    transfer_record = Transfer(
        business_id=business.id,
        call_id=call_id,
        reason=reason,
        status=final_status,
    )
    session.add(transfer_record)
    await session.flush()
    await session.refresh(transfer_record)

    caller_phone = None
    if call_id:
        call = await session.get(Call, call_id)
        if call:
            caller_phone = call.caller_number

    try:
        await notify_transfer(
            session=session,
            business=business,
            transfer=transfer_record,
            caller_phone=caller_phone,
            email_provider=email_provider,
        )
    except Exception as e:
        logger.warning(f"Failed to dispatch transfer notification email: {e}")

    if call_result.success:
        return TransferResult(
            success=True,
            status="completed",
            message=(
                f"I am transferring you now to our team at {business.transfer_number}. "
                f"Please hold on for just a moment."
            ),
            target_phone=business.transfer_number,
        )
    else:
        return TransferResult(
            success=False,
            status="failed",
            message=(
                "I apologize, but our staff line is currently busy and unable to take your call. "
                "Would you like to leave a message so our team can call you back as soon as possible?"
            ),
            target_phone=business.transfer_number,
        )
