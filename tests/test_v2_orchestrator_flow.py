"""Интеграционный сценарий RequestOrchestrator на временном SQLite (без Flask)."""

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
    fd, path = tempfile.mkstemp(suffix="_v2_orch_flow.db")
    os.close(fd)
    _unlink_sqlite_paths(path)
    try:
        yield path
    finally:
        _unlink_sqlite_paths(path)


def test_request_orchestrator_flow_local_confirm_then_skip_send(temp_db_path):
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
    started = orch.start_request(
        raw_text="Нужны поставщики для пекарни",
        city="Новосибирск",
        activity_direction="пекар",
    )
    request_id = started["request_id"]
    assert started["step"] == OrchestrationStep.AWAIT_USER_LOCAL_CONFIRM.value

    after_local = orch.user_confirm_local_send(request_id, True)
    assert after_local["ok"] is True
    assert after_local["step"] == OrchestrationStep.AWAIT_SEND_CONFIRM.value

    conn = get_connection(temp_db_path)
    try:
        n_drafts = conn.execute(
            "SELECT COUNT(*) AS c FROM outbound_email_drafts WHERE request_id = ?",
            (request_id,),
        ).fetchone()["c"]
    finally:
        conn.close()
    assert n_drafts >= 1

    final = orch.confirm_send_emails(request_id, False)
    assert final["ok"] is True
    assert final["step"] == OrchestrationStep.DONE.value

    conn = get_connection(temp_db_path)
    try:
        row = conn.execute(
            "SELECT status FROM user_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row["status"] == OrchestrationStep.DONE.value

    raw = sqlite3.connect(temp_db_path)
    try:
        r2 = raw.execute(
            "SELECT status FROM user_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
    finally:
        raw.close()
    assert r2 is not None
    assert r2[0] == OrchestrationStep.DONE.value
