"""Интеграция оркестратора с SQLite: локальный матч и запись user_requests."""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from app_db import init_db
from app_db.connection import get_connection
from app_db.repositories import SupplierRepository
from orchestration import RequestOrchestrator
from orchestration.state import OrchestrationStep


def _unlink_sqlite_paths(db_path: str) -> None:
    p = Path(db_path)
    for f in (p, p.with_name(p.name + "-wal"), p.with_name(p.name + "-shm")):
        try:
            f.unlink(missing_ok=True)
        except OSError:
            pass


@pytest.fixture
def temp_db_path():
    """Отдельный файл через tempfile (без rmtree каталога — на Windows WAL держит блокировку)."""
    fd, path = tempfile.mkstemp(suffix="_orch_test.db")
    os.close(fd)
    _unlink_sqlite_paths(path)
    try:
        yield path
    finally:
        _unlink_sqlite_paths(path)


def test_start_request_persists_user_request_when_local_supplier_matches(temp_db_path):
    init_db(temp_db_path)
    with SupplierRepository(db_path=temp_db_path) as repo:
        repo.create(
            {
                "name": "Тестовый поставщик",
                "city": "Новосибирск",
                "activity_direction": "Поставка комплектующих для пекарен",
                "email": "supplier@example.test",
                "source": "test",
            }
        )

    orch = RequestOrchestrator(db_path=temp_db_path)
    result = orch.start_request(
        raw_text="Нужны поставщики для пекарни",
        city="Новосибирск",
        activity_direction="пекар",
    )

    request_id = result["request_id"]
    assert result["step"] == OrchestrationStep.AWAIT_USER_LOCAL_CONFIRM.value
    assert result["local_suppliers"]

    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute(
            "SELECT id, status FROM user_requests WHERE id = ?",
            (request_id,),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["id"] == request_id
    assert row["status"] == OrchestrationStep.AWAIT_USER_LOCAL_CONFIRM.value

    # Дублируем проверку «сырым» sqlite3 на том же пути (без зависимости от row_factory)
    raw = sqlite3.connect(temp_db_path)
    try:
        r2 = raw.execute(
            "SELECT status FROM user_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
    finally:
        raw.close()
    assert r2 is not None
    assert r2[0] == OrchestrationStep.AWAIT_USER_LOCAL_CONFIRM.value
