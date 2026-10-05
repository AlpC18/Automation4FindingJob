"""
Celery Application and Configuration
Connects to Redis message broker for distributed task queue processing.
"""

import os
from celery import Celery
from backend.app.core.config import settings
from backend.app.core.monitoring import initialize_error_monitoring

initialize_error_monitoring()

broker_url = settings.REDIS_URL or "redis://localhost:6379/0"
result_backend = settings.REDIS_URL or "redis://localhost:6379/0"

celery_app = Celery(
    "career_engine",
    broker=broker_url,
    backend=result_backend,
    include=["backend.app.tasks.worker_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_delivery_mode="persistent",
    task_time_limit=600,       # 10 minutes max per task
    task_soft_time_limit=540,
    broker_connection_retry_on_startup=True
)

def check_redis_connection() -> bool:
    """Checks if Redis broker is reachable without throwing unhandled exceptions."""
    try:
        import redis
        r = redis.from_url(broker_url, socket_connect_timeout=1.5)
        return r.ping()
    except Exception:
        return False
