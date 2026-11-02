"""Unit and integration tests for knowledge search, threshold cutoff, and tenant isolation."""

import uuid
import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from callwise.cli import app
from callwise.db.models import KnowledgeMiss
from callwise.db.seed import DENTAL_CLINIC_ID, SALON_SPA_ID, run_seed
from callwise.db.session import get_sync_session
from callwise.knowledge.ingest import ingest_file
from callwise.knowledge.search import (
    search_knowledge,
    search_knowledge_async,
)


@pytest.fixture(scope="module", autouse=True)
def setup_seed_and_docs(tmp_path_factory):
    """Seed demo businesses and ingest distinct knowledge documents once for module."""
    run_seed()

    tmp_dir = tmp_path_factory.mktemp("search_docs")

    # Ingest Dental Clinic knowledge
    dental_doc = tmp_dir / "dental_services.txt"
    dental_doc.write_text(
        "BrightSmile Dental Services and Insurance:\n"
        "We offer in-office Zoom teeth whitening for $350. The procedure takes 60 minutes.\n"
        "Root canal treatments are performed under local anesthesia and start at $800.\n"
        "We accept Delta Dental, MetLife, Cigna, and Aetna PPO dental insurance plans.\n"
        "Emergency toothache appointments are accommodated on the same day if called before noon.",
        encoding="utf-8",
    )
    ingest_file(
        business_id=DENTAL_CLINIC_ID,
        file_path=str(dental_doc),
        title="Dental Services Guide",
    )

    # Ingest Salon & Spa knowledge
    salon_doc = tmp_dir / "salon_treatments.txt"
    salon_doc.write_text(
        "Luxe Glow Salon Hair & Spa Treatments.\n\n"
        "Custom Balayage and foil highlights start at $220 and include toner and blowout.\n\n"
        "Organic hydration scalp facials last 50 minutes for $95.\n\n"
        "We use cruelty-free Kevin Murphy hair products for all coloring services.\n\n"
        "Bridal packages include trial styling, champagne, and bridal party discounts.",
        encoding="utf-8",
    )
    ingest_file(
        business_id=SALON_SPA_ID,
        file_path=str(salon_doc),
        title="Salon Treatment Menu",
    )


def test_search_knowledge_relevant_match():
    """Verify relevant query returns top match above threshold with source metadata."""
    result = search_knowledge(
        business_id=DENTAL_CLINIC_ID,
        query="How much does teeth whitening cost and how long does it take?",
        threshold=0.45,
    )
    assert result.is_match is True
    assert result.top_score >= 0.45
    assert len(result.matches) > 0
    top = result.matches[0]
    assert "Dental Services Guide" in top.source_title
    assert "$350" in top.content or "whitening" in top.content.lower()

    # Verify formatted context is suitable for prompt injection
    context = result.formatted_context()
    assert "Dental Services Guide" in context
    assert "Similarity:" in context


def test_search_knowledge_cutoff_no_match():
    """Verify irrelevant query below similarity cutoff explicitly returns NO_MATCH."""
    result = search_knowledge(
        business_id=DENTAL_CLINIC_ID,
        query="What is the quantum mechanical spin of a Higgs boson particle?",
        threshold=0.55,
        log_miss=True,
    )
    assert result.is_match is False
    assert result.matches == []
    assert "NO_MATCH" in result.message


def test_multi_tenant_isolation():
    """Verify tenant isolation: Salon query returns NO_MATCH for Dental Clinic."""
    # Query for salon-specific service against Dental Clinic
    dental_result = search_knowledge(
        business_id=DENTAL_CLINIC_ID,
        query="What products do you use for balayage highlights?",
        threshold=0.50,
    )
    # The dental clinic must NOT return salon chunks
    for match in dental_result.matches:
        assert "Kevin Murphy" not in match.content
        assert "Balayage" not in match.content

    # The same query against Salon MUST find the matches
    salon_result = search_knowledge(
        business_id=SALON_SPA_ID,
        query="What products do you use for balayage highlights?",
        threshold=0.45,
    )
    assert salon_result.is_match is True
    assert any("Balayage" in m.content for m in salon_result.matches)


def test_knowledge_miss_logged_to_database():
    """Verify unanswered queries below threshold are persisted to knowledge_misses."""
    from callwise.db.models import Call
    test_query = "Do you perform veterinary surgery on parrots?"
    test_call_id = uuid.uuid4()

    # Pre-insert call session so foreign key is satisfied
    with get_sync_session() as session:
        call = Call(id=test_call_id, business_id=DENTAL_CLINIC_ID, caller_number="+15551234567")
        session.add(call)
        session.commit()

    result = search_knowledge(
        business_id=DENTAL_CLINIC_ID,
        query=test_query,
        threshold=0.60,
        call_id=test_call_id,
        log_miss=True,
    )
    assert result.is_match is False

    with get_sync_session() as session:
        miss = session.scalar(
            select(KnowledgeMiss).where(
                KnowledgeMiss.business_id == DENTAL_CLINIC_ID,
                KnowledgeMiss.call_id == test_call_id,
            )
        )
        assert miss is not None
        assert miss.query == test_query


@pytest.mark.asyncio
async def test_search_knowledge_async():
    """Verify async search works for LiveKit voice pipeline integration."""
    result = await search_knowledge_async(
        business_id=SALON_SPA_ID,
        query="How much do hair highlights and balayage cost?",
        threshold=0.45,
    )
    assert result.is_match is True
    assert len(result.matches) >= 1
    assert "Balayage" in result.matches[0].content


def test_cli_search_knowledge():
    """Verify CLI search-knowledge command outputs matches and handles no-match."""
    runner = CliRunner()

    # Matching query
    res = runner.invoke(
        app,
        [
            "search-knowledge",
            "--business-id",
            str(DENTAL_CLINIC_ID),
            "--query",
            "teeth whitening",
        ],
    )
    assert res.exit_code == 0
    assert "[MATCH FOUND]" in res.output

    # No match query
    no_match_res = runner.invoke(
        app,
        [
            "search-knowledge",
            "--business-id",
            str(DENTAL_CLINIC_ID),
            "--query",
            "airplane flight training",
            "--threshold",
            "0.70",
        ],
    )
    assert no_match_res.exit_code == 0
    assert "[NO MATCH]" in no_match_res.output
