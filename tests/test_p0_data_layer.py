"""P0: миграции, SupplierRepository.search/upsert, orchestration_repositories."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from app_db import init_db
from app_db.migrate import ensure_p0_user_request_columns, run_migrations
from app_db.orchestration_repositories import (
    append_clarification,
    insert_audit_event,
    insert_user_request,
    update_user_request_structured,
)
from app_db.repositories import SupplierRepository


def _unlink_sqlite_paths(db_path: str) -> None:
    p = Path(db_path)
    for f in (p, p.with_name(p.name + "-wal"), p.with_name(p.name + "-shm")):
        try:
            f.unlink(missing_ok=True)
        except OSError:
            pass


@pytest.fixture
def temp_db_path():
    fd, path = tempfile.mkstemp(suffix="_p0_data.db")
    os.close(fd)
    _unlink_sqlite_paths(path)
    try:
        yield path
    finally:
        _unlink_sqlite_paths(path)


def test_init_db_applies_p0_columns_and_audit_table(temp_db_path):
    init_db(temp_db_path)
    conn = sqlite3.connect(temp_db_path)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(user_requests)")}
        assert "clarification_json" in cols
        assert "selected_supplier_ids" in cols
        assert (
            conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='request_audit_events'"
            ).fetchone()
            is not None
        )
    finally:
        conn.close()


def test_run_migrations_idempotent_on_old_style_user_requests(temp_db_path):
    """БД только из schema без вызова init_db: emulate старая таблица без P0-колонок."""
    conn = sqlite3.connect(temp_db_path)
    try:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE user_requests (
                id TEXT PRIMARY KEY,
                raw_query TEXT NOT NULL,
                structured_json TEXT,
                city TEXT,
                activity_direction TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()

    run_migrations(temp_db_path)
    conn = sqlite3.connect(temp_db_path)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(user_requests)")}
        assert "clarification_json" in cols
        assert "selected_supplier_ids" in cols
        assert (
            conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='request_audit_events'"
            ).fetchone()
            is not None
        )
    finally:
        conn.close()

    applied = run_migrations(temp_db_path)
    assert applied == []


def test_ensure_p0_user_request_columns_noop_when_present(temp_db_path):
    init_db(temp_db_path)
    conn = sqlite3.connect(temp_db_path)
    try:
        ensure_p0_user_request_columns(conn)
        conn.commit()
    finally:
        conn.close()


def test_search_suppliers_for_procurement_geo_only(temp_db_path):
    init_db(temp_db_path)
    with SupplierRepository(db_path=temp_db_path) as repo:
        repo.create(
            {
                "name": "Гео А",
                "city": "Казань",
                "activity_direction": "Продукты питания",
                "source": "t",
            }
        )
        repo.create(
            {
                "name": "Гео Б",
                "city": "Москва",
                "activity_direction": "Услуги",
                "source": "t",
            }
        )
        hits = repo.search_suppliers_for_procurement(
            city="Казань",
            region="",
            activity_direction="продукт",
            product_query="",
            limit=10,
        )
    assert len(hits) == 1
    assert hits[0]["name"] == "Гео А"


def test_search_suppliers_for_procurement_region_filters_geo(temp_db_path):
    init_db(temp_db_path)
    with SupplierRepository(db_path=temp_db_path) as repo:
        repo.create(
            {
                "name": "В Поволжье",
                "city": "Нижний Новгород",
                "activity_direction": "Опт",
                "source": "t",
            }
        )
        repo.create(
            {
                "name": "Другой",
                "city": "Владивосток",
                "activity_direction": "Опт",
                "source": "t",
            }
        )
        hits = repo.search_suppliers_for_procurement(
            city="",
            region="Нижний",
            activity_direction="опт",
            product_query="",
            limit=10,
        )
    assert len(hits) == 1
    assert "Нижний" in hits[0]["city"]


def _fts5_supported() -> bool:
    con = sqlite3.connect(":memory:")
    try:
        con.execute("CREATE VIRTUAL TABLE _fts_probe USING fts5(x)")
        return True
    except sqlite3.OperationalError:
        return False


requires_fts5 = pytest.mark.skipif(not _fts5_supported(), reason="SQLite без FTS5")


@requires_fts5
def test_search_suppliers_for_procurement_combines_fts_and_geo(temp_db_path):
    init_db(temp_db_path)
    token = "ZzProcurementToken441"
    with SupplierRepository(db_path=temp_db_path) as repo:
        repo.create(
            {
                "name": f"FTS {token} поставщик",
                "city": "Уфа",
                "activity_direction": "Стройматериалы",
                "inn": "7700000001",
                "source": "t",
            }
        )
        repo.create(
            {
                "name": "Только гео",
                "city": "Уфа",
                "activity_direction": "Стройматериалы",
                "source": "t",
            }
        )
        hits = repo.search_suppliers_for_procurement(
            city="Уфа",
            region="",
            activity_direction="строй",
            product_query=token,
            limit=10,
        )
    assert len(hits) == 2
    names = " ".join((h.get("name") or "") for h in hits)
    assert token in names


def test_find_for_request_delegates(temp_db_path):
    init_db(temp_db_path)
    with SupplierRepository(db_path=temp_db_path) as repo:
        repo.create(
            {
                "name": "Делегат",
                "city": "Самара",
                "activity_direction": "Логистика",
                "source": "t",
            }
        )
        hits = repo.find_for_request(
            {"city": "Самара", "activity_direction": "логист", "product_query": ""},
            limit=5,
        )
    assert len(hits) == 1


def test_upsert_from_discovery(temp_db_path):
    init_db(temp_db_path)
    with SupplierRepository(db_path=temp_db_path) as repo:
        sid = repo.upsert_from_discovery(
            {
                "name": "ООО Тест Дискавери",
                "website": "https://example.test",
                "email": "a@example.test",
                "phone": "+7 900 000-00-00",
                "inn": "6312345678",
                "city": "Тольятти",
                "activity_direction": "Авто",
                "source": "web",
                "verification_status": "unverified",
            }
        )
        row = repo.get_by_id(sid)
        assert row["website_url"] == "https://example.test"
        assert row["inn"] == "6312345678"
        same = repo.upsert_from_discovery(
            {
                "name": "ООО Тест Дискавери обновл",
                "website_url": "https://example.test",
                "inn": "6312345678",
                "email": "b@example.test",
            }
        )
        assert same == sid
        row2 = repo.get_by_id(sid)
        assert row2["email"] == "b@example.test"
        assert "обновл" in row2["name"]


def test_orchestration_p0_persist_helpers(temp_db_path):
    init_db(temp_db_path)
    rid = "req-p0-1"
    insert_user_request(
        temp_db_path,
        request_id=rid,
        raw_query="тест",
        city="Казань",
        activity_direction="Пищевка",
        status="NEW",
    )
    assert update_user_request_structured(
        temp_db_path,
        rid,
        {"city": "Казань", "product": "мука", "pending_questions": ["кол-во?"]},
    )
    append_clarification(temp_db_path, rid, {"question": "Объём?", "answer": "1 т"})
    append_clarification(temp_db_path, rid, {"question": "Срок?", "answer": "срочно"})

    eid = insert_audit_event(
        temp_db_path,
        request_id=rid,
        event_type="test.event",
        payload={"x": 1},
    )
    assert eid

    conn = sqlite3.connect(temp_db_path)
    conn.row_factory = sqlite3.Row
    try:
        ur = conn.execute("SELECT * FROM user_requests WHERE id = ?", (rid,)).fetchone()
        st = json.loads(ur["structured_json"])
        assert st["product"] == "мука"
        clar = json.loads(ur["clarification_json"])
        assert len(clar["items"]) == 2
        ev = conn.execute(
            "SELECT event_type, payload_json FROM request_audit_events WHERE id = ?",
            (eid,),
        ).fetchone()
        assert ev["event_type"] == "test.event"
        assert json.loads(ev["payload_json"])["x"] == 1
    finally:
        conn.close()
