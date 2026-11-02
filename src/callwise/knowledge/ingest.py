"""Knowledge ingestion pipeline for files and URLs."""

import os
from typing import List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from callwise.db.models import Business, Chunk, Document
from callwise.db.session import get_sync_session
from callwise.knowledge.chunker import chunk_text
from callwise.knowledge.loaders import load_file
from callwise.knowledge.url_fetcher import fetch_and_clean_html
from callwise.providers.embeddings import get_embedding_provider


def store_document_and_chunks(
    session: Session,
    business_id: uuid.UUID,
    title: str,
    source_type: str,
    source_uri: str,
    content: str,
    chunks: List[str],
    embeddings: List[List[float]],
) -> Document:
    """Persist document metadata and associated vector chunks to the database."""
    # Ensure tenant business exists
    business = session.get(Business, business_id)
    if not business:
        raise ValueError(f"Business with ID '{business_id}' does not exist.")

    doc = Document(
        business_id=business_id,
        title=title,
        source_type=source_type,
        source_uri=source_uri,
    )
    session.add(doc)
    session.flush()

    for idx, (chunk_content, embedding) in enumerate(zip(chunks, embeddings)):
        chunk_record = Chunk(
            business_id=business_id,
            document_id=doc.id,
            content=chunk_content,
            embedding=embedding,
            chunk_index=idx,
        )
        session.add(chunk_record)

    session.flush()
    return doc


def ingest_file(
    business_id: uuid.UUID,
    file_path: str,
    title: Optional[str] = None,
) -> Document:
    """
    Ingest a PDF, TXT, or MD file for a tenant business.
    Extracts text, splits into chunks, computes embeddings, and stores in PostgreSQL.
    """
    raw_content, inferred_title = load_file(file_path)
    final_title = title or inferred_title

    chunks = chunk_text(raw_content)
    if not chunks:
        raise ValueError(f"File '{file_path}' yielded no readable text content.")

    embedding_provider = get_embedding_provider()
    embeddings = embedding_provider.embed_batch(chunks)

    with get_sync_session() as session:
        doc = store_document_and_chunks(
            session=session,
            business_id=business_id,
            title=final_title,
            source_type="file",
            source_uri=str(file_path),
            content=raw_content,
            chunks=chunks,
            embeddings=embeddings,
        )
        # Refresh to populate ID outside session
        doc_id = doc.id
        doc_title = doc.title
        doc_source = doc.source_uri

    # Re-fetch or reconstruct return entity with session closed
    with get_sync_session() as session:
        return session.get(Document, doc_id)


def ingest_url(
    business_id: uuid.UUID,
    url: str,
    title: Optional[str] = None,
) -> Document:
    """
    Ingest content from a public website URL with SSRF protection.
    Extracts readable HTML body text, splits into chunks, computes embeddings, and stores.
    """
    raw_content, fetched_title = fetch_and_clean_html(url)
    final_title = title or fetched_title

    chunks = chunk_text(raw_content)
    if not chunks:
        raise ValueError(f"URL '{url}' yielded no readable text content.")

    embedding_provider = get_embedding_provider()
    embeddings = embedding_provider.embed_batch(chunks)

    with get_sync_session() as session:
        doc = store_document_and_chunks(
            session=session,
            business_id=business_id,
            title=final_title,
            source_type="url",
            source_uri=url,
            content=raw_content,
            chunks=chunks,
            embeddings=embeddings,
        )
        doc_id = doc.id

    with get_sync_session() as session:
        return session.get(Document, doc_id)
