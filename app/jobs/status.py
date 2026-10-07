from uuid import UUID

from pydantic import BaseModel

from app.db.models import JobStatus

class RecipientResult(BaseModel):
    row: int
    name: str
    status: str
    error: str | None = None
    certificate_id: UUID | None = None

class JobStatusOut(BaseModel):
    job_id: UUID
    status: JobStatus
    total: int
    done: int
    success: int
    failed: int
    results: list[RecipientResult]
