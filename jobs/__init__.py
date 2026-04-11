"""Фоновые задачи API-поиска: опционально RQ (см. jobs.queue_stub)."""

from jobs.queue_stub import enqueue_api_search

__all__ = ["enqueue_api_search"]
