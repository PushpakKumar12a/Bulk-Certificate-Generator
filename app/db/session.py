from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

if settings.database_url:
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
else:
    engine = None

if engine is not None:
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
else:
    session_maker = None

async def get_db() -> AsyncIterator[AsyncSession]:
    if session_maker is None:
        raise RuntimeError("DATABASE_URL is not configured")

    async with session_maker() as session:
        yield session