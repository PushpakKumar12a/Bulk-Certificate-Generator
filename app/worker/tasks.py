import asyncio
import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

from celery import Task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.certificates.service import generate
from app.certificates.storage import LocalCertificateStorage
from app.core.config import get_settings
from app.db.models import ItemStatus, Job, JobStatus, Recipient
from app.db.session import session_maker
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

def progress(recipients: Iterable[Recipient]) -> tuple[int, int, int]:
    items = list(recipients)
    done = 0
    success = 0
    failed = 0

    for item in items:
        if item.status in (ItemStatus.COMPLETED, ItemStatus.FAILED):
            done += 1

        if item.status == ItemStatus.COMPLETED:
            success += 1

        if item.status == ItemStatus.FAILED:
            failed += 1

    return done, success, failed

async def process(job_id: UUID) -> None:
    if session_maker is None:
        raise RuntimeError("DATABASE_URL is not configured")

    async with session_maker() as db:
        job = await db.get(Job, job_id)
        if job is None:
            logger.warning("Ignoring missing job %s", job_id)

            return

        try:
            job.status = JobStatus.RUNNING
            job.started_at = job.started_at or datetime.now(UTC)
            await db.commit()
            storage = LocalCertificateStorage(get_settings().storage_path)

            recipients = await db.scalars(
                select(Recipient)
                .where(Recipient.job_id == job_id)
                .order_by(Recipient.row)
            )

            for recipient in recipients:
                if recipient.status == ItemStatus.COMPLETED:
                    continue

                await generate(db, job, recipient, storage)
                await update_progress(db, job)

            await update_progress(db, job)
        except Exception:
            logger.exception("Job %s failed in worker", job_id)
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now(UTC)
            await db.commit()

            raise

async def update_progress(db: AsyncSession, job: Job) -> None:
    recipients = await db.scalars(
        select(Recipient).where(Recipient.job_id == job.id)
    )
    job.done, job.success, job.failed = progress(recipients)

    if job.done == job.total:
        job.status = (
            JobStatus.COMPLETED_WITH_ERRORS
            if job.failed
            else JobStatus.COMPLETED
        )
        job.completed_at = datetime.now(UTC)

    await db.commit()

class JobTask(Task):
    autoretry_for = (ConnectionError,)
    retry_backoff = True
    max_retries = 3

@celery_app.task(bind=True, base=JobTask, name="jobs.process")
def process_job(self: JobTask, job_id: str) -> None:
    asyncio.run(process(UUID(job_id)))