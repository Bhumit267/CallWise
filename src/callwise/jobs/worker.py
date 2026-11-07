"""Asynchronous background worker for processing document/URL ingestion and retention jobs."""

import asyncio
from datetime import datetime, timedelta, timezone
import logging
from typing import Optional
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from callwise.db.models import Business, Call, CallTurn, Job
from callwise.db.session import AsyncSessionLocal
from callwise.knowledge.ingest import ingest_file, ingest_url

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(timezone.utc)


async def execute_job(job: Job, session: AsyncSession) -> None:
    """Execute a single job payload and update progress and results."""
    logger.info(f"Processing job {job.id} (type: {job.type}, business: {job.business_id})")

    if job.type == "document_ingestion":
        file_path = job.payload.get("file_path")
        title = job.payload.get("title")
        if not file_path:
            raise ValueError("Missing 'file_path' in document_ingestion payload.")

        job.progress = 30
        await session.flush()

        # Ingest file (extracts text, chunks, embeds, and persists)
        doc = ingest_file(job.business_id, file_path, title=title)

        job.progress = 100
        job.result = {
            "document_id": str(doc.id),
            "title": doc.title,
            "source_type": doc.source_type,
        }

    elif job.type == "url_ingestion":
        url = job.payload.get("url")
        title = job.payload.get("title")
        if not url:
            raise ValueError("Missing 'url' in url_ingestion payload.")

        job.progress = 30
        await session.flush()

        # Ingest URL (validates SSRF, scrapes, chunks, embeds, and persists)
        doc = ingest_url(job.business_id, url, title=title)

        job.progress = 100
        job.result = {
            "document_id": str(doc.id),
            "title": doc.title,
            "source_type": doc.source_type,
        }

    elif job.type == "retention_cleanup":
        # Execute data retention cleanup for businesses
        job.progress = 20
        await session.flush()

        biz = (await session.execute(select(Business).where(Business.id == job.business_id))).scalar_one_or_none()
        retention_days = biz.retention_days if biz and biz.retention_days else 90
        cutoff = utc_now() - timedelta(days=retention_days)

        # Delete expired call turns (transcripts)
        expired_calls_stmt = select(Call.id).where(
            Call.business_id == job.business_id,
            Call.started_at < cutoff,
        )
        expired_call_ids = (await session.execute(expired_calls_stmt)).scalars().all()

        deleted_turns = 0
        if expired_call_ids:
            del_turns_stmt = delete(CallTurn).where(CallTurn.call_id.in_(expired_call_ids))
            res = await session.execute(del_turns_stmt)
            deleted_turns = res.rowcount

        job.progress = 100
        job.result = {
            "retention_days": retention_days,
            "cutoff": cutoff.isoformat(),
            "expired_calls_affected": len(expired_call_ids),
            "deleted_turns_count": deleted_turns,
        }

    else:
        raise ValueError(f"Unsupported job type: '{job.type}'")


async def process_next_job(session: AsyncSession) -> Optional[Job]:
    """
    Acquire and execute the next pending job using SKIP LOCKED to safely allow
    concurrent worker instances.
    """
    # Fetch next pending job and lock row
    stmt = (
        select(Job)
        .where(Job.status == "pending")
        .order_by(Job.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = (await session.execute(stmt)).scalar_one_or_none()
    if not job:
        return None

    job.status = "in_progress"
    job.started_at = utc_now()
    job.progress = 10
    await session.commit()

    try:
        await execute_job(job, session)
        job.status = "completed"
        job.completed_at = utc_now()
        job.error = None
        await session.commit()
        logger.info(f"Job {job.id} completed successfully.")
    except Exception as exc:
        logger.exception(f"Job {job.id} failed with error: {exc}")
        job.status = "failed"
        job.error = str(exc)
        job.progress = 0
        job.completed_at = utc_now()
        await session.commit()

    return job


async def run_worker(poll_interval: int = 5, run_once: bool = False) -> None:
    """Main worker daemon polling loop."""
    logger.info(f"Starting Callwise Background Worker (poll_interval={poll_interval}s, run_once={run_once})...")

    while True:
        try:
            async with AsyncSessionLocal() as session:
                job = await process_next_job(session)
                if run_once:
                    break
                if not job:
                    # No pending job found, sleep before next poll
                    await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            logger.info("Worker daemon cancelled.")
            break
        except Exception as exc:
            logger.error(f"Worker iteration encountered an unexpected error: {exc}")
            if run_once:
                break
            await asyncio.sleep(poll_interval)

