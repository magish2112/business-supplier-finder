"""Persistent storage (SQLite) for supplier orchestration."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from app_db.connection import DEFAULT_DB_PATH, get_connection

__all__ = ["DEFAULT_DB_PATH", "get_connection", "init_db", "import_suppliers_from_excel"]

from app_db.excel_import import import_suppliers_from_excel  # noqa: E402


def init_db(db_path: str | None = None) -> None:
    """
    Create the database file (and parent directories) if needed and apply ``schema.sql``.
    """
    path = Path(db_path or os.getenv("SUPPLIER_DB_PATH", DEFAULT_DB_PATH))
    path.parent.mkdir(parents=True, exist_ok=True)
    schema_file = Path(__file__).resolve().with_name("schema.sql")
    schema_sql = schema_file.read_text(encoding="utf-8")
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()
