"""Unit and integration tests for Step 2: CalendarProvider and Availability Calculation."""

from datetime import date, datetime, timedelta, timezone
import uuid
from zoneinfo import ZoneInfo
import pytest

from callwise.booking.availability import (
    format_spoken_availability,
    get_available_slots,
)
from callwise.db.models import Appointment, Business, Service
from callwise.db.session import get_sync_session
from callwise.providers.calendar import (
    CalendarProvider,
    LocalCalendarProvider,
    TimeSlot,
    get_calendar_provider,
)


class MockCalendarProvider(CalendarProvider):
    """Test mock for CalendarProvider returning predefined busy blocks."""

    def __init__(self, busy_slots=None):
        self._busy_slots = busy_slots or []

    def get_busy_times(self, business_id: uuid.UUID, start_time: datetime, end_time: datetime):
        return [
            slot for slot in self._busy_slots
            if slot.start_at < end_time and slot.end_at > start_time
        ]

    def create_event(self, business_id: uuid.UUID, title: str, start_time: datetime, end_time: datetime, description=None) -> str:
        return f"mock_event_{uuid.uuid4()}"

    def update_event(self, business_id: uuid.UUID, event_id: str, start_time: datetime, end_time: datetime, title=None, description=None) -> bool:
        return True

    def delete_event(self, business_id: uuid.UUID, event_id: str) -> bool:
        return True


@pytest.fixture
def dental_biz():
    """Dental clinic business in America/New_York (Mon-Thu 8-17, Fri 8-13, Sat-Sun Closed)."""
    return Business(
        id=uuid.uuid4(),
        name="BrightSmile Family Dental",
        business_type="Dental Clinic",
        timezone="America/New_York",
        hours={
            "monday": {"open": "08:00", "close": "17:00", "closed": False},
            "tuesday": {"open": "08:00", "close": "17:00", "closed": False},
            "wednesday": {"open": "08:00", "close": "17:00", "closed": False},
            "thursday": {"open": "08:00", "close": "17:00", "closed": False},
            "friday": {"open": "08:00", "close": "13:00", "closed": False},
            "saturday": {"open": None, "close": None, "closed": True},
            "sunday": {"open": None, "close": None, "closed": True},
        },
    )


@pytest.fixture
def dental_cleaning_service(dental_biz):
    """60-minute dental cleaning service."""
    return Service(
        id=uuid.uuid4(),
        business_id=dental_biz.id,
        name="Routine Cleaning & Exam",
        duration_minutes=60,
        price=120.0,
        is_active=True,
    )


def test_closed_days(dental_biz, dental_cleaning_service):
    """Verify closed days return zero slots and graceful spoken text."""
    # Sunday, November 8, 2026 (closed)
    sunday = date(2026, 11, 8)
    slots = get_available_slots(
        business=dental_biz,
        service=dental_cleaning_service,
        target_date=sunday,
        calendar_provider=MockCalendarProvider(),
    )
    assert len(slots) == 0

    spoken = format_spoken_availability(slots, dental_biz, dental_cleaning_service, sunday)
    assert "do not have any open appointments" in spoken
    assert "Routine Cleaning & Exam" in spoken
    assert "Sunday, November 8" in spoken


def test_basic_availability_and_slot_generation(dental_biz, dental_cleaning_service):
    """Verify slots generated on open days match local business hours converted to UTC."""
    # Monday, November 9, 2026: Open 08:00 to 17:00 EST (UTC-5)
    # In UTC: 13:00 to 22:00 UTC
    target_monday = date(2026, 11, 9)
    # Reference now is set well before the day
    ref_now = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)

    slots = get_available_slots(
        business=dental_biz,
        service=dental_cleaning_service,
        target_date=target_monday,
        calendar_provider=MockCalendarProvider(),
        reference_now=ref_now,
        min_notice_hours=2,
    )

    assert len(slots) > 0
    ny_tz = ZoneInfo("America/New_York")

    # First slot must be 8:00 AM local time
    first_local = slots[0].start_at.astimezone(ny_tz)
    assert first_local.hour == 8
    assert first_local.minute == 0

    # Last slot: 60-min service must finish by 17:00 (so latest start is 16:00 or 16:30 depending on step)
    last_local = slots[-1].start_at.astimezone(ny_tz)
    assert last_local.hour + (last_local.minute + 60) / 60.0 <= 17.0

    # Format spoken availability
    spoken = format_spoken_availability(slots, dental_biz, dental_cleaning_service, target_monday)
    assert "We have openings for Routine Cleaning & Exam" in spoken
    assert "8:00 AM" in spoken


def test_busy_times_exclusion(dental_biz, dental_cleaning_service):
    """Verify booked calendar slots are excluded from available slots."""
    target_monday = date(2026, 11, 9)
    ref_now = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)
    ny_tz = ZoneInfo("America/New_York")

    # Book 9:00 AM to 10:00 AM local time (14:00 to 15:00 UTC)
    busy_start_utc = datetime(2026, 11, 9, 9, 0, tzinfo=ny_tz).astimezone(timezone.utc)
    busy_end_utc = datetime(2026, 11, 9, 10, 0, tzinfo=ny_tz).astimezone(timezone.utc)

    provider = MockCalendarProvider([TimeSlot(busy_start_utc, busy_end_utc)])

    slots = get_available_slots(
        business=dental_biz,
        service=dental_cleaning_service,
        target_date=target_monday,
        calendar_provider=provider,
        reference_now=ref_now,
    )

    # Ensure no available slot overlaps with the 9:00 - 10:00 busy slot
    busy_slot = TimeSlot(busy_start_utc, busy_end_utc)
    for slot in slots:
        assert not slot.overlaps(busy_slot), f"Slot {slot} overlaps with busy period {busy_slot}"


def test_minimum_notice_and_past_exclusion(dental_biz, dental_cleaning_service):
    """Verify slots in the past or within min_notice_hours are excluded."""
    target_monday = date(2026, 11, 9)
    ny_tz = ZoneInfo("America/New_York")

    # Suppose current time is Monday at 10:00 AM local time (15:00 UTC) with 2-hour minimum notice
    # Earliest allowed start is 12:00 PM local (17:00 UTC)
    current_time_local = datetime(2026, 11, 9, 10, 0, tzinfo=ny_tz)
    ref_now_utc = current_time_local.astimezone(timezone.utc)

    slots = get_available_slots(
        business=dental_biz,
        service=dental_cleaning_service,
        target_date=target_monday,
        calendar_provider=MockCalendarProvider(),
        reference_now=ref_now_utc,
        min_notice_hours=2,
    )

    for slot in slots:
        local_start = slot.start_at.astimezone(ny_tz)
        assert local_start >= datetime(2026, 11, 9, 12, 0, tzinfo=ny_tz)


def test_midnight_and_late_closing():
    """Verify businesses closing at midnight (00:00) or early morning (02:00) calculate slots across midnight."""
    night_spa = Business(
        id=uuid.uuid4(),
        name="Night Owl Spa",
        business_type="Late Night Spa",
        timezone="America/New_York",
        hours={
            "friday": {"open": "18:00", "close": "02:00", "closed": False},
        },
    )
    spa_service = Service(
        id=uuid.uuid4(),
        business_id=night_spa.id,
        name="Night Massage",
        duration_minutes=60,
        price=150.0,
        is_active=True,
    )

    friday_date = date(2026, 11, 13)
    ref_now = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)

    slots = get_available_slots(
        business=night_spa,
        service=spa_service,
        target_date=friday_date,
        calendar_provider=MockCalendarProvider(),
        reference_now=ref_now,
    )

    ny_tz = ZoneInfo("America/New_York")
    assert len(slots) > 0

    # First slot starts at 18:00 Friday
    assert slots[0].start_at.astimezone(ny_tz).hour == 18

    # Last slot finishes by 02:00 Saturday morning (starts at 01:00 Saturday)
    last_local = slots[-1].start_at.astimezone(ny_tz)
    assert last_local.day == 14  # Saturday morning
    assert last_local.hour == 1


def test_dst_transitions(dental_biz, dental_cleaning_service):
    """Verify slots during Daylight Saving Time spring forward and fall back."""
    ny_tz = ZoneInfo("America/New_York")
    ref_now = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    # 1. Spring Forward: Sunday, March 8, 2026 (clock jumps from 02:00 to 03:00)
    # Check Monday, March 9, 2026 (first day of EDT, UTC-4)
    spring_monday = date(2026, 3, 9)
    spring_slots = get_available_slots(
        business=dental_biz,
        service=dental_cleaning_service,
        target_date=spring_monday,
        calendar_provider=MockCalendarProvider(),
        reference_now=ref_now,
    )
    assert len(spring_slots) > 0
    # 8:00 AM EDT should be 12:00 PM UTC (UTC-4)
    assert spring_slots[0].start_at.hour == 12
    assert spring_slots[0].start_at.astimezone(ny_tz).hour == 8

    # 2. Fall Back: Sunday, November 1, 2026 (clock falls back from 02:00 to 01:00)
    # Check Monday, November 2, 2026 (first day back in EST, UTC-5)
    fall_monday = date(2026, 11, 2)
    fall_slots = get_available_slots(
        business=dental_biz,
        service=dental_cleaning_service,
        target_date=fall_monday,
        calendar_provider=MockCalendarProvider(),
        reference_now=ref_now,
    )
    assert len(fall_slots) > 0
    # 8:00 AM EST should be 13:00 UTC (UTC-5)
    assert fall_slots[0].start_at.hour == 13
    assert fall_slots[0].start_at.astimezone(ny_tz).hour == 8


def test_local_calendar_provider_db_integration():
    """Verify LocalCalendarProvider reads existing appointments from database."""
    biz_id = uuid.uuid4()
    svc_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    with get_sync_session() as session:
        biz = Business(
            id=biz_id,
            name="Test Local Dental",
            business_type="Dental",
            greeting="Welcome to Test Local Dental.",
            timezone="UTC",
            hours={"monday": {"open": "09:00", "close": "17:00", "closed": False}},
        )
        session.add(biz)
        svc = Service(
            id=svc_id,
            business_id=biz_id,
            name="Cleaning",
            duration_minutes=60,
            price=100.0,
            is_active=True,
        )
        session.add(svc)

        # Add booked appointment
        appt = Appointment(
            business_id=biz_id,
            service_id=svc_id,
            customer_name="John Doe",
            customer_phone="555-1234",
            start_at=now + timedelta(hours=2),
            end_at=now + timedelta(hours=3),
            status="booked",
            booking_code_hash="hash_abc",
        )
        session.add(appt)
        session.commit()

    provider = LocalCalendarProvider()
    busy = provider.get_busy_times(biz_id, now, now + timedelta(hours=5))
    assert len(busy) == 1
    assert busy[0].start_at == appt.start_at
    assert busy[0].end_at == appt.end_at
