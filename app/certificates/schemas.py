from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

class CertificateVerifyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    valid: bool = True
    certificate_id: UUID
    recipient_name: str
    course: str
    org: str
    issue_date: date
    issued_at: datetime
