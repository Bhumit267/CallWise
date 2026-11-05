"""Calendar provider interfaces and local database-backed implementation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import List, Optional
import uuid

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
        # GoogleCalendarProvider will be implemented in Step 9
        try:
            from callwise.providers.google_calendar import GoogleCalendarProvider
            return GoogleCalendarProvider()
        except ImportError:
            logger.warning("GoogleCalendarProvider not yet available, falling back to LocalCalendarProvider")
            return LocalCalendarProvider()
    else:
        raise ValueError(f"Unsupported calendar provider: {chosen}")
