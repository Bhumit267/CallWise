"""Pydantic schemas and response models for Callwise core read and list APIs."""

from datetime import datetime
import math
from typing import Any, Dict, Generic, List, Optional, TypeVar
import uuid

from pydantic import BaseModel, ConfigDict, Field


def mask_phone_number(phone: Optional[str]) -> Optional[str]:
    """Mask caller or contact phone number for list endpoints (e.g. '***-***-1234')."""
    if not phone or phone.lower() in ("unknown", "anonymous"):
        return phone
    clean = phone.strip()
    digits = [c for c in clean if c.isdigit()]
    if len(digits) < 4:
        return "****"
    last4 = "".join(digits[-4:])
    return f"***-***-{last4}"


def parse_query_datetime(val: Optional[str]) -> Optional[datetime]:
    """Parse query parameter datetime supporting ISO-8601, UTC 'Z', and space-decoded '+' offsets."""
    if not val:
        return None
    cleaned = val.strip().replace(" ", "+")
    if cleaned.endswith("Z") or cleaned.endswith("z"):
        cleaned = cleaned[:-1] + "+00:00"
    return datetime.fromisoformat(cleaned)


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard pagination envelope."""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    @classmethod
    def create(cls, items: List[T], total: int, page: int, page_size: int) -> "PaginatedResponse[T]":
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )


# ============================================================================
# Calls
# ============================================================================

class CallListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    caller_number: Optional[str] = None  # MASKED
    contact_id: Optional[uuid.UUID] = None
    contact_name: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: float
    summary: Optional[str] = None
    turn_count: int = 0
    has_appointment: bool = False
    has_message: bool = False
    has_transfer: bool = False


class CallTurnItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    speaker: str
    text: str
    latency_ms: Optional[float] = None
    timestamp: datetime


class CallDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    caller_number: Optional[str] = None  # UNMASKED
    contact_id: Optional[uuid.UUID] = None
    contact_name: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: float
    summary: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    tts_provider: Optional[str] = None
    stt_provider: Optional[str] = None
    turns: List[CallTurnItem] = Field(default_factory=list)
    appointments: List[Dict[str, Any]] = Field(default_factory=list)
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    transfers: List[Dict[str, Any]] = Field(default_factory=list)
    knowledge_misses: List[Dict[str, Any]] = Field(default_factory=list)


# ============================================================================
# Messages
# ============================================================================

class MessageListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    call_id: Optional[uuid.UUID] = None
    contact_id: Optional[uuid.UUID] = None
    contact_name: Optional[str] = None
    caller_name: str
    callback_number: str  # MASKED
    reason: str
    created_at: datetime


class MessageDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    call_id: Optional[uuid.UUID] = None
    contact_id: Optional[uuid.UUID] = None
    contact_name: Optional[str] = None
    caller_name: str
    callback_number: str  # UNMASKED
    reason: str
    created_at: datetime
    call_summary: Optional[str] = None


# ============================================================================
# Appointments
# ============================================================================

class AppointmentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    service_id: uuid.UUID
    service_name: str
    customer_name: str
    customer_phone: str  # MASKED
    customer_email: Optional[str] = None
    start_at: datetime
    end_at: datetime
    status: str
    contact_id: Optional[uuid.UUID] = None
    call_id: Optional[uuid.UUID] = None
    created_at: datetime


class AppointmentCalendarItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    service_id: uuid.UUID
    service_name: str
    customer_name: str
    customer_phone: str  # MASKED
    start_at: datetime
    end_at: datetime
    status: str


class AppointmentDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    service_id: uuid.UUID
    service_name: str
    service_price: float
    service_duration_minutes: int
    customer_name: str
    customer_phone: str  # UNMASKED
    customer_email: Optional[str] = None
    start_at: datetime
    end_at: datetime
    status: str
    external_event_id: Optional[str] = None
    contact_id: Optional[uuid.UUID] = None
    call_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    verification_attempts: List[Dict[str, Any]] = Field(default_factory=list)
    reminders: List[Dict[str, Any]] = Field(default_factory=list)


# ============================================================================
# Contacts
# ============================================================================

class ContactListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: Optional[str] = None
    phone: Optional[str] = None  # MASKED
    email: Optional[str] = None
    notes: Optional[str] = None
    do_not_contact: bool = False
    created_at: datetime
    calls_count: int = 0
    appointments_count: int = 0


class ContactDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: Optional[str] = None
    phone: Optional[str] = None  # UNMASKED
    email: Optional[str] = None
    notes: Optional[str] = None
    do_not_contact: bool = False
    created_at: datetime
    updated_at: datetime
    calls: List[CallListItem] = Field(default_factory=list)
    appointments: List[AppointmentListItem] = Field(default_factory=list)
    messages: List[MessageListItem] = Field(default_factory=list)
    follow_ups: List[Dict[str, Any]] = Field(default_factory=list)


# ============================================================================
# Follow-ups
# ============================================================================

class FollowUpListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contact_id: Optional[uuid.UUID] = None
    contact_name: Optional[str] = None
    assigned_to_user_id: Optional[uuid.UUID] = None
    assigned_to_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    source: str
    source_id: Optional[str] = None
    status: str
    snoozed_until: Optional[datetime] = None
    due_at: Optional[datetime] = None
    created_at: datetime


class FollowUpDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contact_id: Optional[uuid.UUID] = None
    contact_name: Optional[str] = None
    assigned_to_user_id: Optional[uuid.UUID] = None
    assigned_to_name: Optional[str] = None
    assigned_to_email: Optional[str] = None
    title: str
    description: Optional[str] = None
    source: str
    source_id: Optional[str] = None
    status: str
    snoozed_until: Optional[datetime] = None
    due_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Knowledge Misses
# ============================================================================

class KnowledgeMissListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    call_id: Optional[uuid.UUID] = None
    query: str
    status: str
    resolved_at: Optional[datetime] = None
    resolved_answer: Optional[str] = None
    created_at: datetime


class KnowledgeMissGroupItem(BaseModel):
    query: str
    count: int
    status: str
    last_asked_at: datetime
    sample_miss_id: uuid.UUID


# ============================================================================
# Unified Inbox
# ============================================================================

class InboxItem(BaseModel):
    id: str
    item_type: str  # call, message, transfer, appointment
    timestamp: datetime
    title: str
    description: Optional[str] = None
    contact_id: Optional[uuid.UUID] = None
    contact_name: Optional[str] = None
    phone: Optional[str] = None  # MASKED
    meta: Dict[str, Any] = Field(default_factory=dict)
