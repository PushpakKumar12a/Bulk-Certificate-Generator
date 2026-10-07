from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Certificate, Job, Recipient

async def add_job(db: AsyncSession, job: Job) -> Job:
    db.add(job)
    await db.commit()

    await db.refresh(job)

    return job

async def get_job(db: AsyncSession, job_id: UUID, owner_id: str) -> Job | None:
    result = await db.scalars(
        select(Job).where(Job.id == job_id, Job.owner_id == owner_id)
    )

    return result.one_or_none()

async def get_recipients(db: AsyncSession, job_id: UUID) -> list[Recipient]:
    result = await db.scalars(
        select(Recipient)
        .options(selectinload(Recipient.certificate))
        .where(Recipient.job_id == job_id)
        .order_by(Recipient.row)
    )

    return list(result)

async def get_certificate(
    db: AsyncSession, job_id: UUID, certificate_id: UUID, owner_id: str
) -> Certificate | None:
    result = await db.scalars(
        select(Certificate)
        .join(Certificate.recipient)
        .where(
            Certificate.id == certificate_id,
            Recipient.job_id == job_id,
            Recipient.job.has(owner_id=owner_id),
        )
    )

    return result.one_or_none()