from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from fastapi.responses import JSONResponse
from sqlalchemy import text
from redis.asyncio import from_url

from app.core.config import get_settings
from app.core.limits import check_rate
from app.core.observability import configure_logging, metrics, observe
from app.db.session import engine
from app.jobs.routes import router as jobs_router
from app.certificates.routes import router as certificates_router

def make_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    application = FastAPI(title=settings.app_name)
    application.middleware("http")(observe)

    if settings.environment == "production":
        application.add_middleware(HTTPSRedirectMiddleware)

    @application.middleware("http")
    async def rate_limit(request: Request, call_next) -> Response:
        await check_rate(request)

        return await call_next(request)

    cors_origins = []

    for origin in settings.cors_origins:
        cors_origins.append(str(origin))

    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-API-Key"],
    )

    async def security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    application.add_middleware(BaseHTTPMiddleware, dispatch=security_headers)
    application.include_router(jobs_router)
    application.include_router(certificates_router)

    @application.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.environment}

    @application.get("/ready", tags=["system"])
    async def ready() -> Response:
        if not settings.database_url or not settings.redis_url:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "degraded",
                    "database": "not configured",
                    "queue": "not configured",
                },
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
                content={
                    "status": "degraded",
                    "database": "unavailable",
                    "queue": "unavailable",
                },
            )
        finally:
            if queue is not None:
                await queue.aclose()

        return JSONResponse(
            status_code=200,
            content={
                "status": "ready",
                "database": "available",
                "queue": "available",
            },
        )

    @application.get("/metrics", tags=["system"])
    def application_metrics() -> dict[str, dict[str, int]]:
        return metrics()

    return application

app = make_app()