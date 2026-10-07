from datetime import date

from pydantic import BaseModel, EmailStr, Field

class RecipientIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None
    number: str | None = Field(default=None, max_length=100)

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