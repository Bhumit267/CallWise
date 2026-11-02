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
