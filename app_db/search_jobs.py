"""Фоновые задачи REST /api/v1/search — персистентность в SQLite (A3)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app_db.connection import get_connection

# Дублирует app_db/schema.sql — для БД, созданных до появления таблицы
_ENSURE_SQL = """
CREATE TABLE IF NOT EXISTS api_search_jobs (
    search_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    product TEXT NOT NULL,
    region TEXT NOT NULL,
    quantity TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    error_message TEXT,
    result_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_api_search_jobs_status ON api_search_jobs (status);
"""


def ensure_search_jobs_table(db_path: Optional[str] = None) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(_ENSURE_SQL)
        conn.commit()
    finally:
        conn.close()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class SearchJobRepository:
    def __init__(self, db_path: Optional[str] = None):
        self._conn = get_connection(db_path)
        self._own = True

    def close(self) -> None:
        if self._own and self._conn is not None:
            self._conn.close()
            self._conn = None

    def create_job(self, search_id: str, product: str, region: str, quantity: str) -> None:
        self._conn.execute(
            """
            INSERT INTO api_search_jobs (
                search_id, status, product, region, quantity, started_at
            ) VALUES (?, 'in_progress', ?, ?, ?, ?)
            """,
            (search_id, product, region, quantity or "", _utc_now_iso()),
        )
        self._conn.commit()

    def mark_completed(self, search_id: str, payload: Dict[str, Any]) -> None:
        self._conn.execute(
            """
            UPDATE api_search_jobs
            SET status = 'completed',
                completed_at = ?,
                error_message = NULL,
                result_json = ?
            WHERE search_id = ?
            """,
            (_utc_now_iso(), json.dumps(payload, ensure_ascii=False), search_id),
        )
        self._conn.commit()

    def mark_failed(self, search_id: str, error_message: str) -> None:
        self._conn.execute(
            """
            UPDATE api_search_jobs
            SET status = 'failed',
                completed_at = ?,
                error_message = ?
            WHERE search_id = ?
            """,
            (_utc_now_iso(), error_message[:4000], search_id),
        )
        self._conn.commit()

    def get(self, search_id: str) -> Optional[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM api_search_jobs WHERE search_id = ?", (search_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("result_json"):
            try:
                d["_result"] = json.loads(d["result_json"])
            except json.JSONDecodeError:
                d["_result"] = None
        return d

    def counts_by_status(self) -> Dict[str, int]:
        cur = self._conn.execute(
            "SELECT status, COUNT(*) AS c FROM api_search_jobs GROUP BY status"
        )
        out: Dict[str, int] = {}
        for row in cur.fetchall():
            out[row["status"]] = row["c"]
        return out
