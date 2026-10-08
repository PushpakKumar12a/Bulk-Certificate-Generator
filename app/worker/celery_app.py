from celery import Celery

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery(
    "bulk_certificate_generator",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=5,
)
