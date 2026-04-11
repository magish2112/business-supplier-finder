"""Repositories for SQLite-backed orchestration entities."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app_db.connection import get_connection


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_field(value: Optional[str]) -> str:
    if value is None:
        return ""
    return value.strip().lower()


def _row_to_dict(row) -> Dict[str, Any]:
    return dict(row)


def _inn_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


SUPPLIER_COLUMNS = (
    "id",
    "name",
    "inn",
    "city",
    "activity_direction",
    "website_url",
    "email",
    "phone",
    "source",
    "verification_status",
    "notes_json",
    "created_at",
    "updated_at",
)


class SupplierRepository:
    def __init__(self, conn=None, db_path: Optional[str] = None):
        self._own_conn = conn is None
        self._conn = conn if conn is not None else get_connection(db_path)

    def close(self) -> None:
        if self._own_conn and self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "SupplierRepository":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def get_by_id(self, supplier_id: str) -> Optional[Dict[str, Any]]:
        cur = self._conn.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,))
        row = cur.fetchone()
        return _row_to_dict(row) if row else None

    def get_by_inn(self, inn: str) -> Optional[Dict[str, Any]]:
        if inn is None or inn.strip() == "":
            return None
        cur = self._conn.execute("SELECT * FROM suppliers WHERE inn = ?", (inn.strip(),))
        row = cur.fetchone()
        return _row_to_dict(row) if row else None

    def create(self, data: Dict[str, Any]) -> str:
        now = _utc_now_iso()
        supplier_id = data.get("id") or str(uuid.uuid4())
        row = {
            "id": supplier_id,
            "name": data["name"],
            "inn": _inn_or_none(data.get("inn")),
            "city": data.get("city"),
            "activity_direction": data.get("activity_direction"),
            "website_url": data.get("website_url"),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "source": data.get("source"),
            "verification_status": data.get("verification_status"),
            "notes_json": data.get("notes_json"),
            "created_at": data.get("created_at", now),
            "updated_at": data.get("updated_at", now),
        }
        if row["notes_json"] is not None and not isinstance(row["notes_json"], str):
            row["notes_json"] = json.dumps(row["notes_json"], ensure_ascii=False)
        self._conn.execute(
            """
            INSERT INTO suppliers (
                id, name, inn, city, activity_direction, website_url, email, phone,
                source, verification_status, notes_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                row["name"],
                row["inn"],
                row["city"],
                row["activity_direction"],
                row["website_url"],
                row["email"],
                row["phone"],
                row["source"],
                row["verification_status"],
                row["notes_json"],
                row["created_at"],
                row["updated_at"],
            ),
        )
        self._conn.commit()
        return supplier_id

    def update(self, supplier_id: str, data: Dict[str, Any]) -> bool:
        existing = self.get_by_id(supplier_id)
        if not existing:
            return False
        now = _utc_now_iso()
        merged = {**existing, **{k: v for k, v in data.items() if k in SUPPLIER_COLUMNS}}
        merged["id"] = supplier_id
        merged["created_at"] = existing["created_at"]
        merged["updated_at"] = data.get("updated_at", now)
        if "inn" in data:
            merged["inn"] = _inn_or_none(data.get("inn"))
        if "notes_json" in data and data["notes_json"] is not None and not isinstance(data["notes_json"], str):
            merged["notes_json"] = json.dumps(data["notes_json"], ensure_ascii=False)
        self._conn.execute(
            """
            UPDATE suppliers SET
                name = ?, inn = ?, city = ?, activity_direction = ?, website_url = ?,
                email = ?, phone = ?, source = ?, verification_status = ?, notes_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                merged["name"],
                merged["inn"],
                merged["city"],
                merged["activity_direction"],
                merged["website_url"],
                merged["email"],
                merged["phone"],
                merged["source"],
                merged["verification_status"],
                merged["notes_json"],
                merged["updated_at"],
                supplier_id,
            ),
        )
        self._conn.commit()
        return True

    def delete(self, supplier_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def list_all(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        q = "SELECT * FROM suppliers ORDER BY updated_at DESC"
        params: tuple = ()
        if limit is not None:
            q += " LIMIT ?"
            params = (limit,)
        cur = self._conn.execute(q, params)
        return [_row_to_dict(r) for r in cur.fetchall()]

    def find_by_city_and_direction(
        self,
        city: str,
        activity_direction: str,
        *,
        exact: bool = False,
        max_rows: int = 10000,
    ) -> List[Dict[str, Any]]:
        # SQLite lower()/LIKE не нормализуют кириллицу как Python; фильтруем в Python.
        cur = self._conn.execute(
            "SELECT * FROM suppliers ORDER BY updated_at DESC LIMIT ?",
            (max_rows,),
        )
        rows = [_row_to_dict(r) for r in cur.fetchall()]
        nc = _normalize_field(city)
        nd = _normalize_field(activity_direction)
        out: List[Dict[str, Any]] = []
        for d in rows:
            ccol = _normalize_field(d.get("city") or "")
            dcol = _normalize_field(d.get("activity_direction") or "")
            if exact:
                if ccol == nc and dcol == nd:
                    out.append(d)
            else:
                if nc and nc not in ccol:
                    continue
                if nd and nd not in dcol:
                    continue
                out.append(d)
        return out

    def search_fts(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return []
        cur = self._conn.execute(
            """
            SELECT s.* FROM suppliers s
            INNER JOIN suppliers_fts f ON s.rowid = f.rowid
            WHERE suppliers_fts MATCH ?
            LIMIT ?
            """,
            (q, limit),
        )
        return [_row_to_dict(r) for r in cur.fetchall()]

    def insert_or_update(self, data: Dict[str, Any]) -> str:
        now = _utc_now_iso()
        supplier_id = data.get("id")
        inn = data.get("inn")
        if supplier_id and self.get_by_id(supplier_id):
            patch = {**data, "updated_at": data.get("updated_at", now)}
            self.update(supplier_id, patch)
            return supplier_id
        if inn is not None and str(inn).strip() != "":
            existing_inn = self.get_by_inn(str(inn))
            if existing_inn:
                sid = existing_inn["id"]
                patch = {**existing_inn, **data, "id": sid, "updated_at": data.get("updated_at", now)}
                self.update(sid, patch)
                return sid
        return self.create({**data, "updated_at": data.get("updated_at", now)})
