"""Similarity search against tenant vector embeddings with threshold gating."""

from typing import List, Optional
import uuid
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from callwise.config import settings
from callwise.db.models import Chunk, Document, KnowledgeMiss
from callwise.db.session import get_async_session, get_sync_session
from callwise.providers.embeddings import get_embedding_provider


class KnowledgeMatch(BaseModel):
    """A single matched knowledge chunk with metadata and similarity score."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    similarity: float
    source_title: str
    source_uri: str
    source_type: str


class SearchResult(BaseModel):
    """Aggregate search outcome containing matches or an explicit no-match state."""

    is_match: bool
    top_score: float = 0.0
    matches: List[KnowledgeMatch] = Field(default_factory=list)
    message: Optional[str] = None

    def formatted_context(self) -> str:
        """Format matches into readable text context for LLM prompt injection."""
        if not self.is_match or not self.matches:
            return ""
        sections = []
        for i, match in enumerate(self.matches, 1):
            sections.append(
                f"[Source {i}: {match.source_title} ({match.source_uri}) | Similarity: {match.similarity:.2f}]\n"
                f"{match.content}"
            )
        return "\n\n".join(sections)


def record_knowledge_miss(
    session: Session,
    business_id: uuid.UUID,
    query: str,
    call_id: Optional[uuid.UUID] = None,
) -> KnowledgeMiss:
    """Save an unanswered query to knowledge_misses for business review."""
    miss = KnowledgeMiss(
        business_id=business_id,
        call_id=call_id,
        query=query.strip(),
    )
    session.add(miss)
    session.flush()
    return miss


async def record_knowledge_miss_async(
    session: AsyncSession,
    business_id: uuid.UUID,
    query: str,
    call_id: Optional[uuid.UUID] = None,
) -> KnowledgeMiss:
    """Async variant: Save an unanswered query to knowledge_misses."""
    miss = KnowledgeMiss(
        business_id=business_id,
        call_id=call_id,
        query=query.strip(),
    )
    session.add(miss)
    await session.flush()
    return miss


def search_knowledge(
    business_id: uuid.UUID,
    query: str,
    threshold: Optional[float] = None,
    top_k: int = 3,
    call_id: Optional[uuid.UUID] = None,
    log_miss: bool = True,
    session: Optional[Session] = None,
) -> SearchResult:
    """
    Synchronously search knowledge base for a specific business tenant.

    Returns SearchResult with top matches or explicit is_match=False with message='NO_MATCH'.
    """
    cutoff = threshold if threshold is not None else settings.similarity_threshold
    embedding_provider = get_embedding_provider()
    query_vector = embedding_provider.embed_text(query)

    def _execute(s: Session) -> SearchResult:
        # Cosine distance in pgvector: 0.0 = identical, 1.0 = orthogonal
        # Cosine similarity = 1 - cosine_distance
        cosine_dist = Chunk.embedding.cosine_distance(query_vector)

        stmt = (
            select(
                Chunk,
                Document.title,
                Document.source_uri,
                Document.source_type,
                (1.0 - cosine_dist).label("similarity"),
            )
            .join(Document, Chunk.document_id == Document.id)
            .where(Chunk.business_id == business_id)
            .order_by(cosine_dist.asc())
            .limit(top_k)
        )

        rows = s.execute(stmt).all()

        if not rows:
            if log_miss:
                record_knowledge_miss(s, business_id=business_id, query=query, call_id=call_id)
            return SearchResult(
                is_match=False,
                top_score=0.0,
                matches=[],
                message="NO_MATCH: No knowledge chunks found for this business.",
            )

        top_similarity = float(rows[0].similarity)

        # Strict cutoff check against similarity threshold
        if top_similarity < cutoff:
            if log_miss:
                record_knowledge_miss(s, business_id=business_id, query=query, call_id=call_id)
            return SearchResult(
                is_match=False,
                top_score=top_similarity,
                matches=[],
                message=f"NO_MATCH: Top similarity {top_similarity:.3f} is below cutoff {cutoff:.3f}.",
            )

        # Filter all rows that satisfy the cutoff threshold
        valid_matches = []
        for chunk, doc_title, doc_uri, doc_type, sim in rows:
            sim_val = float(sim)
            if sim_val >= cutoff:
                valid_matches.append(
                    KnowledgeMatch(
                        chunk_id=chunk.id,
                        document_id=chunk.document_id,
                        content=chunk.content,
                        similarity=round(sim_val, 4),
                        source_title=doc_title,
                        source_uri=doc_uri,
                        source_type=doc_type,
                    )
                )

        return SearchResult(
            is_match=True,
            top_score=top_similarity,
            matches=valid_matches,
            message=None,
        )

    if session is not None:
        return _execute(session)
    else:
        with get_sync_session() as new_session:
            return _execute(new_session)


async def search_knowledge_async(
    business_id: uuid.UUID,
    query: str,
    threshold: Optional[float] = None,
    top_k: int = 3,
    call_id: Optional[uuid.UUID] = None,
    log_miss: bool = True,
    session: Optional[AsyncSession] = None,
) -> SearchResult:
    """
    Asynchronously search knowledge base for a specific business tenant (used by voice agent).
    """
    cutoff = threshold if threshold is not None else settings.similarity_threshold
    embedding_provider = get_embedding_provider()
    query_vector = embedding_provider.embed_text(query)

    async def _execute_async(s: AsyncSession) -> SearchResult:
        cosine_dist = Chunk.embedding.cosine_distance(query_vector)

        stmt = (
            select(
                Chunk,
                Document.title,
                Document.source_uri,
                Document.source_type,
                (1.0 - cosine_dist).label("similarity"),
            )
            .join(Document, Chunk.document_id == Document.id)
            .where(Chunk.business_id == business_id)
            .order_by(cosine_dist.asc())
            .limit(top_k)
        )

        result = await s.execute(stmt)
        rows = result.all()

        if not rows:
            if log_miss:
                await record_knowledge_miss_async(s, business_id=business_id, query=query, call_id=call_id)
            return SearchResult(
                is_match=False,
                top_score=0.0,
                matches=[],
                message="NO_MATCH: No knowledge chunks found for this business.",
            )

        top_similarity = float(rows[0].similarity)

        if top_similarity < cutoff:
            if log_miss:
                await record_knowledge_miss_async(s, business_id=business_id, query=query, call_id=call_id)
            return SearchResult(
                is_match=False,
                top_score=top_similarity,
                matches=[],
                message=f"NO_MATCH: Top similarity {top_similarity:.3f} is below cutoff {cutoff:.3f}.",
            )

        valid_matches = []
        for chunk, doc_title, doc_uri, doc_type, sim in rows:
            sim_val = float(sim)
            if sim_val >= cutoff:
                valid_matches.append(
                    KnowledgeMatch(
                        chunk_id=chunk.id,
                        document_id=chunk.document_id,
                        content=chunk.content,
                        similarity=round(sim_val, 4),
                        source_title=doc_title,
                        source_uri=doc_uri,
                        source_type=doc_type,
                    )
                )

        return SearchResult(
            is_match=True,
            top_score=top_similarity,
            matches=valid_matches,
            message=None,
        )

    if session is not None:
        return await _execute_async(session)
    else:
        async with get_async_session() as new_session:
            return await _execute_async(new_session)
