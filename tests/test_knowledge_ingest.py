"""Tests for knowledge ingestion: chunker, loaders, SSRF protection, embeddings, and storage."""

import os
import tempfile
import uuid
import pytest
from pypdf import PdfWriter
from sqlalchemy import select
from typer.testing import CliRunner

from callwise.cli import app
from callwise.config import settings
from callwise.db.models import Chunk, Document
from callwise.db.seed import DENTAL_CLINIC_ID, run_seed
from callwise.db.session import get_sync_session
from callwise.knowledge.chunker import chunk_text
from callwise.knowledge.ingest import ingest_file
from callwise.knowledge.loaders import load_file
from callwise.knowledge.url_fetcher import validate_public_url
from callwise.providers.embeddings import LocalEmbeddingProvider


def test_chunk_text_basic():
    """Verify chunking splits text with boundaries and overlap."""
    text = (
        "Paragraph one is about dental cleanings. Regular cleanings prevent cavities. "
        "They are recommended every six months.\n\n"
        "Paragraph two discusses teeth whitening. Professional whitening removes deep stains. "
        "It takes about sixty minutes per session.\n\n"
        "Paragraph three covers emergency dentistry. If you have severe pain, call us immediately."
    )
    chunks = chunk_text(text, target_chunk_size=120, chunk_overlap=30)
    assert len(chunks) >= 3
    for chunk in chunks:
        assert len(chunk) > 0


def test_loaders_txt_and_md(tmp_path):
    """Verify loading text and markdown files."""
    txt_file = tmp_path / "dental_faq.txt"
    txt_file.write_text("Q: Do you accept insurance?\nA: Yes, most major PPO plans.", encoding="utf-8")

    content, title = load_file(str(txt_file))
    assert "Dental Faq" in title
    assert "Yes, most major PPO plans" in content

    md_file = tmp_path / "salon_services.md"
    md_file.write_text("# Services\n\n- Haircut: $60\n- Balayage: $180", encoding="utf-8")

    content, title = load_file(str(md_file))
    assert "Salon Services" in title
    assert "Balayage" in content


def test_loaders_pdf(tmp_path):
    """Verify extracting text from PDF documents."""
    pdf_path = tmp_path / "pricing_guide.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    # Write empty PDF page; pypdf will return empty text
    with open(pdf_path, "wb") as f:
        writer.write(f)

    # Blank PDF should raise ValueError
    with pytest.raises(ValueError, match="PDF file contains no extractable text"):
        load_file(str(pdf_path))


@pytest.mark.parametrize(
    "invalid_url, expected_err",
    [
        ("http://localhost:8080/secret", "SSRF Protection"),
        ("http://127.0.0.1/admin", "SSRF Protection"),
        ("http://192.168.1.1/router", "SSRF Protection"),
        ("http://10.0.0.5/api", "SSRF Protection"),
        ("http://172.16.0.1/internal", "SSRF Protection"),
        ("http://169.254.169.254/latest/meta-data/", "SSRF Protection"),
        ("ftp://example.com/file.txt", "Invalid URL scheme"),
        ("file:///etc/passwd", "Invalid URL scheme"),
    ],
)
def test_ssrf_blocking(invalid_url, expected_err):
    """Verify that private IP ranges, loopback, and cloud metadata are blocked."""
    with pytest.raises(ValueError, match=expected_err):
        validate_public_url(invalid_url)


def test_embedding_provider_shape():
    """Verify local embedding provider returns correct normalized dimensions."""
    provider = LocalEmbeddingProvider()
    vec = provider.embed_text("BrightSmile Family Dental office hours and procedures")
    assert len(vec) == settings.embedding_dimension
    # Unit vector magnitude check (~1.0 for normalized embeddings)
    norm = sum(x * x for x in vec) ** 0.5
    assert abs(norm - 1.0) < 0.01

    batch_vecs = provider.embed_batch(["First sentence", "Second sentence"])
    assert len(batch_vecs) == 2
    assert len(batch_vecs[0]) == settings.embedding_dimension
    assert len(batch_vecs[1]) == settings.embedding_dimension


def test_ingest_file_to_database(tmp_path):
    """Verify end-to-end file ingestion stores Document and Chunks with embeddings."""
    run_seed()

    faq_file = tmp_path / "dental_faq.txt"
    faq_file.write_text(
        "BrightSmile Family Dental FAQ.\n\n"
        "We are located at 123 Main Street, Suite 400, New York, NY.\n"
        "We accept Delta Dental, MetLife, Cigna, and Guardian PPO insurance.\n"
        "Routine cleanings take approximately 45 minutes.\n"
        "Parking is validated for up to two hours in the adjacent garage.",
        encoding="utf-8",
    )

    doc = ingest_file(
        business_id=DENTAL_CLINIC_ID,
        file_path=str(faq_file),
        title="Dental Clinic FAQ Guide",
    )

    assert doc is not None
    assert doc.business_id == DENTAL_CLINIC_ID
    assert doc.title == "Dental Clinic FAQ Guide"
    assert doc.source_type == "file"

    with get_sync_session() as session:
        stored_chunks = session.scalars(
            select(Chunk).where(Chunk.document_id == doc.id).order_by(Chunk.chunk_index)
        ).all()
        assert len(stored_chunks) >= 1
        assert stored_chunks[0].business_id == DENTAL_CLINIC_ID
        assert len(stored_chunks[0].embedding) == settings.embedding_dimension
        assert "BrightSmile Family Dental" in stored_chunks[0].content


def test_cli_ingest_and_list_documents(tmp_path):
    """Verify CLI commands for ingesting file and listing documents."""
    run_seed()

    guide_file = tmp_path / "salon_hair_treatments.md"
    guide_file.write_text(
        "# Luxe Glow Hair Treatments\n\n"
        "Our salon uses sulfate-free organic products.\n"
        "Keratin treatments require a 24-hour advance booking.\n"
        "Complimentary sparkling water or espresso is provided to all guests.",
        encoding="utf-8",
    )

    runner = CliRunner()
    ingest_result = runner.invoke(
        app,
        [
            "ingest-file",
            "--business-id",
            str(DENTAL_CLINIC_ID),
            "--file",
            str(guide_file),
            "--title",
            "Salon Hair Guide",
        ],
    )
    assert ingest_result.exit_code == 0
    assert "[OK] Ingested document: Salon Hair Guide" in ingest_result.output

    list_result = runner.invoke(
        app,
        ["list-documents", "--business-id", str(DENTAL_CLINIC_ID)],
    )
    assert list_result.exit_code == 0
    assert "Salon Hair Guide" in list_result.output
