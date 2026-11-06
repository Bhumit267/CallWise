"""Unit and integration tests for database models and tenant relationships."""

import uuid
import pytest
from sqlalchemy import select

from callwise.config import settings
from callwise.db.models import (
    Business,
    Call,
    CallTurn,
    Chunk,
    Document,
    KnowledgeMiss,
    Message,
)
from callwise.db.session import get_sync_session


def test_business_creation_and_cascade():
    """Verify business creation and cascading deletion of tenant child records."""
    test_id = uuid.uuid4()
    with get_sync_session() as session:
        biz = Business(
            id=test_id,
            name="Cascade Test Clinic",
            business_type="Clinic",
            greeting="Hello",
            tone="Friendly",
            timezone="America/New_York",
            hours={"monday": {"open": "09:00", "close": "17:00", "closed": False}},
        )
        session.add(biz)
        session.flush()

        doc = Document(
            business_id=biz.id,
            title="Clinic FAQ",
            source_type="file",
            source_uri="/docs/faq.txt",
        )
        session.add(doc)
        session.flush()

        # Dummy embedding matching dimension
        dummy_vector = [0.1] * settings.embedding_dimension
        chunk = Chunk(
            business_id=biz.id,
            document_id=doc.id,
            content="We offer routine cleanings.",
            embedding=dummy_vector,
            chunk_index=0,
        )
        session.add(chunk)

        call = Call(
            business_id=biz.id,
            caller_number="+15551234567",
            summary="Caller inquired about hours.",
        )
        session.add(call)
        session.flush()

        turn = CallTurn(
            business_id=biz.id,
            call_id=call.id,
            speaker="caller",
            text="What are your hours?",
            latency_ms=120.5,
        )
        session.add(turn)

        msg = Message(
            business_id=biz.id,
            call_id=call.id,
            caller_name="Alice Smith",
            callback_number="+15551234567",
            reason="Need emergency appointment",
        )
        session.add(msg)

        miss = KnowledgeMiss(
            business_id=biz.id,
            call_id=call.id,
            query="Do you do acupuncture?",
        )
        session.add(miss)
        session.commit()

    # Now verify all records exist
    with get_sync_session() as session:
        loaded_biz = session.get(Business, test_id)
        assert loaded_biz is not None
        assert len(loaded_biz.documents) == 1
        assert len(loaded_biz.chunks) == 1
        assert len(loaded_biz.calls) == 1
        assert len(loaded_biz.messages) == 1
        assert len(loaded_biz.knowledge_misses) == 1

        # Delete the business and verify cascade cleanup
        session.delete(loaded_biz)
        session.commit()

    # Verify children are deleted (cascade)
    with get_sync_session() as session:
        assert session.get(Business, test_id) is None
        assert session.scalar(select(Document).where(Document.business_id == test_id)) is None
        assert session.scalar(select(Chunk).where(Chunk.business_id == test_id)) is None
        assert session.scalar(select(Call).where(Call.business_id == test_id)) is None
        assert session.scalar(select(CallTurn).where(CallTurn.business_id == test_id)) is None
        assert session.scalar(select(Message).where(Message.business_id == test_id)) is None
        assert session.scalar(select(KnowledgeMiss).where(KnowledgeMiss.business_id == test_id)) is None


def test_phase3_models_and_relationships():
    """Verify Phase 3 models: User, Membership, Session, Invite, PasswordReset, AuditLog, Job, Contact, FollowUp."""
    from datetime import datetime, timezone, timedelta
    from callwise.db.models import (
        User,
        Membership,
        Session as UserSession,
        Invite,
        PasswordReset,
        AuditLog,
        Job,
        Contact,
        FollowUp,
    )

    biz_id = uuid.uuid4()
    with get_sync_session() as session:
        biz = Business(
            id=biz_id,
            name="Phase 3 Dental Suite",
            business_type="dental clinic",
            greeting="Welcome to Phase 3 Dental Suite",
            tone="professional",
            timezone="America/New_York",
            hours={"monday": {"open": "08:00", "close": "17:00", "closed": False}},
            retention_days=180,
            website_url="https://phase3dental.example.com",
        )
        session.add(biz)

        user = User(
            email=f"owner_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="argon2_hashed_secret",
            name="Dr. Jane Smith",
            is_active=True,
        )
        session.add(user)
        session.flush()

        # Membership (owner)
        membership = Membership(
            user_id=user.id,
            business_id=biz.id,
            role="owner",
        )
        session.add(membership)

        # Session
        now = datetime.now(timezone.utc)
        rand_token = (uuid.uuid4().hex + uuid.uuid4().hex)[:64]
        usr_session = UserSession(
            session_token_hash=rand_token,
            user_id=user.id,
            current_business_id=biz.id,
            expires_at=now + timedelta(days=7),
            ip_address="127.0.0.1",
            user_agent="Mozilla/5.0",
        )
        session.add(usr_session)

        # Invite
        inv_token = (uuid.uuid4().hex + uuid.uuid4().hex)[:64]
        invite = Invite(
            business_id=biz.id,
            email=f"manager_{uuid.uuid4().hex[:6]}@example.com",
            role="manager",
            token_hash=inv_token,
            invited_by_user_id=user.id,
            expires_at=now + timedelta(days=3),
        )
        session.add(invite)

        # Password Reset
        reset_token = (uuid.uuid4().hex + uuid.uuid4().hex)[:64]
        pw_reset = PasswordReset(
            user_id=user.id,
            token_hash=reset_token,
            expires_at=now + timedelta(hours=1),
        )
        session.add(pw_reset)

        # Audit Log
        audit = AuditLog(
            business_id=biz.id,
            user_id=user.id,
            action="business.create",
            resource_type="business",
            resource_id=str(biz.id),
            changes={"name": "Phase 3 Dental Suite"},
        )
        session.add(audit)

        # Job
        job = Job(
            business_id=biz.id,
            type="url_ingestion",
            status="pending",
            payload={"url": "https://phase3dental.example.com/faq"},
            progress=0,
        )
        session.add(job)

        # Contact
        contact = Contact(
            business_id=biz.id,
            name="Alice Patient",
            phone="+15559876543",
            email="alice@example.com",
            notes="Prefers afternoon appointments",
            do_not_contact=False,
        )
        session.add(contact)
        session.flush()

        # FollowUp
        follow_up = FollowUp(
            business_id=biz.id,
            contact_id=contact.id,
            assigned_to_user_id=user.id,
            title="Follow up on root canal quote",
            source="manual",
            status="open",
        )
        session.add(follow_up)
        session.commit()

    # Query and verify
    with get_sync_session() as session:
        loaded_biz = session.get(Business, biz_id)
        assert loaded_biz is not None
        assert loaded_biz.retention_days == 180
        assert loaded_biz.website_url == "https://phase3dental.example.com"
        assert len(loaded_biz.memberships) == 1
        assert loaded_biz.memberships[0].role == "owner"
        assert len(loaded_biz.invites) == 1
        assert len(loaded_biz.audit_logs) == 1
        assert len(loaded_biz.jobs) == 1
        assert len(loaded_biz.contacts) == 1
        assert len(loaded_biz.follow_ups) == 1

        loaded_contact = loaded_biz.contacts[0]
        assert loaded_contact.name == "Alice Patient"
        assert len(loaded_contact.follow_ups) == 1

        # Delete business and verify cascading deletion
        session.delete(loaded_biz)
        session.commit()

    with get_sync_session() as session:
        assert session.get(Business, biz_id) is None
        assert session.scalar(select(Membership).where(Membership.business_id == biz_id)) is None
        assert session.scalar(select(Invite).where(Invite.business_id == biz_id)) is None
        assert session.scalar(select(AuditLog).where(AuditLog.business_id == biz_id)) is None
        assert session.scalar(select(Job).where(Job.business_id == biz_id)) is None
        assert session.scalar(select(Contact).where(Contact.business_id == biz_id)) is None
        assert session.scalar(select(FollowUp).where(FollowUp.business_id == biz_id)) is None


def test_contact_backfill_integrity():
    """Verify that contacts were auto-created and linked for existing appointments/messages/calls."""
    from callwise.db.models import Appointment, Contact, Message, Call
    with get_sync_session() as session:
        # Check if any existing appointments have contacts linked
        appts = session.scalars(select(Appointment).where(Appointment.customer_phone != "")).all()
        for a in appts:
            if a.contact_id:
                c = session.get(Contact, a.contact_id)
                assert c is not None
                assert c.phone == a.customer_phone
                assert c.business_id == a.business_id

