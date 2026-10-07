from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.auth import Identity, require_scope
from app.db.models import Job, JobStatus, Recipient
from app.db.repo import get_job, get_recipients
from app.db.session import get_db
from app.jobs.csv import read_csv
from app.jobs.schemas import JobIn, JobOut
from app.jobs.status import JobStatusOut, RecipientResult
from app.worker.tasks import process_job

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.post("", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    title: str = Form(...),
    course: str = Form(...),
    org: str = Form(...),
    issue_date: date = Form(...),
    recipients_file: UploadFile = File(...),
    identity: Identity = Depends(require_scope("jobs:write")),
    db: AsyncSession = Depends(get_db),
) -> JobOut:
    settings = get_settings()
    if not recipients_file.filename or not recipients_file.filename.lower().endswith(
        ".csv"
    ):
        raise HTTPException(status_code=400, detail="recipients_file must be a CSV file")

    data = await recipients_file.read(settings.max_csv_bytes + 1)

    if len(data) > settings.max_csv_bytes:
        raise HTTPException(status_code=413, detail="CSV file is too large")

    try:
        meta = JobIn(
            title=title.strip(),
            course=course.strip(),
            org=org.strip(),
            issue_date=issue_date,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    try:
        rows = read_csv(data, settings.max_rows)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    count = await db.scalar(
        select(func.count())
        .select_from(Job)
        .where(
            Job.owner_id == identity.user_id,
            Job.status.in_((JobStatus.QUEUED, JobStatus.RUNNING)),
        )
    )

    if count >= settings.max_jobs_per_user:
        raise HTTPException(status_code=429, detail="job quota exceeded")

    job = Job(
        owner_id=identity.user_id,
        title=meta.title,
        course=meta.course,
        org=meta.org,
        issue_date=meta.issue_date,
        total=len(rows),
    )
    recipients = []
    for line, item in rows:
        if item.email:
            email = str(item.email)
        else:
            email = None
        recipient = Recipient(
            row=line,
            name=item.name,
            email=email,
            number=item.number,
        )
        recipients.append(recipient)

    job.recipients = recipients
    db.add(job)
    await db.commit()
    await db.refresh(job)
    try:
        process_job.delay(str(job.id))
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.completed_at = datetime.now(UTC)
        await db.commit()
        raise HTTPException(
            status_code=503,
            detail="job queue is unavailable",
        ) from exc

    return JobOut(
        job_id=str(job.id),
        status=job.status.value,
        total=job.total,
        status_url=f"/jobs/{job.id}",
    )

@router.get("/{job_id}", response_model=JobStatusOut)
async def job_status(
    job_id: UUID,
    identity: Identity = Depends(require_scope("jobs:read")),
    db: AsyncSession = Depends(get_db),
) -> JobStatusOut:
    job = await get_job(db, job_id, identity.user_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    recipients = await get_recipients(db, job_id)
    results = []

    for item in recipients:
        if item.certificate:
            certificate_id = item.certificate.id
        else:
            certificate_id = None
        result = RecipientResult(
            row=item.row,
            name=item.name,
            status=item.status.value,
            error=item.error,
            certificate_id=certificate_id,
        )
        results.append(result)

    return JobStatusOut(
        job_id=job.id,
        status=job.status,
        total=job.total,
        done=job.done,
        success=job.success,
        failed=job.failed,
        results=results,
    )