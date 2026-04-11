"""CLI: RQ worker для очереди API-поиска."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    url = (os.getenv("REDIS_URL") or "").strip()
    if not url:
        raise SystemExit("REDIS_URL is required to run the RQ worker")

    from redis import Redis
    from rq import Worker

    from jobs.queue_stub import QUEUE_NAME

    redis_conn = Redis.from_url(url)
    Worker([QUEUE_NAME], connection=redis_conn).work()
