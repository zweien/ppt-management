"""Celery application(ADR-0001 / PRD §17.2)。

worker 分四组:basic / render / mineru / ai。阶段一涉及 basic 与 render。
"""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "ppt_library",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.basic", "app.tasks.render", "app.tasks.mineru", "app.tasks.ai", "app.tasks.export"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=60 * 30,  # 30 min hard
    task_soft_time_limit=60 * 25,
    worker_prefetch_multiplier=1,  # single concurrency per worker (ADR-0005)
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    result_expires=60 * 60 * 24 * 7,
)

# Task routes by queue
celery_app.conf.task_routes = {
    "app.tasks.render.*": {"queue": "render"},
    "app.tasks.basic.*": {"queue": "basic"},
    "app.tasks.mineru.*": {"queue": "mineru"},
    "app.tasks.ai.*": {"queue": "ai"},
}
