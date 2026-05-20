from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery = Celery(
    "math_correction",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks", "app.workers.embed_tasks"],
)

celery.conf.update(
    task_track_started=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Ensure task modules are imported so tasks are registered.
import app.workers.embed_tasks  # noqa: E402,F401
import app.workers.tasks  # noqa: E402,F401
