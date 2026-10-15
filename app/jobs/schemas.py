from datetime import date
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field
from app.db.models import JobStatus

class RecipientIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None

class JobIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    course: str = Field(min_length=1, max_length=200)
    org: str = Field(min_length=1, max_length=200)
    issue_date: date

class JobOut(BaseModel):
    job_id: str
    status: str
    total: int
    status_url: str

class RecipientResult(BaseModel):
    row: int
    name: str
    status: str
    error: str | None = None
    certificate_id: UUID | None = None
    download_url: str | None = None
    verification_url: str | None = None

class JobStatusOut(BaseModel):
    job_id: UUID
    status: JobStatus
    total: int
    done: int
    success: int
    failed: int
    results: list[RecipientResult]