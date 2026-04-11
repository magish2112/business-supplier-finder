"""Persistent storage (SQLite) for supplier orchestration."""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

from app_db.connection import DEFAULT_DB_PATH, get_connection

__all__ = [
    "DEFAULT_DB_PATH",
    "get_connection",
    "init_db",
    "import_suppliers_from_excel",
    "ensure_suppliers_fts",
]

from app_db.excel_import import import_suppliers_from_excel  # noqa: E402

logger = logging.getLogger(__name__)

# Маркер в schema.sql: всё после этой строки — опциональный FTS5 (см. ensure_suppliers_fts).
_FTS_SECTION_MARKER = "-- BEGIN FTS5 OPTIONAL\n"


def ensure_suppliers_fts(conn: sqlite3.Connection) -> None:
    """
    Создаёт виртуальную таблицу suppliers_fts и триггеры синхронизации.
    Безопасно для повторных вызовов (IF NOT EXISTS). Ошибки (нет FTS5 в сборке SQLite) не пробрасываются.
    """
    schema_file = Path(__file__).resolve().with_name("schema.sql")
    full = schema_file.read_text(encoding="utf-8")
    if _FTS_SECTION_MARKER not in full:
        return
    _, _, fts_sql = full.partition(_FTS_SECTION_MARKER)
    fts_sql = fts_sql.strip()
    if not fts_sql:
        return
    try:
        conn.executescript(fts_sql)
        conn.commit()
    except sqlite3.OperationalError as e:
        logger.warning("FTS5 для suppliers недоступен или не создан: %s", e)
        conn.rollback()


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
        if _FTS_SECTION_MARKER in schema_sql:
            base_sql, _, _ = schema_sql.partition(_FTS_SECTION_MARKER)
            conn.executescript(base_sql)
        else:
            conn.executescript(schema_sql)
        conn.commit()
        ensure_suppliers_fts(conn)
    finally:
        conn.close()
