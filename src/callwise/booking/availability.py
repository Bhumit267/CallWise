"""Availability calculation engine for appointments across operational hours and timezones."""

from datetime import date, datetime, timedelta, timezone
import logging
from typing import List, Optional
import uuid
from zoneinfo import ZoneInfo

from callwise.config import settings
from callwise.db.models import Business, Service
from callwise.providers.calendar import CalendarProvider, TimeSlot, get_calendar_provider

logger = logging.getLogger(__name__)


def get_available_slots(
    business: Business,
    service: Service,
    target_date: date,
    calendar_provider: Optional[CalendarProvider] = None,
    min_notice_hours: Optional[int] = None,
    reference_now: Optional[datetime] = None,
    slot_step_minutes: int = 30,
) -> List[TimeSlot]:
    """
    Calculate available booking slots for a given service on a specified date.

    Args:
        business: Business entity containing weekly hours schedule and timezone.
        service: Service entity containing appointment duration.
        target_date: Target calendar date to check (interpreted in business local timezone).
        calendar_provider: Provider to fetch busy times (defaults to configured provider).
        min_notice_hours: Minimum hours of advance notice required (defaults to settings).
        reference_now: Reference current datetime in UTC (defaults to current time).
        slot_step_minutes: Step interval in minutes between candidate slots (default 30).

    Returns:
        List of available TimeSlot objects with start_at and end_at in UTC.
    """
    if not service.is_active:
        return []

    notice_hours = min_notice_hours if min_notice_hours is not None else settings.min_booking_notice_hours
    now_utc = reference_now if reference_now is not None else datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    earliest_allowed_utc = now_utc + timedelta(hours=notice_hours)

    try:
        biz_tz = ZoneInfo(business.timezone)
    except Exception as exc:
        logger.warning(f"Invalid timezone '{business.timezone}', falling back to UTC: {exc}")
        biz_tz = ZoneInfo("UTC")

    # Determine weekday configuration
    weekday_key = target_date.strftime("%A").lower()
    day_cfg = (business.hours or {}).get(weekday_key)

    if not day_cfg or day_cfg.get("closed", False):
        return []

    open_str = day_cfg.get("open")
    close_str = day_cfg.get("close")
    if not open_str or not close_str:
        return []

    try:
        open_h, open_m = map(int, open_str.split(":"))
        close_h, close_m = map(int, close_str.split(":"))
    except ValueError:
        logger.error(f"Malformed open/close time for {business.name}: {open_str} - {close_str}")
        return []

    # Construct business day start and end in local timezone
    day_open_local = datetime(
        target_date.year, target_date.month, target_date.day, open_h, open_m, tzinfo=biz_tz
    )

    # Handle midnight or overnight closing
    if (close_h == 0 and close_m == 0) or close_str == "24:00":
        day_close_local = datetime(
            target_date.year, target_date.month, target_date.day, 0, 0, tzinfo=biz_tz
        ) + timedelta(days=1)
    elif (close_h, close_m) < (open_h, open_m):
        # Shifts crossing midnight into next calendar day
        day_close_local = datetime(
            target_date.year, target_date.month, target_date.day, close_h, close_m, tzinfo=biz_tz
        ) + timedelta(days=1)
    else:
        day_close_local = datetime(
            target_date.year, target_date.month, target_date.day, close_h, close_m, tzinfo=biz_tz
        )

    # Convert local business open/close to UTC (preserves DST adjustments accurately)
    day_open_utc = day_open_local.astimezone(timezone.utc)
    day_close_utc = day_close_local.astimezone(timezone.utc)

    # If the entire business day is in the past, return empty
    if day_close_utc <= earliest_allowed_utc:
        return []

    # Fetch busy times from calendar provider
    provider = calendar_provider or get_calendar_provider()
    busy_slots = provider.get_busy_times(business.id, day_open_utc, day_close_utc)

    service_duration = timedelta(minutes=service.duration_minutes)
    step = timedelta(minutes=max(5, slot_step_minutes))

    available_slots: List[TimeSlot] = []
    current_start = day_open_utc

    while current_start + service_duration <= day_close_utc:
        candidate = TimeSlot(
            start_at=current_start,
            end_at=current_start + service_duration,
        )

        # 1. Must satisfy minimum advance notice and not be in past
        if candidate.start_at >= earliest_allowed_utc:
            # 2. Must not overlap with any busy calendar block
            is_busy = any(candidate.overlaps(busy) for busy in busy_slots)
            if not is_busy:
                available_slots.append(candidate)

        current_start += step

    return available_slots


def format_spoken_availability(
    available_slots: List[TimeSlot],
    business: Business,
    service: Service,
    target_date: date,
    max_options: int = 3,
) -> str:
    """
    Format available slots into concise, natural spoken options for the caller.

    Returns e.g.:
    'We have openings for Routine Cleaning & Exam on Monday, November 9th at 9:00 AM, 11:30 AM, and 2:00 PM. Would any of those work for you?'
    """
    try:
        biz_tz = ZoneInfo(business.timezone)
    except Exception:
        biz_tz = ZoneInfo("UTC")

    date_formatted = target_date.strftime("%A, %B %d").replace(" 0", " ")

    if not available_slots:
        return f"I'm sorry, we do not have any open appointments for {service.name} on {date_formatted}."

    # Select representative options (e.g. up to max_options)
    # If many options, pick spread out morning / afternoon slots
    if len(available_slots) <= max_options:
        selected = available_slots
    else:
        # Pick first, middle, and last options to provide varied times
        step_idx = len(available_slots) // max_options
        selected = [available_slots[i * step_idx] for i in range(max_options)]

    times_str_list = []
    for slot in selected:
        local_time = slot.start_at.astimezone(biz_tz)
        # Format like '9:00 AM' (stripping leading zero)
        time_str = local_time.strftime("%I:%M %p").lstrip("0")
        times_str_list.append(time_str)

    if len(times_str_list) == 1:
        options_text = times_str_list[0]
    elif len(times_str_list) == 2:
        options_text = f"{times_str_list[0]} and {times_str_list[1]}"
    else:
        options_text = f"{', '.join(times_str_list[:-1])}, and {times_str_list[-1]}"

    return (
        f"We have openings for {service.name} on {date_formatted} at {options_text}. "
        "Would any of those times work for you?"
    )

