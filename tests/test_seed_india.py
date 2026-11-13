"""Unit and integration tests for Option 5: 1-Click Indian Demo Clinic Seed Script."""

import uuid
import pytest
import pytest_asyncio
from typer.testing import CliRunner

from callwise.cli import app
from callwise.db.models import Business, Chunk, Document, Service
from callwise.db.seed import INDIAN_CLINIC_ID, run_seed_india, seed_indian_business
from callwise.db.session import async_engine, get_sync_session
from callwise.knowledge.search import search_knowledge

runner = CliRunner()


@pytest_asyncio.fixture(autouse=True)
async def cleanup_db_pool():
    """Ensure async engine pool is disposed within the running event loop."""
    yield
    await async_engine.dispose()


def test_seed_indian_business_creates_records():
    """Verify seed_indian_business populates clinic, INR services, and FAQ vector chunks."""
    with get_sync_session() as session:
        biz = seed_indian_business(session)
        session.commit()

        assert biz.id == INDIAN_CLINIC_ID
        assert biz.name == "Aarav Health & Dental Clinic"
        assert biz.timezone == "Asia/Kolkata"
        assert biz.transfer_number == "+918025251122"

        # Verify services in INR
        services = session.query(Service).filter(Service.business_id == INDIAN_CLINIC_ID).all()
        assert len(services) == 5
        service_names = {s.name: s.price for s in services}
        assert service_names["Root Canal Treatment (Single Sitting)"] == 4500.0
        assert service_names["Zoom Laser Teeth Whitening"] == 3500.0
        assert service_names["Routine Scaling & Ultrasonic Polishing"] == 1500.0
        assert service_names["Dental Implant Consultation & 3D CBCT Scan"] == 800.0
        assert service_names["Emergency Toothache & Broken Tooth Relief"] == 600.0

        # Verify knowledge base FAQs
        docs = session.query(Document).filter(Document.business_id == INDIAN_CLINIC_ID).all()
        assert len(docs) == 5
        doc_titles = {d.title for d in docs}
        assert "Payment Methods and UPI Options" in doc_titles
        assert "Clinic Location, Metro, and Directions" in doc_titles
        assert "Specialist Doctors and Qualifications" in doc_titles

        chunks = session.query(Chunk).filter(Chunk.business_id == INDIAN_CLINIC_ID).all()
        assert len(chunks) == 5
        for c in chunks:
            assert len(c.embedding) == 384


def test_knowledge_search_aarav_clinic_faqs():
    """Verify semantic search answers realistic Indian clinic inquiries."""
    with get_sync_session() as session:
        seed_indian_business(session)
        session.commit()

        # 1. UPI payment search
        upi_res = search_knowledge(
            session=session,
            business_id=INDIAN_CLINIC_ID,
            query="Can I pay via Google Pay, PhonePe, or Paytm UPI QR code?",
            top_k=2,
        )
        assert upi_res.is_match is True
        assert len(upi_res.matches) > 0
        top_match = upi_res.matches[0]
        assert "UPI" in top_match.content or "Google Pay" in top_match.content

        # 2. Metro connectivity search
        metro_res = search_knowledge(
            session=session,
            business_id=INDIAN_CLINIC_ID,
            query="Which Namma Metro station is near the clinic in Indiranagar?",
            top_k=2,
        )
        assert metro_res.is_match is True
        assert len(metro_res.matches) > 0
        assert "Metro" in metro_res.matches[0].content or "Indiranagar" in metro_res.matches[0].content


def test_cli_seed_india_command():
    """Verify 'callwise seed-india' CLI command executes and reports success table."""
    result = runner.invoke(app, ["seed-india"])
    assert result.exit_code == 0
    assert "Aarav Health & Dental Clinic" in result.output
    assert "Asia/Kolkata" in result.output
    assert "+918025251122" in result.output

