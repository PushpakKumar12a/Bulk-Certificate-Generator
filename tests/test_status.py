from uuid import uuid4

from app.db.models import ItemStatus, JobStatus, Recipient
from app.jobs.status import JobStatusOut, RecipientResult
from app.worker.tasks import progress

def test_progress_counts_partial_failures() -> None:
    recipients = [
        Recipient(status=ItemStatus.COMPLETED),
        Recipient(status=ItemStatus.FAILED),
        Recipient(status=ItemStatus.PENDING),
    ]

    assert progress(recipients) == (2, 1, 1)

def test_status_contains_progress_and_results() -> None:
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
