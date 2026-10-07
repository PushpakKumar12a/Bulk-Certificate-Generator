import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.certificates.storage import CertificateStorage
from app.certificates.template import certificate_pdf
from app.db.models import Certificate, ItemStatus, Job, Recipient

logger = logging.getLogger(__name__)

def certificate_storage_key(job_id: UUID, certificate_id: UUID) -> str:
    return f"certificates/{job_id}/{certificate_id}.pdf"

async def generate(
    db: AsyncSession,
    job: Job,
    recipient: Recipient,
    storage: CertificateStorage,
) -> Certificate | None:
    """Generate one recipient independently and persist its terminal result."""
    recipient.status = ItemStatus.PROCESSING
    await db.commit()

    certificate_id = Certificate.__table__.c.id.default.arg()
    key = certificate_storage_key(job.id, certificate_id)
    try:
        content = certificate_pdf(
            name=recipient.name,
            course=job.course,
            org=job.org,
            issue_date=job.issue_date,
            number=recipient.number,
        )
        storage.save(key, content)
        certificate = Certificate(
            id=certificate_id,
            recipient_id=recipient.id,
            file_path=key,
        )
        db.add(certificate)
        recipient.status = ItemStatus.COMPLETED
        recipient.error = None
        await db.commit()
        return certificate
    except Exception as exc:
        logger.exception("Certificate generation failed for recipient %s", recipient.id)
        recipient.status = ItemStatus.FAILED
        recipient.error = str(exc)[:2000]
        await db.commit()
        return None

def finish_job(job: Job) -> None:
    job.done = sum(
        recipient.status in (ItemStatus.COMPLETED, ItemStatus.FAILED)
        for recipient in job.recipients
    )
    job.success = sum(
        recipient.status == ItemStatus.COMPLETED for recipient in job.recipients
    )
    job.failed = sum(
        recipient.status == ItemStatus.FAILED for recipient in job.recipients
    )
    if job.done == job.total:
        job.completed_at = datetime.now(UTC)
