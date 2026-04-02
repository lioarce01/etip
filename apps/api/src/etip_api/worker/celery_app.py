from celery import Celery
from etip_core.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "etip",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["etip_api.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)
