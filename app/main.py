from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import from_url
from sqlalchemy import text

from app.certificates.routes import router as certificates_router
from app.core.config import get_settings
from app.db.session import engine
from app.jobs.routes import router as jobs_router

def make_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title=settings.app_name)

    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=[str(o) for o in settings.cors_origins],
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )

    application.include_router(jobs_router)
    application.include_router(certificates_router)

    @application.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.environment}

    @application.get("/ready", tags=["system"])
    async def ready() -> JSONResponse:
        if not settings.database_url or not settings.redis_url:
            return JSONResponse(
                status_code=503,
                content={"status": "degraded", "database": "not configured", "queue": "not configured"},
            )

        queue = None
        try:
            if engine is None:
                raise RuntimeError("database engine is not configured")
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            queue = from_url(settings.redis_url)
            await queue.ping()
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"status": "degraded", "database": "unavailable", "queue": "unavailable"},
            )
        finally:
            if queue is not None:
                await queue.aclose()

        return JSONResponse(
            status_code=200,
            content={"status": "ready", "database": "available", "queue": "available"},
        )

    return application

app = make_app()