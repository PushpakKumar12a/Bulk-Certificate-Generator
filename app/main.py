from fastapi import FastAPI
from app.config import get_settings

def make_app() -> FastAPI:

    settings = get_settings()
    application = FastAPI(title=settings.app_name)

    @application.get("/health", tags=["system"])
    def health() -> dict[str, str]:

        return {"status": "ok", "environment": settings.environment}

    return application


app = make_app()
