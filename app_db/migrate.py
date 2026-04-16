"""
SQL-миграции для SQLite без Alembic.

Запуск вручную (не вызывается из init_db, чтобы не ломать существующие установки):

    python -m app_db.migrate

Путь к БД: переменная окружения SUPPLIER_DB_PATH или значение по умолчанию из app_db.connection.
"""

from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app_db.connection import DEFAULT_DB_PATH

_MIGRATION_FILE = re.compile(r"^(\d+)_.*\.sql$", re.IGNORECASE)


def _migrations_dir() -> Path:
    return Path(__file__).resolve().parent / "migrations"


def _sql_statements(sql: str) -> list[str]:
    """Делит SQL на выражения по ';' вне одиночных кавычек ('' = экранированная кавычка)."""
    parts: list[str] = []
    chunk: list[str] = []
    i, n = 0, len(sql)
    in_quote = False
    while i < n:
        c = sql[i]
        if c == "'":
            if in_quote and i + 1 < n and sql[i + 1] == "'":
                chunk.append("''")
                i += 2
                continue
            in_quote = not in_quote
            chunk.append(c)
        elif c == ";" and not in_quote:
            s = "".join(chunk).strip()
            if s:
                parts.append(s)
            chunk = []
        else:
            chunk.append(c)
        i += 1
    tail = "".join(chunk).strip()
    if tail:
        parts.append(tail)
    return parts


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS _schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT
        )
        """
    )


def ensure_p0_user_request_columns(conn: sqlite3.Connection) -> None:
    """
    Добавляет колонки P0 в user_requests, если их ещё нет (старые БД до обновления schema.sql).
    """
    cur = conn.execute("PRAGMA table_info(user_requests)")
    cols = {str(row[1]) for row in cur.fetchall()}
    if "clarification_json" not in cols:
        conn.execute("ALTER TABLE user_requests ADD COLUMN clarification_json TEXT")
    if "selected_supplier_ids" not in cols:
        conn.execute("ALTER TABLE user_requests ADD COLUMN selected_supplier_ids TEXT")


def run_migrations(db_path: str | None = None) -> list[int]:
    """
    Накатывает ``app_db/migrations/*.sql`` по возрастанию имени файла.
    Версия — числовой префикс до первого ``_`` (например ``0002_foo.sql`` → 2).
    Возвращает список версий, применённых в этом запуске.
    """
    path = db_path if db_path is not None else os.getenv("SUPPLIER_DB_PATH", DEFAULT_DB_PATH)
    applied_new: list[int] = []
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        _ensure_table(conn)
        ensure_p0_user_request_columns(conn)
        conn.commit()
        done = {row[0] for row in conn.execute("SELECT version FROM _schema_migrations")}
        files = sorted(_migrations_dir().glob("*.sql"))
        for f in files:
            m = _MIGRATION_FILE.match(f.name)
            if not m:
                continue
            version = int(m.group(1), 10)
            if version in done:
                continue
            sql = f.read_text(encoding="utf-8")
            conn.execute("BEGIN IMMEDIATE")
            try:
                for stmt in _sql_statements(sql):
                    conn.execute(stmt)
                conn.execute(
                    "INSERT INTO _schema_migrations (version, applied_at) VALUES (?, ?)",
                    (version, datetime.now(timezone.utc).isoformat()),
                )
                conn.execute("COMMIT")
                applied_new.append(version)
                done.add(version)
            except Exception:
                conn.execute("ROLLBACK")
                raise
    finally:
        conn.close()
    return applied_new


if __name__ == "__main__":
    applied = run_migrations(os.getenv("SUPPLIER_DB_PATH", DEFAULT_DB_PATH))
    print("Applied migrations:", applied if applied else "(none)")
