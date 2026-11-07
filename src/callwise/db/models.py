"""SQLAlchemy models for Callwise multi-tenant voice receptionist."""

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from callwise.config import settings
from callwise.db.session import Base


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class Business(Base):
    """Tenant entity holding configuration, persona, tone, and operational hours."""

    __tablename__ = "businesses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_type: Mapped[str] = mapped_column(String(100), nullable=False)
    greeting: Mapped[str] = mapped_column(Text, nullable=False)
    tone: Mapped[str] = mapped_column(String(100), nullable=False, default="professional")
    timezone: Mapped[str] = mapped_column(String(100), nullable=False, default="UTC")
    # Structured schedule: e.g. {"monday": {"open": "09:00", "close": "17:00", "closed": False}, ...}
    hours: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    transfer_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notification_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    retention_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=90)
    website_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    # Relationships
    documents: Mapped[List["Document"]] = relationship(
        "Document", back_populates="business", cascade="all, delete-orphan"
    )
    chunks: Mapped[List["Chunk"]] = relationship(
        "Chunk", back_populates="business", cascade="all, delete-orphan"
    )
    calls: Mapped[List["Call"]] = relationship(
        "Call", back_populates="business", cascade="all, delete-orphan"
    )
    messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="business", cascade="all, delete-orphan"
    )
    knowledge_misses: Mapped[List["KnowledgeMiss"]] = relationship(
        "KnowledgeMiss", back_populates="business", cascade="all, delete-orphan"
    )
    services: Mapped[List["Service"]] = relationship(
        "Service", back_populates="business", cascade="all, delete-orphan"
    )
    appointments: Mapped[List["Appointment"]] = relationship(
        "Appointment", back_populates="business", cascade="all, delete-orphan"
    )
    verification_attempts: Mapped[List["VerificationAttempt"]] = relationship(
        "VerificationAttempt", back_populates="business", cascade="all, delete-orphan"
    )
    transfers: Mapped[List["Transfer"]] = relationship(
        "Transfer", back_populates="business", cascade="all, delete-orphan"
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification", back_populates="business", cascade="all, delete-orphan"
    )
    reminders: Mapped[List["Reminder"]] = relationship(
        "Reminder", back_populates="business", cascade="all, delete-orphan"
    )
    memberships: Mapped[List["Membership"]] = relationship(
        "Membership", back_populates="business", cascade="all, delete-orphan"
    )
    invites: Mapped[List["Invite"]] = relationship(
        "Invite", back_populates="business", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog", back_populates="business", cascade="all, delete-orphan"
    )
    jobs: Mapped[List["Job"]] = relationship(
        "Job", back_populates="business", cascade="all, delete-orphan"
    )
    contacts: Mapped[List["Contact"]] = relationship(
        "Contact", back_populates="business", cascade="all, delete-orphan"
    )
    follow_ups: Mapped[List["FollowUp"]] = relationship(
        "FollowUp", back_populates="business", cascade="all, delete-orphan"
    )
    phone_numbers: Mapped[List["PhoneNumber"]] = relationship(
        "PhoneNumber", back_populates="business", cascade="all, delete-orphan"
    )
    usage_records: Mapped[List["UsageRecord"]] = relationship(
        "UsageRecord", back_populates="business", cascade="all, delete-orphan"
    )
    usage_limits: Mapped[Optional["UsageLimits"]] = relationship(
        "UsageLimits", back_populates="business", uselist=False, cascade="all, delete-orphan"
    )
    widget_settings: Mapped[Optional["WidgetSettings"]] = relationship(
        "WidgetSettings", back_populates="business", uselist=False, cascade="all, delete-orphan"
    )
    blocklist_entries: Mapped[List["BlocklistEntry"]] = relationship(
        "BlocklistEntry", back_populates="business", cascade="all, delete-orphan"
    )


class Document(Base):
    """Source file or crawled web page ingested for a business."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "file" or "url"
    source_uri: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    business: Mapped["Business"] = relationship("Business", back_populates="documents")
    chunks: Mapped[List["Chunk"]] = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan"
    )


class Chunk(Base):
    """Text chunk extracted from a document with high-dimensional embedding."""

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(settings.embedding_dimension), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    business: Mapped["Business"] = relationship("Business", back_populates="chunks")
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")


class Call(Base):
    """A phone / WebRTC call session for a business."""

    __tablename__ = "calls"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    caller_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="unknown")
    contact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    llm_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tts_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    stt_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    business: Mapped["Business"] = relationship("Business", back_populates="calls")
    contact: Mapped[Optional["Contact"]] = relationship("Contact", back_populates="calls")
    turns: Mapped[List["CallTurn"]] = relationship(
        "CallTurn", back_populates="call", cascade="all, delete-orphan", order_by="CallTurn.timestamp"
    )
    messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="call"
    )
    appointments: Mapped[List["Appointment"]] = relationship(
        "Appointment", back_populates="call"
    )
    verification_attempts: Mapped[List["VerificationAttempt"]] = relationship(
        "VerificationAttempt", back_populates="call"
    )
    transfers: Mapped[List["Transfer"]] = relationship(
        "Transfer", back_populates="call"
    )
    knowledge_misses: Mapped[List["KnowledgeMiss"]] = relationship(
        "KnowledgeMiss", back_populates="call"
    )


class CallTurn(Base):
    """Individual conversational dialogue turn (caller or agent)."""

    __tablename__ = "call_turns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    speaker: Mapped[str] = mapped_column(String(20), nullable=False)  # "caller" or "agent"
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Turn response latency: time elapsed from caller finishing speech to agent audio starting
    latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    call: Mapped["Call"] = relationship("Call", back_populates="turns")


class Message(Base):
    """Callback message recorded when agent cannot answer or caller requests it."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    call_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calls.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    caller_name: Mapped[str] = mapped_column(String(255), nullable=False)
    callback_number: Mapped[str] = mapped_column(String(50), nullable=False)
    contact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    business: Mapped["Business"] = relationship("Business", back_populates="messages")
    call: Mapped[Optional["Call"]] = relationship("Call", back_populates="messages")
    contact: Mapped[Optional["Contact"]] = relationship("Contact", back_populates="messages")


class KnowledgeMiss(Base):
    """Records unanswered queries where knowledge similarity cutoff was not met."""

    __tablename__ = "knowledge_misses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    call_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calls.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="unresolved", index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    business: Mapped["Business"] = relationship("Business", back_populates="knowledge_misses")
    call: Mapped[Optional["Call"]] = relationship("Call", back_populates="knowledge_misses")


class Service(Base):
    """Offered business appointment service with duration and price."""

    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    business: Mapped["Business"] = relationship("Business", back_populates="services")
    appointments: Mapped[List["Appointment"]] = relationship(
        "Appointment", back_populates="service", cascade="all, delete-orphan"
    )


class Appointment(Base):
    """Booked customer appointment with verified details and start/end times in UTC."""

    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(100), nullable=False)
    customer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="booked")  # booked, cancelled, completed, no_show
    booking_code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    external_event_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    call_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calls.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    business: Mapped["Business"] = relationship("Business", back_populates="appointments")
    service: Mapped["Service"] = relationship("Service", back_populates="appointments")
    contact: Mapped[Optional["Contact"]] = relationship("Contact", back_populates="appointments")
    call: Mapped[Optional["Call"]] = relationship("Call", back_populates="appointments")
    verification_attempts: Mapped[List["VerificationAttempt"]] = relationship(
        "VerificationAttempt", back_populates="appointment", cascade="all, delete-orphan"
    )
    reminders: Mapped[List["Reminder"]] = relationship(
        "Reminder", back_populates="appointment", cascade="all, delete-orphan"
    )


class VerificationAttempt(Base):
    """Audit log of verification attempts for booking modifications."""

    __tablename__ = "verification_attempts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    appointment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    phone: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    call_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calls.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    business: Mapped["Business"] = relationship("Business", back_populates="verification_attempts")
    appointment: Mapped[Optional["Appointment"]] = relationship("Appointment", back_populates="verification_attempts")
    call: Mapped[Optional["Call"]] = relationship("Call", back_populates="verification_attempts")


class Transfer(Base):
    """Live call transfer records and human escalation status."""

    __tablename__ = "transfers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    call_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calls.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # initiated, completed, failed, fallback_message
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    business: Mapped["Business"] = relationship("Business", back_populates="transfers")
    call: Mapped[Optional["Call"]] = relationship("Call", back_populates="transfers")


class Notification(Base):
    """Outgoing notification tracking for emails to owners and customers."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(100), nullable=False)  # booking_confirmation, booking_cancelled, owner_alert, etc.
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")  # pending, sent, failed
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    business: Mapped["Business"] = relationship("Business", back_populates="notifications")


class Reminder(Base):
    """Scheduled customer appointment reminders (e.g. 24h prior to appointment)."""

    __tablename__ = "reminders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    send_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="email")  # "email" or "call"
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")  # pending, sent, failed, cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    business: Mapped["Business"] = relationship("Business", back_populates="reminders")
    appointment: Mapped["Appointment"] = relationship("Appointment", back_populates="reminders")


class User(Base):
    """Registered team user account."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    memberships: Mapped[List["Membership"]] = relationship(
        "Membership", back_populates="user", cascade="all, delete-orphan"
    )
    sessions: Mapped[List["Session"]] = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog", back_populates="user"
    )


class Membership(Base):
    """User membership in a business tenant with RBAC role."""

    __tablename__ = "memberships"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # owner, manager, staff
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    user: Mapped["User"] = relationship("User", back_populates="memberships")
    business: Mapped["Business"] = relationship("Business", back_populates="memberships")

    __table_args__ = (
        Index("uq_memberships_user_business", "user_id", "business_id", unique=True),
    )


class Session(Base):
    """Server-side authenticated session."""

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    current_business_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    user: Mapped["User"] = relationship("User", back_populates="sessions")
    current_business: Mapped[Optional["Business"]] = relationship("Business")


class Invite(Base):
    """Pending team invitations sent via email."""

    __tablename__ = "invites"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # owner, manager, staff
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    invited_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    business: Mapped["Business"] = relationship("Business", back_populates="invites")
    invited_by: Mapped[Optional["User"]] = relationship("User")


class PasswordReset(Base):
    """Single-use password reset tokens."""

    __tablename__ = "password_resets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    user: Mapped["User"] = relationship("User")


class AuditLog(Base):
    """Immutable audit trail of actions taken in the dashboard."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    changes: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    business: Mapped["Business"] = relationship("Business", back_populates="audit_logs")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")


class Job(Base):
    """Asynchronous background work item for document/website ingestion."""

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(100), nullable=False)  # document_ingestion, url_ingestion, retention_cleanup
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    business: Mapped["Business"] = relationship("Business", back_populates="jobs")


class Contact(Base):
    """Customer identity merged across calls, messages, and appointments."""

    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    do_not_contact: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    business: Mapped["Business"] = relationship("Business", back_populates="contacts")
    calls: Mapped[List["Call"]] = relationship("Call", back_populates="contact")
    messages: Mapped[List["Message"]] = relationship("Message", back_populates="contact")
    appointments: Mapped[List["Appointment"]] = relationship("Appointment", back_populates="contact")
    follow_ups: Mapped[List["FollowUp"]] = relationship("FollowUp", back_populates="contact")

    __table_args__ = (
        Index("ix_contacts_business_phone", "business_id", "phone"),
        Index("ix_contacts_business_email", "business_id", "email"),
    )


class FollowUp(Base):
    """Actionable tasks for business staff derived from calls, messages, and misses."""

    __tablename__ = "follow_ups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assigned_to_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # message, failed_transfer, missed_question, manual
    source_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open", index=True)  # open, done, snoozed
    snoozed_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    business: Mapped["Business"] = relationship("Business", back_populates="follow_ups")
    contact: Mapped[Optional["Contact"]] = relationship("Contact", back_populates="follow_ups")
    assigned_to: Mapped[Optional["User"]] = relationship("User")


class PhoneNumber(Base):
    """Business inbound or outbound phone numbers mapped to businesses."""

    __tablename__ = "phone_numbers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    e164_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="livekit")
    label: Mapped[str] = mapped_column(String(100), nullable=False, default="Main Inbound")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    business: Mapped["Business"] = relationship("Business", back_populates="phone_numbers")


class UsageRecord(Base):
    """Detailed usage metrics and cost estimation for every call or chat session."""

    __tablename__ = "usage_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    call_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calls.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    session_type: Mapped[str] = mapped_column(String(50), nullable=False, default="phone")  # phone, widget, test_console
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stt_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tts_characters: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    llm_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tts_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    stt_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    business: Mapped["Business"] = relationship("Business", back_populates="usage_records")
    call: Mapped[Optional["Call"]] = relationship("Call")


class UsageLimits(Base):
    """Per-tenant usage limits configured by platform admins."""

    __tablename__ = "usage_limits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    voice_minutes_per_month: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    chat_messages_per_month: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    max_concurrent_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    max_call_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=600)
    llm_tokens_per_month: Mapped[int] = mapped_column(Integer, nullable=False, default=500000)
    hard_limit_enforced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    business: Mapped["Business"] = relationship("Business", back_populates="usage_limits")


class WidgetSettings(Base):
    """Settings, styling, and public key authentication for the embeddable chat widget."""

    __tablename__ = "widget_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    public_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allowed_origins: Mapped[str] = mapped_column(Text, nullable=False, default="*")
    primary_color: Mapped[str] = mapped_column(String(30), nullable=False, default="#2563EB")
    greeting_message: Mapped[str] = mapped_column(Text, nullable=False, default="Hi! How can we help you today?")
    ask_lead_capture: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    require_lead_name: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_booking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rate_limit_rpm: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    max_turns_per_session: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    business: Mapped["Business"] = relationship("Business", back_populates="widget_settings")


class BlocklistEntry(Base):
    """Abuse prevention blocklist for phone numbers and IP addresses."""

    __tablename__ = "blocklist"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    identifier_type: Mapped[str] = mapped_column(String(30), nullable=False)  # "phone", "ip"
    identifier_value: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    blocked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    business: Mapped["Business"] = relationship("Business", back_populates="blocklist_entries")

    __table_args__ = (
        Index("ix_blocklist_business_identifier", "business_id", "identifier_type", "identifier_value"),
    )

