"""Knowledge ingestion, chunking, and similarity search."""

from callwise.knowledge.chunker import chunk_text, split_into_sentences
from callwise.knowledge.ingest import ingest_file, ingest_text_snippet, ingest_url
from callwise.knowledge.loaders import load_file, load_pdf_file, load_text_file
from callwise.knowledge.search import (
    KnowledgeMatch,
    SearchResult,
    record_knowledge_miss,
    record_knowledge_miss_async,
    search_knowledge,
    search_knowledge_async,
)
from callwise.knowledge.url_fetcher import fetch_and_clean_html, validate_public_url

__all__ = [
    "chunk_text",
    "split_into_sentences",
    "ingest_file",
    "ingest_text_snippet",
    "ingest_url",
    "load_file",
    "load_pdf_file",
    "load_text_file",
    "fetch_and_clean_html",
    "validate_public_url",
    "search_knowledge",
    "search_knowledge_async",
    "SearchResult",
    "KnowledgeMatch",
    "record_knowledge_miss",
    "record_knowledge_miss_async",
]
