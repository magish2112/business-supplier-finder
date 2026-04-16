"""Persistence for orchestration: user_requests and outbound_email_drafts."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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


def update_user_request_structured(
    db_path: Optional[str],
    request_id: str,
    structured: Dict[str, Any],
    *,
    sync_geo_columns: bool = False,
) -> bool:
    """
    Сохраняет structured_json (объект → JSON-строка). Возвращает True, если строка найдена и обновлена.
    При sync_geo_columns=True дублирует city и activity_direction из structured в колонки user_requests.
    """
    raw = json.dumps(structured, ensure_ascii=False)
    conn = get_connection(db_path)
    try:
        if sync_geo_columns:
            city = structured.get("city")
            act = structured.get("activity_direction")
            city_v = (str(city).strip() if city is not None else "") or None
            act_v = (str(act).strip() if act is not None else "") or None
            cur = conn.execute(
                "UPDATE user_requests SET structured_json = ?, city = ?, activity_direction = ? WHERE id = ?",
                (raw, city_v, act_v, request_id),
            )
        else:
            cur = conn.execute(
                "UPDATE user_requests SET structured_json = ? WHERE id = ?",
                (raw, request_id),
            )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def update_user_request_selected_supplier_ids(
    db_path: Optional[str],
    request_id: str,
    supplier_ids: List[str],
) -> bool:
    """Сохраняет выбранные id поставщиков как JSON-массив в selected_supplier_ids."""
    raw = json.dumps([str(x) for x in supplier_ids if x], ensure_ascii=False)
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "UPDATE user_requests SET selected_supplier_ids = ? WHERE id = ?",
            (raw, request_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def append_clarification(
    db_path: Optional[str],
    request_id: str,
    entry: Dict[str, Any],
) -> None:
    """
    Добавляет запись в clarification_json (массив items), не затирая предыдущие уточнения.
    """
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT clarification_json FROM user_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
        if not row:
            return
        prev_raw = row["clarification_json"]
        data: Dict[str, Any] = {"items": []}
        if prev_raw:
            try:
                parsed = json.loads(prev_raw)
                if isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
                    data = parsed
                elif isinstance(parsed, list):
                    data = {"items": parsed}
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        data.setdefault("items", []).append(entry)
        conn.execute(
            "UPDATE user_requests SET clarification_json = ? WHERE id = ?",
            (json.dumps(data, ensure_ascii=False), request_id),
        )
        conn.commit()
    finally:
        conn.close()


def insert_audit_event(
    db_path: Optional[str],
    *,
    request_id: str,
    event_type: str,
    payload: Optional[Dict[str, Any]] = None,
    event_id: Optional[str] = None,
    created_at: Optional[str] = None,
) -> str:
    """Событие аудита по заявке (P1+); payload сериализуется в JSON."""
    eid = event_id or str(uuid.uuid4())
    ts = created_at or _utc_now_iso()
    payload_json = None if payload is None else json.dumps(payload, ensure_ascii=False)
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO request_audit_events (id, request_id, event_type, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (eid, request_id, event_type, payload_json, ts),
        )
        conn.commit()
    finally:
        conn.close()
    return eid


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
