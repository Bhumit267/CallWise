"""Abuse protection: per-caller rate limiting, tenant blocklist, and nonsense detection."""

from datetime import datetime, timedelta, timezone
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from callwise.config import settings
from callwise.db.models import BlocklistEntry, Business, Call

logger = logging.getLogger(__name__)

# Common gibberish patterns (e.g. keyboard smashes like "asdfghjk", "qwertyuiop")
KEYBOARD_SMASH_REGEX = re.compile(
    r"^(asdf|qwer|zxcv|1234|abcd|hjkl|jkl;|testtest|bla+h+|na+h+)", re.IGNORECASE
)


def detect_nonsense_repetition(recent_caller_utterances: List[str]) -> bool:
    """
    Detect repeated nonsensical or spam caller utterances.
    Returns True if:
    1. The last 3 non-empty caller utterances are identical.
    2. The caller has sent 3 consecutive single-character or keyboard smash utterances.
    """
    if len(recent_caller_utterances) < 3:
        return False

    last_three = [u.strip().lower() for u in recent_caller_utterances[-3:]]

    # Check 1: 3 identical utterances in a row
    if last_three[0] == last_three[1] == last_three[2] and len(last_three[0]) > 0:
        return True

    # Check 2: 3 consecutive single-character or 2-character utterances
    if all(len(u) <= 2 for u in last_three):
        return True

    # Check 3: 3 consecutive keyboard smashes
    if all(KEYBOARD_SMASH_REGEX.match(u) for u in last_three):
        return True

    return False


async def is_caller_blocked(
    session: AsyncSession,
    caller_number: str,
    business_id: uuid.UUID,
) -> Tuple[bool, Optional[str]]:
    """
    Check if a caller phone number is on the blocklist for the tenant business.
    Returns (is_blocked, reason).
    """
    clean_number = caller_number.strip()
    now = datetime.now(timezone.utc)

    stmt = select(BlocklistEntry).where(
        BlocklistEntry.business_id == business_id,
        BlocklistEntry.identifier_type == "phone",
        BlocklistEntry.identifier_value == clean_number,
    )
    entry = (await session.execute(stmt)).scalar_one_or_none()

    if not entry:
        return False, None

    # Check expiration
    if entry.blocked_until and entry.blocked_until <= now:
        # Expired block entry, remove it
        await session.delete(entry)
        await session.flush()
        return False, None

    logger.warning(
        f"[Blocklist] Blocked incoming call from '{clean_number}' for business {business_id}. Reason: {entry.reason}"
    )
    return True, entry.reason


async def check_caller_rate_limit(
    session: AsyncSession,
    caller_number: str,
    business_id: uuid.UUID,
    window_hours: int = 1,
) -> Tuple[bool, int, str]:
    """
    Enforce per-caller rate limit (e.g. max 5 calls per hour).
    Returns (is_rate_limited, call_count, rejection_message).
    """
    clean_number = caller_number.strip()
    # Skip rate limiting for internal test/widget sessions or unknown callers
    if clean_number.lower() in ("unknown", "anonymous") or clean_number.startswith("widget_"):
        return False, 0, ""

    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=window_hours)

    count_stmt = select(func.count(Call.id)).where(
        Call.business_id == business_id,
        Call.caller_number == clean_number,
        Call.started_at >= cutoff_time,
    )
    call_count = (await session.execute(count_stmt)).scalar() or 0

    max_calls = settings.max_calls_per_caller_hour

    if call_count >= max_calls:
        logger.warning(
            f"[Abuse Protection] Caller '{clean_number}' exceeded hourly call limit ({call_count}/{max_calls}) for business {business_id}."
        )
        msg = (
            "You have reached the maximum number of calls allowed within one hour. "
            "Please call back later or submit an inquiry through our website. Goodbye."
        )
        return True, call_count, msg

    return False, call_count, ""


async def add_to_blocklist(
    session: AsyncSession,
    business_id: uuid.UUID,
    caller_number: str,
    reason: str = "Spam / Abusive caller",
    expires_in_days: Optional[int] = None,
) -> BlocklistEntry:
    """Add a telephone number to the tenant's blocklist."""
    clean_number = caller_number.strip()
    now = datetime.now(timezone.utc)
    blocked_until = (now + timedelta(days=expires_in_days)) if expires_in_days else None

    # Check if entry already exists
    stmt = select(BlocklistEntry).where(
        BlocklistEntry.business_id == business_id,
        BlocklistEntry.identifier_type == "phone",
        BlocklistEntry.identifier_value == clean_number,
    )
    entry = (await session.execute(stmt)).scalar_one_or_none()

    if entry:
        entry.reason = reason
        entry.blocked_until = blocked_until
        entry.created_at = now
    else:
        entry = BlocklistEntry(
            id=uuid.uuid4(),
            business_id=business_id,
            identifier_type="phone",
            identifier_value=clean_number,
            reason=reason,
            created_at=now,
            blocked_until=blocked_until,
        )
        session.add(entry)

    await session.commit()
    return entry


async def remove_from_blocklist(
    session: AsyncSession,
    business_id: uuid.UUID,
    caller_number: str,
) -> bool:
    """Remove a telephone number from the tenant's blocklist."""
    clean_number = caller_number.strip()
    stmt = delete(BlocklistEntry).where(
        BlocklistEntry.business_id == business_id,
        BlocklistEntry.identifier_type == "phone",
        BlocklistEntry.identifier_value == clean_number,
    )
    result = await session.execute(stmt)
    await session.commit()
    return (result.rowcount or 0) > 0


async def list_blocklist_entries(
    session: AsyncSession,
    business_id: uuid.UUID,
) -> List[BlocklistEntry]:
    """List all active blocklist entries for the business tenant."""
    stmt = (
        select(BlocklistEntry)
        .where(BlocklistEntry.business_id == business_id)
        .order_by(BlocklistEntry.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())
