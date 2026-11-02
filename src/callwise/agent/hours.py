"""Timezone-aware business hours evaluation, closed day detection, and status reporting."""

from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
import zoneinfo
from pydantic import BaseModel, Field

from callwise.db.models import Business

DAYS_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class BusinessHoursStatus(BaseModel):
    """Structured status of business operating hours at a specific moment in time."""

    is_open: bool
    business_timezone: str
    current_time_local: str
    day_of_week: str
    today_schedule: str
    next_open_time: Optional[str] = None
    spoken_summary: str
    weekly_schedule_summary: str


def parse_time_str(val: Optional[str]) -> Optional[time]:
    """Parse time string in HH:MM or HH:MM:SS format (handles '24:00' as midnight)."""
    if not val:
        return None
    val = val.strip()
    if val in ("24:00", "24:00:00"):
        return time(23, 59, 59)

    parts = val.split(":")
    if len(parts) >= 2:
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) > 2 else 0
        return time(hour, minute, second)
    return None


def format_time_12h(t: time) -> str:
    """Format time object to human-friendly 12-hour string (e.g., '8:00 AM')."""
    if t.hour == 23 and t.minute == 59 and t.second == 59:
        return "midnight"
    if t.hour == 0 and t.minute == 0:
        return "midnight"
    if t.hour == 12 and t.minute == 0:
        return "noon"

    period = "AM" if t.hour < 12 else "PM"
    hour12 = t.hour % 12
    if hour12 == 0:
        hour12 = 12

    if t.minute == 0:
        return f"{hour12} {period}"
    return f"{hour12}:{t.minute:02d} {period}"


def get_business_local_now(tz_name: str, at_time: Optional[datetime] = None) -> datetime:
    """Resolve the current or requested moment in the business's local IANA timezone."""
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = zoneinfo.ZoneInfo("UTC")

    if at_time is None:
        return datetime.now(timezone.utc).astimezone(tz)
    else:
        # If naive, assume UTC; otherwise convert to business timezone
        if at_time.tzinfo is None:
            return at_time.replace(tzinfo=timezone.utc).astimezone(tz)
        return at_time.astimezone(tz)


def is_open_now(
    hours_config: Dict[str, Any],
    tz_name: str,
    at_time: Optional[datetime] = None,
) -> bool:
    """
    Check if the business is currently open, accounting for timezones, closed days,
    midnight crossings, and overnight shifts from the previous day.
    """
    local_dt = get_business_local_now(tz_name, at_time)
    weekday_idx = local_dt.weekday()  # Monday is 0, Sunday is 6
    today_name = DAYS_ORDER[weekday_idx]
    current_t = local_dt.time()

    today_cfg = hours_config.get(today_name, {})
    is_closed_today = today_cfg.get("closed", False)
    today_open = parse_time_str(today_cfg.get("open"))
    today_close = parse_time_str(today_cfg.get("close"))

    # 1. Check if open during today's shift
    if not is_closed_today and today_open and today_close:
        if today_open < today_close:
            # Standard daytime shift (e.g. 09:00 - 17:00)
            if today_open <= current_t < today_close:
                return True
        else:
            # Overnight shift starting today and crossing midnight (e.g. 21:00 - 02:00)
            if current_t >= today_open or current_t < today_close:
                return True

    # 2. Check if open due to an overnight shift that started yesterday
    yesterday_idx = (weekday_idx - 1) % 7
    yesterday_name = DAYS_ORDER[yesterday_idx]
    yesterday_cfg = hours_config.get(yesterday_name, {})

    if not yesterday_cfg.get("closed", False):
        y_open = parse_time_str(yesterday_cfg.get("open"))
        y_close = parse_time_str(yesterday_cfg.get("close"))
        if y_open and y_close and y_open >= y_close:
            # Yesterday was an overnight shift that spills into today before y_close
            if current_t < y_close:
                return True

    return False


def get_next_open_time(
    hours_config: Dict[str, Any],
    local_dt: datetime,
) -> Optional[Tuple[str, str]]:
    """
    Find the next opening day and time within the next 7 days.

    Returns:
        (day_relative_or_name, formatted_time) e.g. ("tomorrow", "8:00 AM")
    """
    current_weekday_idx = local_dt.weekday()
    current_t = local_dt.time()

    for days_ahead in range(1, 8):
        target_idx = (current_weekday_idx + days_ahead) % 7
        day_name = DAYS_ORDER[target_idx]
        cfg = hours_config.get(day_name, {})

        if not cfg.get("closed", False):
            open_t = parse_time_str(cfg.get("open"))
            if open_t:
                day_label = "tomorrow" if days_ahead == 1 else day_name.capitalize()
                return day_label, format_time_12h(open_t)

    return None


def generate_weekly_summary(hours_config: Dict[str, Any]) -> str:
    """Generate a clean, spoken summary of the weekly operating schedule."""
    lines: List[str] = []
    for day in DAYS_ORDER:
        cfg = hours_config.get(day, {})
        day_cap = day.capitalize()
        if cfg.get("closed", False) or not cfg.get("open"):
            lines.append(f"{day_cap}: Closed")
        else:
            open_t = parse_time_str(cfg.get("open"))
            close_t = parse_time_str(cfg.get("close"))
            if open_t and close_t:
                lines.append(f"{day_cap}: {format_time_12h(open_t)} to {format_time_12h(close_t)}")
            else:
                lines.append(f"{day_cap}: Closed")
    return ", ".join(lines)


def get_business_hours_status(
    business_or_config: Union[Business, Tuple[Dict[str, Any], str]],
    at_time: Optional[datetime] = None,
) -> BusinessHoursStatus:
    """
    Comprehensive evaluation of current status, schedules, and natural spoken summary.
    """
    if isinstance(business_or_config, Business):
        hours_config = business_or_config.hours or {}
        tz_name = business_or_config.timezone or "UTC"
    else:
        hours_config, tz_name = business_or_config

    local_dt = get_business_local_now(tz_name, at_time)
    weekday_idx = local_dt.weekday()
    today_name = DAYS_ORDER[weekday_idx]
    today_cfg = hours_config.get(today_name, {})

    open_status = is_open_now(hours_config, tz_name, at_time)

    # Format today's schedule
    if today_cfg.get("closed", False) or not today_cfg.get("open"):
        today_sched = "Closed"
    else:
        t_open = parse_time_str(today_cfg.get("open"))
        t_close = parse_time_str(today_cfg.get("close"))
        if t_open and t_close:
            today_sched = f"{format_time_12h(t_open)} to {format_time_12h(t_close)}"
        else:
            today_sched = "Closed"

    # Spoken summary generation
    if open_status:
        t_close = parse_time_str(today_cfg.get("close"))
        close_str = format_time_12h(t_close) if t_close else "the evening"
        spoken = f"We are currently open today until {close_str}."
        next_open = None
    else:
        next_info = get_next_open_time(hours_config, local_dt)
        if next_info:
            next_open = f"{next_info[0]} at {next_info[1]}"
            spoken = f"We are currently closed. We reopen {next_open}."
        else:
            next_open = None
            spoken = "We are currently closed."

    weekly_summary = generate_weekly_summary(hours_config)

    return BusinessHoursStatus(
        is_open=open_status,
        business_timezone=tz_name,
        current_time_local=local_dt.strftime("%A, %I:%M %p %Z"),
        day_of_week=today_name.capitalize(),
        today_schedule=today_sched,
        next_open_time=next_open,
        spoken_summary=spoken,
        weekly_schedule_summary=weekly_summary,
    )
