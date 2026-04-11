"""Очередь фоновых задач API-поиска: по умолчанию поток; опционально Redis RQ."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# Имя очереди RQ (worker: python -m jobs.worker из корня проекта)
QUEUE_NAME = "bizsf"


def _job_queue_enabled() -> bool:
    v = os.environ.get("JOB_QUEUE_ENABLED", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _redis_url() -> str:
    return (os.environ.get("REDIS_URL") or "").strip()


def enqueue_api_search(search_id: str, product: str, region: str, quantity: str) -> bool:
    """
    Постановка API-поиска в RQ при JOB_QUEUE_ENABLED и REDIS_URL.

    Возвращает True только если задача реально поставлена в Redis; иначе False
    (веб-приложение запускает прежний daemon thread).
    """
    if not _job_queue_enabled():
        return False

    url = _redis_url()
    if not url:
        logger.info(
            "JOB_QUEUE_ENABLED set but REDIS_URL empty; api_search will use in-process thread. "
            "search_id=%s",
            search_id,
        )
        return False

    try:
        from redis import Redis
        from rq import Queue
    except ImportError as e:
        logger.error(
            "JOB_QUEUE_ENABLED and REDIS_URL set but rq/redis are not installed (%s). "
            "Falling back to thread. search_id=%s",
            e,
            search_id,
        )
        return False

    try:
        from jobs.tasks import run_api_search_job

        conn = Redis.from_url(url)
        q = Queue(QUEUE_NAME, connection=conn)
        q.enqueue(run_api_search_job, search_id, product, region, quantity or "")
        logger.info(
            "Enqueued api_search job queue=%s search_id=%s",
            QUEUE_NAME,
            search_id,
        )
        return True
    except Exception as e:
        logger.error(
            "Failed to enqueue api_search search_id=%s: %s. Falling back to thread.",
            search_id,
            e,
            exc_info=True,
        )
        return False
