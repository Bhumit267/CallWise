"""Unit and edge-case tests for timezone-aware business hours logic."""

from datetime import datetime, timezone
import zoneinfo
import pytest
from typer.testing import CliRunner

from callwise.agent.hours import (
    BusinessHoursStatus,
    get_business_hours_status,
    is_open_now,
    parse_time_str,
)
from callwise.cli import app
from callwise.db.seed import DENTAL_CLINIC_ID, DEMO_BUSINESSES, SALON_SPA_ID, run_seed

DENTAL_HOURS = DEMO_BUSINESSES[0]["hours"]
DENTAL_TZ = DEMO_BUSINESSES[0]["timezone"]  # America/New_York

SALON_HOURS = DEMO_BUSINESSES[1]["hours"]
SALON_TZ = DEMO_BUSINESSES[1]["timezone"]  # America/Los_Angeles


def test_dental_clinic_open_and_closed_hours():
    """Verify dental clinic hours (Mon-Sat 10-20, Sun 10-14)."""
    ist_tz = zoneinfo.ZoneInfo("Asia/Kolkata")

    # Wednesday at 11:00 AM IST -> Open
    wed_open = datetime(2026, 11, 4, 11, 0, 0, tzinfo=ist_tz)
    assert is_open_now(DENTAL_HOURS, DENTAL_TZ, at_time=wed_open) is True

    # Wednesday at 9:30 AM IST -> Closed (opens at 10:00 AM)
    wed_early = datetime(2026, 11, 4, 9, 30, 0, tzinfo=ist_tz)
    assert is_open_now(DENTAL_HOURS, DENTAL_TZ, at_time=wed_early) is False

    # Wednesday at 8:01 PM IST -> Closed (closes at 8:00 PM)
    wed_late = datetime(2026, 11, 4, 20, 1, 0, tzinfo=ist_tz)
    assert is_open_now(DENTAL_HOURS, DENTAL_TZ, at_time=wed_late) is False

    # Sunday at 11:30 AM IST -> Open (closes at 2:00 PM)
    sun_open = datetime(2026, 11, 8, 11, 30, 0, tzinfo=ist_tz)
    assert is_open_now(DENTAL_HOURS, DENTAL_TZ, at_time=sun_open) is True

    # Sunday at 2:30 PM IST -> Closed (Sunday half day closes at 2:00 PM)
    sun_late = datetime(2026, 11, 8, 14, 30, 0, tzinfo=ist_tz)
    assert is_open_now(DENTAL_HOURS, DENTAL_TZ, at_time=sun_late) is False


def test_salon_spa_hours_and_monday_closed():
    """Verify salon hours (Tue-Sat 10-19, Sun 11-16, Mon closed)."""
    la_tz = zoneinfo.ZoneInfo("America/Los_Angeles")

    # Monday at 12:00 PM LA time -> Closed (Mondays closed)
    mon = datetime(2026, 11, 2, 12, 0, 0, tzinfo=la_tz)
    assert is_open_now(SALON_HOURS, SALON_TZ, at_time=mon) is False

    # Tuesday at 11:00 AM LA time -> Open
    tue = datetime(2026, 11, 3, 11, 0, 0, tzinfo=la_tz)
    assert is_open_now(SALON_HOURS, SALON_TZ, at_time=tue) is True

    # Sunday at 12:00 PM LA time -> Open (11:00 - 16:00)
    sun = datetime(2026, 11, 8, 12, 0, 0, tzinfo=la_tz)
    assert is_open_now(SALON_HOURS, SALON_TZ, at_time=sun) is True


def test_timezone_difference_simultaneous_moment():
    """
    At 14:00 UTC on Wednesday:
    - In New York (EDT/EST = UTC-5): 9:00 AM -> Dental Clinic is OPEN.
    - In Los Angeles (PDT/PST = UTC-8): 6:00 AM -> Salon is CLOSED.
    """
    utc_moment = datetime(2026, 11, 4, 14, 0, 0, tzinfo=timezone.utc)
    assert is_open_now(DENTAL_HOURS, DENTAL_TZ, at_time=utc_moment) is True
    assert is_open_now(SALON_HOURS, SALON_TZ, at_time=utc_moment) is False


def test_midnight_closing_shift():
    """Verify shift scheduled to close exactly at midnight (00:00 / 24:00)."""
    hours = {
        "friday": {"open": "17:00", "close": "00:00", "closed": False},
        "saturday": {"open": None, "close": None, "closed": True},
    }
    tz = "America/New_York"
    ny_tz = zoneinfo.ZoneInfo(tz)

    # Friday at 23:55 -> Open
    fri_late = datetime(2026, 11, 6, 23, 55, 0, tzinfo=ny_tz)
    assert is_open_now(hours, tz, at_time=fri_late) is True

    # Saturday at 00:01 -> Closed
    sat_early = datetime(2026, 11, 7, 0, 1, 0, tzinfo=ny_tz)
    assert is_open_now(hours, tz, at_time=sat_early) is False


def test_overnight_shift_spanning_midnight():
    """Verify overnight shift starting Friday at 20:00 and ending Saturday at 02:00."""
    hours = {
        "friday": {"open": "20:00", "close": "02:00", "closed": False},
        "saturday": {"open": None, "close": None, "closed": True},
    }
    tz = "America/Chicago"
    ch_tz = zoneinfo.ZoneInfo(tz)

    # Friday at 21:00 -> Open
    fri_night = datetime(2026, 11, 6, 21, 0, 0, tzinfo=ch_tz)
    assert is_open_now(hours, tz, at_time=fri_night) is True

    # Saturday at 01:30 AM -> Still Open from Friday's overnight shift
    sat_overnight = datetime(2026, 11, 7, 1, 30, 0, tzinfo=ch_tz)
    assert is_open_now(hours, tz, at_time=sat_overnight) is True

    # Saturday at 02:01 AM -> Closed
    sat_after = datetime(2026, 11, 7, 2, 1, 0, tzinfo=ch_tz)
    assert is_open_now(hours, tz, at_time=sat_after) is False


def test_daylight_saving_time_transitions():
    """
    Test Spring Forward (March) and Fall Back (November) transitions.
    In US EDT/EST:
    - 2026 Spring forward: Sunday, March 8, 2026.
    - 2026 Fall back: Sunday, November 1, 2026.
    """
    ny_tz = zoneinfo.ZoneInfo("America/New_York")

    # Spring Forward Monday: March 9, 2026 at 9:00 AM EDT (UTC-4) -> Open
    spring_mon = datetime(2026, 3, 9, 9, 0, 0, tzinfo=ny_tz)
    assert is_open_now(DENTAL_HOURS, DENTAL_TZ, at_time=spring_mon) is True

    # Fall Back Monday: November 2, 2026 at 9:00 AM EST (UTC-5) -> Open
    fall_mon = datetime(2026, 11, 2, 9, 0, 0, tzinfo=ny_tz)
    assert is_open_now(DENTAL_HOURS, DENTAL_TZ, at_time=fall_mon) is True


def test_status_and_next_opening_calculation():
    """Verify natural spoken status and next opening time calculation."""
    ist_tz = zoneinfo.ZoneInfo("Asia/Kolkata")

    # Sunday afternoon after dental clinic closed at 2:00 PM -> Should report reopening tomorrow (Monday) at 10 AM
    sun_afternoon = datetime(2026, 11, 8, 15, 0, 0, tzinfo=ist_tz)
    status = get_business_hours_status((DENTAL_HOURS, DENTAL_TZ), at_time=sun_afternoon)
    assert status.is_open is False
    assert status.next_open_time is not None
    assert "tomorrow at 10 AM" in status.next_open_time or "Monday at 10 AM" in status.next_open_time
    assert "currently closed" in status.spoken_summary.lower()


def test_cli_check_hours():
    """Verify CLI check-hours command returns structured output."""
    run_seed()
    runner = CliRunner()

    res = runner.invoke(
        app,
        [
            "check-hours",
            "--business-id",
            str(DENTAL_CLINIC_ID),
            "--at",
            "2026-11-04T14:00:00Z",  # Wed 9:00 AM NY time -> Open
        ],
    )
    assert res.exit_code == 0
    assert "Aarav Health & Dental Clinic" in res.output
    assert "[OPEN NOW]" in res.output
