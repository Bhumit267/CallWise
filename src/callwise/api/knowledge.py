"""Knowledge API router: sources CRUD, Q&A snippets, async uploads, URL ingestion, and background jobs."""

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from callwise.api.audit import record_audit_log
from callwise.api.deps import get_tenant_db
from callwise.api.permissions import require_manager, require_staff
from callwise.db.models import Business, Chunk, Document, Job, Session as UserSession, User
from callwise.knowledge.ingest import ingest_text_snippet
from callwise.knowledge.url_fetcher import validate_public_url

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])

UPLOAD_DIR = Path("uploads")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}


# ============================================================================
# Schemas
# ============================================================================

class DocumentSourceItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    source_type: str  # file, url, qa_snippet
    source_uri: str
    chunk_count: int
    created_at: datetime


class QACreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Question or topic title")
    content: str = Field(..., min_length=1, description="Answer or snippet text content")


class QAUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: str = Field(..., min_length=1)


class URLIngestRequest(BaseModel):
    url: str = Field(..., description="Public website URL to crawl and ingest")
    title: Optional[str] = Field(None, description="Optional custom title for the knowledge source")


class JobStatusResponse(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    progress: int
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/sources", response_model=List[DocumentSourceItem])
async def list_sources(
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> List[DocumentSourceItem]:
    """List all ingested knowledge sources (files, URLs, Q&A snippets) and chunk counts."""
    _, business, _, _ = auth_ctx

    stmt = (
        select(Document)
        .options(selectinload(Document.chunks))
        .where(Document.business_id == business.id)
        .order_by(Document.created_at.desc())
    )
    docs = (await db.execute(stmt)).scalars().all()

    return [
        DocumentSourceItem(
            id=d.id,
            title=d.title,
            source_type=d.source_type,
            source_uri=d.source_uri,
            chunk_count=len(d.chunks),
            created_at=d.created_at,
        )
        for d in docs
    ]


@router.delete("/sources/{document_id}")
async def delete_source(
    document_id: uuid.UUID,
    request: Request,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> Dict[str, Any]:
    """Delete a knowledge source and all its associated vector chunks."""
    user, business, _, _ = auth_ctx

    stmt = select(Document).where(Document.id == document_id, Document.business_id == business.id)
    doc = (await db.execute(stmt)).scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document source '{document_id}' not found.",
        )

    title = doc.title
    await db.delete(doc)
    await record_audit_log(
        db=db,
        business_id=business.id,
        user_id=user.id,
        action="delete_knowledge_source",
        resource_type="document",
        resource_id=str(document_id),
        changes={"title": title, "source_type": doc.source_type},
        ip_address=request.client.host if request.client else None,
    )
    await db.flush()

    return {"status": "ok", "message": f"Source '{title}' and its chunks have been deleted.", "document_id": str(document_id)}


@router.post("/qa", response_model=DocumentSourceItem, status_code=status.HTTP_201_CREATED)
async def create_qa_snippet(
    payload: QACreate,
    request: Request,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> DocumentSourceItem:
    """Create and immediately chunk & embed a manual Q&A text snippet."""
    user, business, _, _ = auth_ctx

    doc = ingest_text_snippet(
        business_id=business.id,
        title=payload.title,
        content=payload.content,
    )

    await record_audit_log(
        db=db,
        business_id=business.id,
        user_id=user.id,
        action="create_qa_snippet",
        resource_type="document",
        resource_id=str(doc.id),
        changes={"title": payload.title},
        ip_address=request.client.host if request.client else None,
    )

    # Re-fetch with chunks loaded
    stmt = (
        select(Document)
        .options(selectinload(Document.chunks))
        .where(Document.id == doc.id, Document.business_id == business.id)
    )
    saved_doc = (await db.execute(stmt)).scalar_one()

    return DocumentSourceItem(
        id=saved_doc.id,
        title=saved_doc.title,
        source_type=saved_doc.source_type,
        source_uri=saved_doc.source_uri,
        chunk_count=len(saved_doc.chunks),
        created_at=saved_doc.created_at,
    )


@router.put("/qa/{document_id}", response_model=DocumentSourceItem)
async def update_qa_snippet(
    document_id: uuid.UUID,
    payload: QAUpdate,
    request: Request,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> DocumentSourceItem:
    """Update a Q&A snippet, re-generating its chunks and vector embeddings."""
    user, business, _, _ = auth_ctx

    stmt = select(Document).where(Document.id == document_id, Document.business_id == business.id)
    existing_doc = (await db.execute(stmt)).scalar_one_or_none()

    if not existing_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Q&A snippet '{document_id}' not found.",
        )

    title = payload.title or existing_doc.title
    # Delete old chunks and recreate
    await db.delete(existing_doc)
    await db.flush()

    new_doc = ingest_text_snippet(
        business_id=business.id,
        title=title,
        content=payload.content,
    )

    await record_audit_log(
        db=db,
        business_id=business.id,
        user_id=user.id,
        action="update_qa_snippet",
        resource_type="document",
        resource_id=str(new_doc.id),
        changes={"title": title, "replaced_document_id": str(document_id)},
        ip_address=request.client.host if request.client else None,
    )

    # Load with chunks
    fetch_stmt = (
        select(Document)
        .options(selectinload(Document.chunks))
        .where(Document.id == new_doc.id, Document.business_id == business.id)
    )
    saved = (await db.execute(fetch_stmt)).scalar_one()

    return DocumentSourceItem(
        id=saved.id,
        title=saved.title,
        source_type=saved.source_type,
        source_uri=saved.source_uri,
        chunk_count=len(saved.chunks),
        created_at=saved.created_at,
    )


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Query(None, description="Optional custom source title"),
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> Dict[str, Any]:
    """
    Secure file upload (.pdf, .txt, .md) with size limit.
    Enqueues an asynchronous document_ingestion job.
    """
    _, business, _, _ = auth_ctx

    filename = file.filename or "unknown.txt"
    _, ext = os.path.splitext(filename)
    ext = ext.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{ext}'. Allowed extensions are: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Read content and enforce size limit
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {MAX_FILE_SIZE // (1024 * 1024)} MB.",
        )

    # Save to disk with random UUID name
    business_dir = UPLOAD_DIR / str(business.id)
    business_dir.mkdir(parents=True, exist_ok=True)
    safe_filename = f"{uuid.uuid4().hex}{ext}"
    dest_path = business_dir / safe_filename

    with open(dest_path, "wb") as f:
        f.write(content)

    final_title = title.strip() if title and title.strip() else filename

    # Create background job
    job = Job(
        id=uuid.uuid4(),
        business_id=business.id,
        type="document_ingestion",
        status="pending",
        payload={
            "file_path": str(dest_path),
            "title": final_title,
            "original_filename": filename,
        },
        progress=0,
    )
    db.add(job)
    await db.flush()

    return {
        "job_id": str(job.id),
        "status": "pending",
        "message": f"Document '{final_title}' queued for ingestion.",
    }


@router.post("/url", status_code=status.HTTP_202_ACCEPTED)
async def enqueue_url_ingestion(
    payload: URLIngestRequest,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> Dict[str, Any]:
    """Validate public website URL against SSRF and enqueue an asynchronous url_ingestion job."""
    _, business, _, _ = auth_ctx

    raw_url = payload.url.strip()
    try:
        validate_public_url(raw_url)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or prohibited URL: {err}",
        )

    job = Job(
        id=uuid.uuid4(),
        business_id=business.id,
        type="url_ingestion",
        status="pending",
        payload={
            "url": raw_url,
            "title": payload.title or raw_url,
        },
        progress=0,
    )
    db.add(job)
    await db.flush()

    return {
        "job_id": str(job.id),
        "status": "pending",
        "message": f"URL '{raw_url}' queued for ingestion.",
    }


@router.post("/sources/{document_id}/reingest", status_code=status.HTTP_202_ACCEPTED)
async def reingest_source(
    document_id: uuid.UUID,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> Dict[str, Any]:
    """Re-enqueue an existing document or URL source for fresh ingestion."""
    _, business, _, _ = auth_ctx

    stmt = select(Document).where(Document.id == document_id, Document.business_id == business.id)
    doc = (await db.execute(stmt)).scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document source '{document_id}' not found.",
        )

    # Delete existing chunks
    await db.execute(delete(Chunk).where(Chunk.document_id == document_id))

    if doc.source_type == "url":
        job_type = "url_ingestion"
        payload = {"url": doc.source_uri, "title": doc.title}
    elif doc.source_type == "file":
        job_type = "document_ingestion"
        payload = {"file_path": doc.source_uri, "title": doc.title}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Direct re-ingestion of source type '{doc.source_type}' is not supported.",
        )

    job = Job(
        id=uuid.uuid4(),
        business_id=business.id,
        type=job_type,
        status="pending",
        payload=payload,
        progress=0,
    )
    db.add(job)
    await db.flush()

    return {
        "job_id": str(job.id),
        "status": "pending",
        "message": f"Source '{doc.title}' queued for re-ingestion.",
    }


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: uuid.UUID,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> JobStatusResponse:
    """Check asynchronous background job status, progress, and result."""
    _, business, _, _ = auth_ctx

    stmt = select(Job).where(Job.id == job_id, Job.business_id == business.id)
    job = (await db.execute(stmt)).scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )

    return JobStatusResponse(
        id=job.id,
        type=job.type,
        status=job.status,
        progress=job.progress,
        result=job.result,
        error=job.error,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )
