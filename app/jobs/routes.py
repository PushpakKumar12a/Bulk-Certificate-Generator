from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Job, Recipient
from app.db.session import get_db
from app.jobs.csv import read_csv
from app.jobs.schemas import JobIn, JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.post("", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    title: str = Form(...),
    course: str = Form(...),
    org: str = Form(...),
    issue_date: date = Form(...),
    recipients_file: UploadFile = File(...),
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

    job = Job(
        title=meta.title,
        course=meta.course,
        org=meta.org,
        issue_date=meta.issue_date,
        total=len(rows),
    )
    job.recipients = [
        Recipient(
            row=line,
            name=item.name,
            email=str(item.email) if item.email else None,
            number=item.number,
        )
        for line, item in rows
    ]
    db.add(job)
    await db.commit()
    await db.refresh(job)

    return JobOut(
        job_id=str(job.id),
        status=job.status.value,
        total=job.total,
        status_url=f"/jobs/{job.id}",
    )