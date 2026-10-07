from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.database_url) if settings.database_url else None
session_maker = (
    async_sessionmaker(engine, expire_on_commit=False) if engine is not None else None
)

async def get_db() -> AsyncIterator[AsyncSession]:
    if session_maker is None:
        raise RuntimeError("DATABASE_URL is not configured")

    async with session_maker() as session:
        yield session
