from celery import Celery

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery(
    "bulk_certificate_generator",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.worker_concurrency = settings.worker_concurrency