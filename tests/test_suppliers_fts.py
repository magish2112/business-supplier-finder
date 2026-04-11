"""Полнотекстовый поиск поставщиков (FTS5)."""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from app_db import init_db
from app_db.repositories import SupplierRepository


def _unlink_sqlite_paths(db_path: str) -> None:
    p = Path(db_path)
    for f in (p, p.with_name(p.name + "-wal"), p.with_name(p.name + "-shm")):
        try:
            f.unlink(missing_ok=True)
        except OSError:
            pass


def _fts5_supported() -> bool:
    con = sqlite3.connect(":memory:")
    try:
        con.execute("CREATE VIRTUAL TABLE _fts_probe USING fts5(x)")
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        con.close()


requires_fts5 = pytest.mark.skipif(not _fts5_supported(), reason="SQLite без FTS5")


@pytest.fixture
def temp_db_path():
    fd, path = tempfile.mkstemp(suffix="_fts_test.db")
    os.close(fd)
    _unlink_sqlite_paths(path)
    try:
        yield path
    finally:
        _unlink_sqlite_paths(path)


@requires_fts5
def test_search_fts_finds_supplier_by_distinctive_word(temp_db_path):
    init_db(temp_db_path)
    token = "XyZZyFtsToken9941"
    with SupplierRepository(db_path=temp_db_path) as repo:
        repo.create(
            {
                "name": f"ООО {token} Поставка",
                "city": "Казань",
                "activity_direction": "Оптовая торговля",
                "inn": "7700000000",
                "source": "test",
            }
        )
        repo.create(
            {
                "name": "Другая компания",
                "city": "Москва",
                "activity_direction": "Услуги",
                "source": "test",
            }
        )
        hits = repo.search_fts(token)
    assert len(hits) >= 1
    assert any(token in (r.get("name") or "") for r in hits)
