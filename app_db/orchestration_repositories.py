"""Persistence for orchestration: user_requests and outbound_email_drafts."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from app_db.connection import get_connection


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def insert_user_request(
    db_path: Optional[str],
    *,
    request_id: str,
    raw_query: str,
    city: Optional[str],
    activity_direction: Optional[str],
    status: str,
    structured_json: Optional[str] = None,
    created_at: Optional[str] = None,
) -> None:
    """Insert a row into user_requests (matches schema.sql types)."""
    ts = created_at or _utc_now_iso()
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO user_requests (
                id, raw_query, structured_json, city, activity_direction, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                raw_query,
                structured_json,
                city,
                activity_direction,
                status,
                ts,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def update_user_request_status(db_path: Optional[str], request_id: str, status: str) -> None:
    """Set user_requests.status for an existing row."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE user_requests SET status = ? WHERE id = ?",
            (status, request_id),
        )
        conn.commit()
    finally:
        conn.close()


def insert_outbound_email_drafts(
    db_path: Optional[str],
    *,
    request_id: str,
    recipients: List[str],
    subject: str,
    body: str,
    created_at: Optional[str] = None,
) -> None:
    """One outbound_email_drafts row per recipient; user_confirmed=0, sent_at NULL."""
    ts = created_at or _utc_now_iso()
    conn = get_connection(db_path)
    try:
        for addr in recipients:
            if not addr or not str(addr).strip():
                continue
            conn.execute(
                """
                INSERT INTO outbound_email_drafts (
                    id, request_id, recipient, subject, body, user_confirmed, sent_at, created_at
                ) VALUES (?, ?, ?, ?, ?, 0, NULL, ?)
                """,
                (str(uuid.uuid4()), request_id, str(addr).strip(), subject, body, ts),
            )
        conn.commit()
    finally:
        conn.close()


def mark_outbound_email_drafts_sent(
    db_path: Optional[str],
    *,
    request_id: str,
    sent_at_iso: str,
) -> None:
    """Set sent_at on all drafts for this request that are not yet marked sent."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            UPDATE outbound_email_drafts
            SET sent_at = ?
            WHERE request_id = ? AND sent_at IS NULL
            """,
            (sent_at_iso, request_id),
        )
        conn.commit()
    finally:
        conn.close()
