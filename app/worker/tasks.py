import asyncio
import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

from celery import Task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.certificates.service import generate
from app.certificates.storage import CertificateStorage
from app.core.config import get_settings
from app.db.models import ItemStatus, Job, JobStatus, Recipient
from app.db.session import session_maker
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

def progress(recipients: Iterable[Recipient]) -> tuple[int, int, int]:
    done = success = failed = 0
    for item in recipients:
        if item.status == ItemStatus.COMPLETED:
            done += 1
            success += 1
        elif item.status == ItemStatus.FAILED:
            done += 1
            failed += 1
    return done, success, failed

class BatchRetryError(Exception):
    pass

async def process(
    job_id: UUID,
    current_retry: int = 0,
    max_retries: int = 3,
) -> None:
    if session_maker is None:
        raise RuntimeError("DATABASE_URL is not configured")

    async with session_maker() as db:
        job = await db.get(Job, job_id)
        if job is None:
            logger.warning("Ignoring missing job %s", job_id)

            return

        can_retry = current_retry < max_retries

        try:
            job.status = JobStatus.RUNNING
            job.started_at = job.started_at or datetime.now(UTC)
            await db.commit()
            storage = CertificateStorage(get_settings().storage_path)

            recipients = list(
                await db.scalars(
                    select(Recipient)
                    .options(selectinload(Recipient.certificate))
                    .where(Recipient.job_id == job_id)
                    .order_by(Recipient.row)
                )
            )

            for idx, recipient in enumerate(recipients, 1):
                if recipient.status == ItemStatus.COMPLETED:
                    continue

                await generate(db, job, recipient, storage)
                if idx % 10 == 0:
                    await update_progress(db, job, can_retry=can_retry)

            await update_progress(db, job, can_retry=can_retry)

            if job.failed > 0 and can_retry:
                logger.warning(
                    "Job %s has %d failed recipient(s) on attempt %d/%d; scheduling Celery auto-retry",
                    job_id,
                    job.failed,
                    current_retry + 1,
                    max_retries + 1,
                )
                raise BatchRetryError(
                    f"Job {job_id} has {job.failed} failed recipient(s) on attempt {current_retry + 1}"
                )

        except BatchRetryError:
            raise
        except Exception:
            logger.exception("Job %s encountered unexpected worker error", job_id)
            if not can_retry:
                job.status = JobStatus.FAILED
                job.completed_at = datetime.now(UTC)
                await db.commit()

            raise

async def update_progress(
    db: AsyncSession,
    job: Job,
    can_retry: bool = False,
) -> None:
    recipients = list(
        await db.scalars(select(Recipient).where(Recipient.job_id == job.id))
    )
    job.done, job.success, job.failed = progress(recipients)

    if job.done == job.total:
        if job.failed == 0:
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(UTC)
        elif not can_retry:
            job.status = JobStatus.COMPLETED_WITH_ERRORS
            job.completed_at = datetime.now(UTC)
        else:
            job.status = JobStatus.RUNNING

    await db.commit()

class JobTask(Task):
    autoretry_for = (ConnectionError, OSError, BatchRetryError)
    retry_backoff = True
    retry_backoff_max = 60
    max_retries = 3
    retry_jitter = True

@celery_app.task(bind=True, base=JobTask, name="jobs.process")
def process_job(self: JobTask, job_id: str) -> None:
    asyncio.run(
        process(
            UUID(job_id),
            current_retry=self.request.retries,
            max_retries=self.max_retries,
        )
    )
