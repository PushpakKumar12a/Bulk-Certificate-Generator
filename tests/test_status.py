from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.db.models import ItemStatus, Job, JobStatus, Recipient
from app.jobs.status import JobStatusOut, RecipientResult
from app.worker.celery_app import celery_app
from app.worker.tasks import BatchRetryError, JobTask, progress, update_progress

def test_progress_counts() -> None:
    recipients = [
        Recipient(status=ItemStatus.COMPLETED),
        Recipient(status=ItemStatus.FAILED),
        Recipient(status=ItemStatus.PENDING),
    ]

    assert progress(recipients) == (2, 1, 1)

def test_status_results() -> None:
    job_id = uuid4()
    certificate_id = uuid4()
    result = JobStatusOut(
        job_id=job_id,
        status=JobStatus.COMPLETED_WITH_ERRORS,
        total=2,
        done=2,
        success=1,
        failed=1,
        results=[
            RecipientResult(
                row=2,
                name="Sonu",
                status="completed",
                certificate_id=certificate_id,
            ),
            RecipientResult(
                row=3,
                name="Ben",
                status="failed",
                error="render failed",
            ),
        ],
    )

    assert result.model_dump()["failed"] == 1
    assert result.results[0].certificate_id == certificate_id

def test_celery_retry_config() -> None:
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True
    assert BatchRetryError in JobTask.autoretry_for
    assert ConnectionError in JobTask.autoretry_for
    assert JobTask.max_retries == 3
    assert JobTask.retry_backoff is True

@pytest.mark.asyncio
async def test_update_progress_retry() -> None:
    job = Job(
        title="Test",
        course="Test Course",
        org="Test Org",
        issue_date=None,
        total=2,
        done=0,
        success=0,
        failed=0,
    )
    recipients = [
        Recipient(status=ItemStatus.COMPLETED),
        Recipient(status=ItemStatus.FAILED),
    ]

    mock_db = MagicMock()
    mock_db.scalars = AsyncMock(return_value=recipients)
    mock_db.commit = AsyncMock()

    await update_progress(mock_db, job, can_retry=True)
    assert job.done == 2
    assert job.success == 1
    assert job.failed == 1
    assert job.status == JobStatus.RUNNING

    await update_progress(mock_db, job, can_retry=False)
    assert job.status == JobStatus.COMPLETED_WITH_ERRORS
    assert job.completed_at is not None

@pytest.mark.asyncio
async def test_process_retry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from contextlib import asynccontextmanager
    from app.worker.tasks import process

    job_id = uuid4()
    job = Job(
        id=job_id,
        title="Test",
        course="Test Course",
        org="Test Org",
        issue_date=None,
        total=1,
        done=0,
        success=0,
        failed=0,
    )
    recipient = Recipient(
        id=uuid4(),
        job_id=job_id,
        row=1,
        name="Test User",
        status=ItemStatus.PENDING,
    )

    mock_db = MagicMock()
    mock_db.get = AsyncMock(return_value=job)
    mock_db.scalars = AsyncMock(side_effect=[
        [recipient],
        [recipient],
    ])
    mock_db.commit = AsyncMock()

    async def mock_generate(db, job, rec, storage):
        rec.status = ItemStatus.FAILED
        rec.error = "Simulated render failure"
        return None

    monkeypatch.setattr("app.worker.tasks.generate", mock_generate)
    monkeypatch.setattr("app.worker.tasks.get_settings", lambda: MagicMock(storage_path=tmp_path))

    @asynccontextmanager
    async def mock_session():
        yield mock_db

    monkeypatch.setattr("app.worker.tasks.session_maker", mock_session)

    with pytest.raises(BatchRetryError):
        await process(job_id, current_retry=0, max_retries=3)

    mock_db.scalars = AsyncMock(side_effect=[
        [recipient],
        [recipient],
    ])
    await process(job_id, current_retry=3, max_retries=3)
    assert job.status == JobStatus.COMPLETED_WITH_ERRORS

