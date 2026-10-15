from contextlib import asynccontextmanager
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.certificates.routes import router as certificates_router
from app.core.config import get_settings
from app.db.models import Base
from app.db.session import engine
from app.jobs.routes import router as jobs_router
from app.queue.client import get_queue_client

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(application: FastAPI):
    if engine is not None:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables verified and created successfully.")
        except Exception as exc:
            logger.error(f"Failed to initialize database tables: {exc}")
    yield

def make_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title=settings.app_name, lifespan=lifespan)

    origins = settings.cors_origins if settings.cors_origins else ["*"]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    application.include_router(jobs_router)
    application.include_router(certificates_router)

    @application.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.environment}

    @application.get("/ready", tags=["system"])
    async def ready() -> JSONResponse:
        db_status = "unavailable"
        queue_status = "unavailable"

        if not settings.database_url:
            db_status = "not configured"
        elif engine is not None:
            try:
                async with engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
                db_status = "available"
            except Exception:
                pass

        try:
            if get_queue_client(settings).ping():
                queue_status = "available"
        except Exception:
            pass

        is_ready = db_status == "available" and queue_status == "available"
        return JSONResponse(
            status_code=200 if is_ready else 503,
            content={
                "status": "ready" if is_ready else "degraded",
                "database": db_status,
                "queue": queue_status,
            },
        )

    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    if not frontend_dir.exists():
        frontend_dir = Path("/app/frontend")

    if frontend_dir.exists() and (frontend_dir / "index.html").exists():
        application.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    return application

app = make_app()