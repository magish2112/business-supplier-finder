"""Интеграционный сценарий RequestOrchestrator на временном SQLite (без Flask)."""

import json
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


def _patch_llm_no_clarify(monkeypatch, **fields):
    payload = {
        "product_query": "пекарня",
        "city": "Новосибирск",
        "region": "",
        "activity_direction": "пекар",
        "quantity": "",
        "delivery_address": "",
        "needs_clarification": False,
        "clarification_questions": [],
    }
    payload.update(fields)

    def fake_complete_json(system, user, max_tokens):
        return json.dumps(payload, ensure_ascii=False)

    monkeypatch.setattr("orchestration.service.complete_json", fake_complete_json)


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


def test_request_orchestrator_flow_local_confirm_then_skip_send(temp_db_path, monkeypatch):
    _patch_llm_no_clarify(monkeypatch)
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


def test_clarification_then_local_search(temp_db_path, monkeypatch):
    _patch_llm_no_clarify(
        monkeypatch,
        needs_clarification=True,
        clarification_questions=["Уточните объём закупки?"],
    )
    init_db(temp_db_path)
    with SupplierRepository(db_path=temp_db_path) as repo:
        repo.create(
            {
                "name": "Поставщик пекарни",
                "city": "Новосибирск",
                "activity_direction": "Поставка для пекарен",
                "email": "a@example.test",
                "source": "test",
            }
        )

    orch = RequestOrchestrator(db_path=temp_db_path)
    started = orch.start_request(
        raw_text="Нужны поставщики",
        city="Новосибирск",
        activity_direction="пекар",
    )
    rid = started["request_id"]
    assert started["step"] == OrchestrationStep.AWAIT_CLARIFICATION.value

    after = orch.submit_clarification(rid, {"q0": "10 тонн в месяц"})
    assert after["ok"] is True
    assert after["step"] == OrchestrationStep.AWAIT_USER_LOCAL_CONFIRM.value
    assert after["local_suppliers"]

    conn = get_connection(temp_db_path)
    try:
        n_audit = conn.execute(
            "SELECT COUNT(*) AS c FROM request_audit_events WHERE request_id = ?",
            (rid,),
        ).fetchone()["c"]
    finally:
        conn.close()
    assert n_audit >= 2


def test_recipient_selection_two_emails(temp_db_path, monkeypatch):
    _patch_llm_no_clarify(
        monkeypatch,
        product_query="кирпич",
        city="Омск",
        activity_direction="строй",
    )
    init_db(temp_db_path)
    ids = []
    with SupplierRepository(db_path=temp_db_path) as repo:
        ids.append(
            repo.create(
                {
                    "name": "Поставщик 1",
                    "city": "Омск",
                    "activity_direction": "Стройка",
                    "email": "one@example.test",
                    "source": "test",
                }
            )
        )
        ids.append(
            repo.create(
                {
                    "name": "Поставщик 2",
                    "city": "Омск",
                    "activity_direction": "Стройматериалы",
                    "email": "two@example.test",
                    "source": "test",
                }
            )
        )

    orch = RequestOrchestrator(db_path=temp_db_path)
    started = orch.start_request(
        raw_text="Кирпич",
        city="Омск",
        activity_direction="строй",
    )
    rid = started["request_id"]
    assert started["step"] == OrchestrationStep.AWAIT_USER_LOCAL_CONFIRM.value

    c1 = orch.user_confirm_local_send(rid, True)
    assert c1["ok"] is True
    assert c1["step"] == OrchestrationStep.AWAIT_RECIPIENT_SELECTION.value

    picked_id = ids[0]
    c2 = orch.submit_recipient_selection(rid, [picked_id])
    assert c2["ok"] is True
    assert c2["step"] == OrchestrationStep.AWAIT_SEND_CONFIRM.value
    assert len(c2.get("email_draft", {}).get("recipients") or []) == 1

    conn = get_connection(temp_db_path)
    try:
        raw_ids = conn.execute(
            "SELECT selected_supplier_ids FROM user_requests WHERE id = ?",
            (rid,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert picked_id in json.loads(raw_ids)
