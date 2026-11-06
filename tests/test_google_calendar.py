"""Tests for GoogleCalendarProvider implementation, REST synchronization, and fallback resilience."""

from datetime import datetime, timezone
import json
import uuid
import httpx
import pytest

from callwise.db.models import Appointment, Business
from callwise.db.session import AsyncSessionLocal
from callwise.providers.calendar import (
    GoogleCalendarProvider,
    LocalCalendarProvider,
    TimeSlot,
    get_calendar_provider,
)


def test_google_calendar_factory_resolution():
    """Verify get_calendar_provider resolves GoogleCalendarProvider."""
    provider = get_calendar_provider("google")
    assert isinstance(provider, GoogleCalendarProvider)

    local_p = get_calendar_provider("local")
    assert isinstance(local_p, LocalCalendarProvider)

    with pytest.raises(ValueError, match="Unsupported calendar provider"):
        get_calendar_provider("unsupported_cloud")


def test_google_calendar_no_credentials_fallback():
    """Verify graceful simulation / fallback when credentials are not configured."""
    biz_id = uuid.uuid4()
    provider = GoogleCalendarProvider(credentials_file=None, access_token=None)

    # get_busy_times returns local busy slots
    start = datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 11, 10, 18, 0, tzinfo=timezone.utc)
    busy = provider.get_busy_times(biz_id, start, end)
    assert isinstance(busy, list)

    # create_event returns simulated gcal ID
    event_id = provider.create_event(biz_id, "Checkup", start, end, "Description")
    assert event_id.startswith("gcal_sim_")

    # update and delete succeed in simulation mode
    assert provider.update_event(biz_id, event_id, start, end) is True
    assert provider.delete_event(biz_id, event_id) is True


def test_google_calendar_mocked_api_get_busy_times():
    """Verify get_busy_times parses Google Calendar v3 events response."""
    biz_id = uuid.uuid4()

    mock_events = {
        "items": [
            {
                "id": "event_1",
                "summary": "Existing Cleaning",
                "start": {"dateTime": "2026-11-10T09:00:00Z"},
                "end": {"dateTime": "2026-11-10T10:00:00Z"},
            },
            {
                "id": "event_2",
                "summary": "Root Canal",
                "start": {"dateTime": "2026-11-10T13:00:00-05:00"},
                "end": {"dateTime": "2026-11-10T14:30:00-05:00"},
            },
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert "timeMin" in str(request.url)
        assert "timeMax" in str(request.url)
        return httpx.Response(200, json=mock_events)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)

    provider = GoogleCalendarProvider(
        access_token="fake_test_token",
        calendar_id="clinic@callwise.ai",
        http_client=client,
    )

    start = datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 11, 10, 20, 0, tzinfo=timezone.utc)

    busy = provider.get_busy_times(biz_id, start, end)
    assert len(busy) == 2

    # Check slot 1 in UTC
    assert busy[0].start_at == datetime(2026, 11, 10, 9, 0, tzinfo=timezone.utc)
    assert busy[0].end_at == datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc)

    # Check slot 2 converted to UTC (13:00 -05:00 is 18:00 UTC)
    assert busy[1].start_at == datetime(2026, 11, 10, 18, 0, tzinfo=timezone.utc)
    assert busy[1].end_at == datetime(2026, 11, 10, 19, 30, tzinfo=timezone.utc)


def test_google_calendar_mocked_api_create_update_delete():
    """Verify create_event, update_event, and delete_event via Google Calendar API."""
    biz_id = uuid.uuid4()
    captured_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        if request.method == "POST":
            return httpx.Response(201, json={"id": "gcal_evt_12345"})
        elif request.method == "PATCH":
            return httpx.Response(200, json={"id": "gcal_evt_12345", "status": "confirmed"})
        elif request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)

    provider = GoogleCalendarProvider(
        access_token="fake_token_xyz",
        calendar_id="primary",
        http_client=client,
    )

    start = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 11, 12, 11, 0, tzinfo=timezone.utc)

    # 1. Create event
    event_id = provider.create_event(
        business_id=biz_id,
        title="Dental Cleaning - John Doe",
        start_time=start,
        end_time=end,
        description="Patient: John Doe",
    )
    assert event_id == "gcal_evt_12345"
    assert captured_requests[-1].method == "POST"
    body = json.loads(captured_requests[-1].content)
    assert body["summary"] == "Dental Cleaning - John Doe"
    assert "2026-11-12T10:00:00" in body["start"]["dateTime"]

    # 2. Update event
    new_start = datetime(2026, 11, 12, 14, 0, tzinfo=timezone.utc)
    new_end = datetime(2026, 11, 12, 15, 0, tzinfo=timezone.utc)
    updated = provider.update_event(
        business_id=biz_id,
        event_id=event_id,
        start_time=new_start,
        end_time=new_end,
        title="Rescheduled Cleaning",
    )
    assert updated is True
    assert captured_requests[-1].method == "PATCH"
    patch_body = json.loads(captured_requests[-1].content)
    assert patch_body["summary"] == "Rescheduled Cleaning"
    assert "2026-11-12T14:00:00" in patch_body["start"]["dateTime"]

    # 3. Delete event
    deleted = provider.delete_event(biz_id, event_id)
    assert deleted is True
    assert captured_requests[-1].method == "DELETE"
    assert "gcal_evt_12345" in str(captured_requests[-1].url)


def test_google_calendar_api_error_resilience():
    """Verify provider handles HTTP errors (e.g. 500, network issues) without crashing."""
    biz_id = uuid.uuid4()

    def error_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Google Server Error")

    transport = httpx.MockTransport(error_handler)
    client = httpx.Client(transport=transport)

    provider = GoogleCalendarProvider(
        access_token="fake_token",
        http_client=client,
    )

    start = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 11, 12, 11, 0, tzinfo=timezone.utc)

    # get_busy_times should not raise, returns local busy slots
    busy = provider.get_busy_times(biz_id, start, end)
    assert isinstance(busy, list)

    # create_event falls back to internal fallback id
    evt_id = provider.create_event(biz_id, "Test", start, end)
    assert evt_id.startswith("gcal_fallback_")

    # update and delete return False on 500 error
    assert provider.update_event(biz_id, evt_id, start, end) is False
    assert provider.delete_event(biz_id, evt_id) is False

