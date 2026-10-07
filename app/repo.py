from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job, Recipient

async def add_job(db: AsyncSession, job: Job) -> Job:
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job

async def get_job(db: AsyncSession, job_id: UUID) -> Job | None:
    return await db.get(Job, job_id)

async def get_recipients(db: AsyncSession, job_id: UUID) -> list[Recipient]:
    result = await db.scalars(
        select(Recipient).where(Recipient.job_id == job_id).order_by(Recipient.row)
    )
    return list(result)
