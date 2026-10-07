from fastapi import FastAPI

from app.core.config import get_settings
from app.jobs.routes import router as jobs_router

def make_app() -> FastAPI:

    settings = get_settings()
    application = FastAPI(title=settings.app_name)
    application.include_router(jobs_router)

    @application.get("/health", tags=["system"])
    def health() -> dict[str, str]:

        return {"status": "ok", "environment": settings.environment}

    return application

app = make_app()