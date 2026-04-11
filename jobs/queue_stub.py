"""Stub очереди фоновых задач: без Redis/RQ; заменится реальной реализацией позже."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _job_queue_enabled() -> bool:
    v = os.environ.get("JOB_QUEUE_ENABLED", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def enqueue_api_search(search_id: str, product: str, region: str, quantity: str) -> bool:
    """
    Постановка API-поиска в очередь (заглушка).

    При выключенной очереди (по умолчанию) ничего не делает и возвращает False.
    """
    if not _job_queue_enabled():
        return False
    logger.info(
        "Would enqueue api_search job: search_id=%s product=%r region=%r quantity=%r",
        search_id,
        product,
        region,
        quantity,
    )
    return True
