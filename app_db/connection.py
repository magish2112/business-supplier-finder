"""SQLite connection helper."""

from __future__ import annotations

import os
import sqlite3
from typing import Optional

DEFAULT_DB_PATH = "supplier_finder.db"


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Open a SQLite connection. Path: ``db_path`` or env ``SUPPLIER_DB_PATH`` or ``supplier_finder.db``.
    Enables foreign keys and row_factory for dict-like rows.
    """
    path = db_path if db_path is not None else os.getenv("SUPPLIER_DB_PATH", DEFAULT_DB_PATH)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn
