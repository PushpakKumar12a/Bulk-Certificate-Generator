from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Certificate, Job, Recipient

async def get_job(db: AsyncSession, job_id: UUID) -> Job | None:
    result = await db.scalars(select(Job).where(Job.id == job_id))
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
    db: AsyncSession, job_id: UUID, certificate_id: UUID
) -> Certificate | None:
    query = (
        select(Certificate)
        .options(
            selectinload(Certificate.recipient).selectinload(Recipient.job)
        )
        .join(Certificate.recipient)
        .where(
            Certificate.id == certificate_id,
            Recipient.job_id == job_id,
        )
    )
    result = await db.scalars(query)
    return result.one_or_none()

async def get_certificate_by_id(
    db: AsyncSession, certificate_id: UUID
) -> Certificate | None:
    query = (
        select(Certificate)
        .options(
            selectinload(Certificate.recipient).selectinload(Recipient.job)
        )
        .where(Certificate.id == certificate_id)
    )
    result = await db.scalars(query)
    return result.one_or_none()