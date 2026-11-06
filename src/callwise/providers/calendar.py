"""Calendar provider interfaces and local database / Google Calendar implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

import httpx
from sqlalchemy import select

from callwise.config import settings
from callwise.db.models import Appointment
from callwise.db.session import get_sync_session

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TimeSlot:
    """Represents a time interval with UTC start and end datetimes."""
    start_at: datetime
    end_at: datetime

    def overlaps(self, other: "TimeSlot") -> bool:
        """Check if this time slot overlaps with another time slot."""
        return self.start_at < other.end_at and self.end_at > other.start_at


class CalendarProvider(ABC):
    """Abstract interface for checking busy times and synchronizing calendar events."""

    @abstractmethod
    def get_busy_times(
        self,
        business_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> List[TimeSlot]:
        """Retrieve existing busy time blocks in UTC within the specified window."""
        pass

    @abstractmethod
    def create_event(
        self,
        business_id: uuid.UUID,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: Optional[str] = None,
    ) -> str:
        """Create a calendar event. Returns external event identifier."""
        pass

    @abstractmethod
    def update_event(
        self,
        business_id: uuid.UUID,
        event_id: str,
        start_time: datetime,
        end_time: datetime,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> bool:
        """Update an existing calendar event."""
        pass

    @abstractmethod
    def delete_event(
        self,
        business_id: uuid.UUID,
        event_id: str,
    ) -> bool:
        """Cancel or delete an existing calendar event."""
        pass


class LocalCalendarProvider(CalendarProvider):
    """Database-backed local calendar provider querying booked Callwise appointments."""

    def get_busy_times(
        self,
        business_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> List[TimeSlot]:
        """Query appointments table for booked time intervals overlapping the window."""
        st_utc = start_time if start_time.tzinfo else start_time.replace(tzinfo=timezone.utc)
        et_utc = end_time if end_time.tzinfo else end_time.replace(tzinfo=timezone.utc)

        with get_sync_session() as session:
            stmt = select(Appointment).where(
                Appointment.business_id == business_id,
                Appointment.status == "booked",
                Appointment.start_at < et_utc,
                Appointment.end_at > st_utc,
            )
            appts = session.scalars(stmt).all()
            return [TimeSlot(start_at=a.start_at, end_at=a.end_at) for a in appts]

    def create_event(
        self,
        business_id: uuid.UUID,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: Optional[str] = None,
    ) -> str:
        """Generate an internal tracking ID for local database events."""
        event_id = f"local_{uuid.uuid4()}"
        logger.debug(f"Local calendar event created: {event_id} ({title})")
        return event_id

    def update_event(
        self,
        business_id: uuid.UUID,
        event_id: str,
        start_time: datetime,
        end_time: datetime,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> bool:
        """Update tracking for local calendar event."""
        logger.debug(f"Local calendar event updated: {event_id}")
        return True

    def delete_event(
        self,
        business_id: uuid.UUID,
        event_id: str,
    ) -> bool:
        """Delete tracking for local calendar event."""
        logger.debug(f"Local calendar event deleted: {event_id}")
        return True


class GoogleCalendarProvider(CalendarProvider):
    """
    Google Calendar API v3 provider for real-time busy slot synchronization and event management.
    Communicates via Google Calendar REST API with bearer token / service account or mocked HTTP client.
    """

    def __init__(
        self,
        credentials_file: Optional[str] = None,
        calendar_id: str = "primary",
        access_token: Optional[str] = None,
        http_client: Optional[httpx.Client] = None,
    ):
        self.credentials_file = credentials_file or settings.google_calendar_credentials_file
        self.calendar_id = calendar_id
        self.access_token = access_token
        self._client = http_client
        self._local_fallback = LocalCalendarProvider()

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=10.0)
        return self._client

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def get_busy_times(
        self,
        business_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> List[TimeSlot]:
        """Query Google Calendar for events in the window and merge with local booked appointments."""
        st_utc = start_time if start_time.tzinfo else start_time.replace(tzinfo=timezone.utc)
        et_utc = end_time if end_time.tzinfo else end_time.replace(tzinfo=timezone.utc)

        # 1. Local appointments busy times
        busy_slots = self._local_fallback.get_busy_times(business_id, st_utc, et_utc)

        # 2. If credentials or access token are missing, log info and return local busy slots
        if not self.access_token and not self.credentials_file:
            logger.info("Google Calendar credentials not configured, using local calendar busy slots.")
            return busy_slots

        # 3. Query Google Calendar v3 events
        url = f"https://www.googleapis.com/calendar/v3/calendars/{self.calendar_id}/events"
        params = {
            "timeMin": st_utc.isoformat(),
            "timeMax": et_utc.isoformat(),
            "singleEvents": "true",
            "orderBy": "startTime",
        }

        try:
            resp = self.client.get(url, params=params, headers=self._get_headers())
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("items", []):
                    start_raw = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date")
                    end_raw = item.get("end", {}).get("dateTime") or item.get("end", {}).get("date")
                    if start_raw and end_raw:
                        s_dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
                        e_dt = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
                        if s_dt.tzinfo is None:
                            s_dt = s_dt.replace(tzinfo=timezone.utc)
                        else:
                            s_dt = s_dt.astimezone(timezone.utc)
                        if e_dt.tzinfo is None:
                            e_dt = e_dt.replace(tzinfo=timezone.utc)
                        else:
                            e_dt = e_dt.astimezone(timezone.utc)
                        busy_slots.append(TimeSlot(start_at=s_dt, end_at=e_dt))
            else:
                logger.warning(f"Google Calendar API get_busy_times error {resp.status_code}: {resp.text}")
        except Exception as exc:
            logger.error(f"Failed to fetch Google Calendar busy times: {exc}")

        return busy_slots

    def create_event(
        self,
        business_id: uuid.UUID,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: Optional[str] = None,
    ) -> str:
        """Create an event on Google Calendar."""
        st_utc = start_time if start_time.tzinfo else start_time.replace(tzinfo=timezone.utc)
        et_utc = end_time if end_time.tzinfo else end_time.replace(tzinfo=timezone.utc)

        if not self.access_token and not self.credentials_file:
            return f"gcal_sim_{uuid.uuid4()}"

        url = f"https://www.googleapis.com/calendar/v3/calendars/{self.calendar_id}/events"
        payload = {
            "summary": title,
            "description": description or "",
            "start": {"dateTime": st_utc.isoformat()},
            "end": {"dateTime": et_utc.isoformat()},
        }

        try:
            resp = self.client.post(url, json=payload, headers=self._get_headers())
            if resp.status_code in (200, 201):
                data = resp.json()
                return data.get("id", f"gcal_{uuid.uuid4()}")
            logger.warning(f"Google Calendar API create_event error {resp.status_code}: {resp.text}")
        except Exception as exc:
            logger.error(f"Failed to create Google Calendar event: {exc}")

        return f"gcal_fallback_{uuid.uuid4()}"

    def update_event(
        self,
        business_id: uuid.UUID,
        event_id: str,
        start_time: datetime,
        end_time: datetime,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> bool:
        """Update an existing event on Google Calendar."""
        st_utc = start_time if start_time.tzinfo else start_time.replace(tzinfo=timezone.utc)
        et_utc = end_time if end_time.tzinfo else end_time.replace(tzinfo=timezone.utc)

        if not self.access_token and not self.credentials_file:
            return True

        url = f"https://www.googleapis.com/calendar/v3/calendars/{self.calendar_id}/events/{event_id}"
        payload: Dict[str, Any] = {
            "start": {"dateTime": st_utc.isoformat()},
            "end": {"dateTime": et_utc.isoformat()},
        }
        if title:
            payload["summary"] = title
        if description:
            payload["description"] = description

        try:
            resp = self.client.patch(url, json=payload, headers=self._get_headers())
            return resp.status_code == 200
        except Exception as exc:
            logger.error(f"Failed to update Google Calendar event {event_id}: {exc}")
            return False

    def delete_event(
        self,
        business_id: uuid.UUID,
        event_id: str,
    ) -> bool:
        """Delete an existing event on Google Calendar."""
        if not self.access_token and not self.credentials_file:
            return True

        url = f"https://www.googleapis.com/calendar/v3/calendars/{self.calendar_id}/events/{event_id}"
        try:
            resp = self.client.delete(url, headers=self._get_headers())
            return resp.status_code in (200, 204)
        except Exception as exc:
            logger.error(f"Failed to delete Google Calendar event {event_id}: {exc}")
            return False


_calendar_provider_instance: Optional[CalendarProvider] = None


def get_calendar_provider(provider_type: Optional[str] = None) -> CalendarProvider:
    """Factory retrieving the configured CalendarProvider."""
    global _calendar_provider_instance
    chosen = (provider_type or settings.calendar_provider).lower().strip()

    if chosen == "local":
        if _calendar_provider_instance is None or not isinstance(_calendar_provider_instance, LocalCalendarProvider):
            _calendar_provider_instance = LocalCalendarProvider()
        return _calendar_provider_instance
    elif chosen == "google":
        if _calendar_provider_instance is None or not isinstance(_calendar_provider_instance, GoogleCalendarProvider):
            _calendar_provider_instance = GoogleCalendarProvider()
        return _calendar_provider_instance
    else:
        raise ValueError(f"Unsupported calendar provider: {chosen}")
