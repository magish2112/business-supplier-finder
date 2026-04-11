"""Оркестратор заявок на подбор поставщиков (MVP, SQLite)."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from integrations.llm_client import complete_json
from integrations.email_service import send_email
from app_db.connection import DEFAULT_DB_PATH
from app_db.orchestration_repositories import (
    insert_outbound_email_drafts,
    insert_user_request,
    mark_outbound_email_drafts_sent,
    update_user_request_status,
)
from app_db.repositories import SupplierRepository
from orchestration.state import OrchestrationStep

logger = logging.getLogger(__name__)


def _strip_json_fence(text: str) -> str:
    t = (text or "").strip()
    if not t.startswith("```"):
        return t
    lines = t.split("\n")
    if len(lines) >= 2 and lines[0].strip().startswith("```"):
        lines = lines[1:]
    while lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    if lines and "```" in lines[-1]:
        lines[-1] = lines[-1].rsplit("```", 1)[0]
    return "\n".join(lines).strip()


def _try_refine_email_body(draft: Dict[str, Any], ctx: Dict[str, Any]) -> str:
    """Опционально улучшает тело письма через настроенный LLM (LLM_PROVIDER); при ошибке — исходный черновик."""
    stub = (draft.get("body_preview") or "").strip()
    system = (
        "Отвечай только валидным JSON-объектом без пояснений и без markdown. "
        'Формат: {"body": "<текст>"}. '
        "Поле body — вежливое деловое письмо на русском языке одному адресату, "
        "кратко, с просьбой о коммерческом предложении; без строки темы внутри текста."
    )
    user_payload = json.dumps(
        {
            "tema_pisma": draft.get("subject") or "",
            "gorod": ctx.get("city") or "",
            "napravlenie": ctx.get("activity_direction") or "",
            "tekst_zayavki": ((ctx.get("raw_text") or "")[:800]),
            "chernovik_tela": stub,
        },
        ensure_ascii=False,
    )
    user = f"Улучши черновик письма. Входные данные (JSON):\n{user_payload}"
    raw = complete_json(system, user, max_tokens=1024)
    try:
        data = json.loads(_strip_json_fence(raw))
        if isinstance(data, dict):
            body = data.get("body")
            if isinstance(body, str) and body.strip():
                return body.strip()
    except (json.JSONDecodeError, TypeError, ValueError):
        logger.debug("Не удалось разобрать JSON тела письма от модели, оставляем черновик.")
    return stub

SESSIONS_DDL = """
CREATE TABLE IF NOT EXISTS orchestration_sessions (
    request_id TEXT PRIMARY KEY,
    step TEXT NOT NULL,
    context_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _resolve_db_path(explicit: Optional[str]) -> str:
    """
    Явный аргумент → ORCHESTRATION_DB_PATH → тот же файл, что и у get_connection()
    (SUPPLIER_DB_PATH или supplier_finder.db).
    """
    if explicit:
        return explicit
    env_orch = os.getenv("ORCHESTRATION_DB_PATH")
    if env_orch:
        return env_orch
    return os.getenv("SUPPLIER_DB_PATH", DEFAULT_DB_PATH)


def _supplier_card_from_finder(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": (item.get("name") or "").strip() or "Без названия",
        "website": item.get("website"),
        "email": item.get("email"),
        "source": item.get("source") or "web",
    }


def _supplier_card_from_supplier_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": (row.get("name") or "").strip() or "Без названия",
        "website": row.get("website_url"),
        "email": row.get("email"),
        "source": row.get("source") or "local_db",
    }


class RequestOrchestrator:
    """
    Управляет шагами сценария и хранит состояние в SQLite (таблица orchestration_sessions).
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = _resolve_db_path(db_path)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_sessions_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_sessions_table(self) -> None:
        with self._connect() as conn:
            conn.executescript(SESSIONS_DDL)

    def _load_session(self, request_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT request_id, step, context_json FROM orchestration_sessions WHERE request_id = ?",
                (request_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "request_id": row["request_id"],
            "step": row["step"],
            "context": json.loads(row["context_json"]),
        }

    def _save_session(self, request_id: str, step: OrchestrationStep, context: Dict[str, Any]) -> None:
        now = _utc_now_iso()
        payload = json.dumps(context, ensure_ascii=False)
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT request_id FROM orchestration_sessions WHERE request_id = ?",
                (request_id,),
            )
            exists = cur.fetchone() is not None
            if exists:
                conn.execute(
                    """UPDATE orchestration_sessions
                       SET step = ?, context_json = ?, updated_at = ?
                       WHERE request_id = ?""",
                    (step.value, payload, now, request_id),
                )
            else:
                conn.execute(
                    """INSERT INTO orchestration_sessions
                       (request_id, step, context_json, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (request_id, step.value, payload, now, now),
                )

    def _query_local_suppliers(self, city: str, activity_direction: str) -> List[Dict[str, Any]]:
        """
        Локальные кандидаты из таблицы suppliers через SupplierRepository.
        exact=False: подстрока в city и activity_direction (нормализация в Python, в т.ч. кириллица);
        пустое city или направление — без фильтра по этому полю (любые значения в БД).
        """
        city_norm = (city or "").strip()
        act = (activity_direction or "").strip()
        try:
            with SupplierRepository(db_path=self._db_path) as repo:
                rows = repo.find_by_city_and_direction(city_norm, act, exact=False)
            return [_supplier_card_from_supplier_row(r) for r in rows]
        except sqlite3.OperationalError as e:
            if "no such table" in str(e).lower():
                logger.info("Таблица suppliers отсутствует — локальный список пуст.")
                return []
            raise

    def _run_web_discovery(self, product: str, region: str) -> List[Dict[str, Any]]:
        try:
            from business_supplier_finder import BusinessSupplierFinder

            raw = BusinessSupplierFinder().search_suppliers(
                product=product, region=region, quantity=""
            )
            return [_supplier_card_from_finder(x) for x in raw]
        except Exception as e:
            logger.exception("Ошибка веб-поиска поставщиков: %s", e)
            return []

    def start_request(self, raw_text: str, city: str, activity_direction: str) -> Dict[str, Any]:
        """
        Создаёт заявку: локальный матч, при отсутствии записей — внешний поиск.
        Возвращает идентификатор, текущий шаг, локальный список, при необходимости — найденные в сети карточки.
        """
        request_id = str(uuid.uuid4())
        local = self._query_local_suppliers(city, activity_direction)
        product = (activity_direction or "").strip() or (raw_text or "").strip()[:200]

        context: Dict[str, Any] = {
            "raw_text": raw_text,
            "city": city,
            "activity_direction": activity_direction,
            "local_suppliers": local,
            "discovered_suppliers": [],
            "email_draft": None,
            "ui_message": "",
            "send_confirmed": None,
        }

        if local:
            step = OrchestrationStep.AWAIT_USER_LOCAL_CONFIRM
            msg = (
                "Найдены локальные поставщики по городу и направлению. "
                "Подтвердите, нужно ли подготовить рассылку по этому списку."
            )
        else:
            discovered = self._run_web_discovery(product=product, region=city)
            context["discovered_suppliers"] = discovered
            step = OrchestrationStep.PROPOSE
            if discovered:
                msg = (
                    "В локальном каталоге записей нет. Ниже — предварительный список "
                    "из открытых источников (проверьте контакты перед использованием)."
                )
            else:
                msg = (
                    "Локальных поставщиков не найдено, а автоматический поиск в сети "
                    "сейчас не дал результатов. Попробуйте уточнить город или формулировку запроса."
                )

        context["ui_message"] = msg
        self._save_session(request_id, step, context)

        try:
            insert_user_request(
                self._db_path,
                request_id=request_id,
                raw_query=raw_text or "",
                city=(city or "").strip() or None,
                activity_direction=(activity_direction or "").strip() or None,
                status=step.value,
                structured_json=None,
            )
        except Exception as e:
            logger.warning("Не удалось записать user_requests: %s", e, exc_info=True)

        out: Dict[str, Any] = {
            "request_id": request_id,
            "step": step.value,
            "local_suppliers": local,
            "message_for_user": msg,
        }
        if not local:
            out["discovered_suppliers"] = context["discovered_suppliers"]
        return out

    def user_confirm_local_send(self, request_id: str, yes: bool) -> Dict[str, Any]:
        """
        Ответ пользователя на предложение рассылки локальным поставщикам.
        При согласии — переход к подтверждению отправки (черновик без реальной отправки).
        При отказе — веб-поиск и предложение внешних кандидатов.
        """
        session = self._load_session(request_id)
        if not session or session["step"] != OrchestrationStep.AWAIT_USER_LOCAL_CONFIRM.value:
            return {
                "request_id": request_id,
                "step": session["step"] if session else "UNKNOWN",
                "ok": False,
                "message_for_user": "Заявка не найдена или для неё недоступно это действие.",
            }

        ctx = session["context"]
        city = ctx.get("city") or ""
        product = (ctx.get("activity_direction") or "").strip() or (ctx.get("raw_text") or "")[:200]

        if yes:
            locals_list = ctx.get("local_suppliers") or []
            emails = [s.get("email") for s in locals_list if s.get("email")]
            ctx["email_draft"] = {
                "stub": True,
                "recipients": emails,
                "subject": f"Запрос поставки — {product or 'без темы'}",
                "body_preview": (
                    "Здравствуйте. Просим направить коммерческое предложение "
                    "по запросу клиента (текст заявки хранится в системе). Отправка не выполнялась."
                ),
            }
            step = OrchestrationStep.AWAIT_SEND_CONFIRM
            msg = (
                "Черновик письма для локальных поставщиков подготовлен (отправка ещё не выполнялась). "
                "Подтвердите отправку через API отправки писем, когда будете готовы."
            )
            try:
                ed = ctx["email_draft"]
                insert_outbound_email_drafts(
                    self._db_path,
                    request_id=request_id,
                    recipients=list(ed.get("recipients") or []),
                    subject=(ed.get("subject") or "").strip() or "Запрос поставщику",
                    body=(ed.get("body_preview") or "").strip(),
                )
            except Exception as e:
                logger.warning("Не удалось записать outbound_email_drafts: %s", e, exc_info=True)
        else:
            discovered = self._run_web_discovery(product=product, region=city)
            ctx["discovered_suppliers"] = discovered
            step = OrchestrationStep.PROPOSE
            if discovered:
                msg = (
                    "Рассылка локальным поставщикам отменена. Ниже — варианты из интернет-поиска "
                    "(проверьте данные самостоятельно)."
                )
            else:
                msg = (
                    "Рассылка локальным поставщикам отменена. Автоматический поиск в сети "
                    "не дал результатов; уточните параметры и попробуйте снова."
                )

        ctx["ui_message"] = msg
        ctx["send_confirmed"] = bool(yes)
        self._save_session(request_id, step, ctx)

        try:
            update_user_request_status(self._db_path, request_id, step.value)
        except Exception as e:
            logger.warning("Не удалось обновить user_requests.status: %s", e, exc_info=True)

        result: Dict[str, Any] = {
            "request_id": request_id,
            "step": step.value,
            "ok": True,
            "message_for_user": msg,
        }
        if yes:
            result["email_draft"] = ctx.get("email_draft")
        else:
            result["discovered_suppliers"] = ctx.get("discovered_suppliers", [])
        return result

    def confirm_send_emails(self, request_id: str, execute: bool) -> Dict[str, Any]:
        """
        Подтверждение отправки писем после шага AWAIT_SEND_CONFIRM.
        При execute=False — только завершение сценария без SMTP.
        """
        session = self._load_session(request_id)
        if not session or session["step"] != OrchestrationStep.AWAIT_SEND_CONFIRM.value:
            return {
                "request_id": request_id,
                "step": session["step"] if session else "UNKNOWN",
                "ok": False,
                "message_for_user": (
                    "Заявка не найдена или для неё недоступно подтверждение отправки "
                    "(ожидается шаг ожидания подтверждения писем)."
                ),
            }

        ctx = session["context"]
        draft = ctx.get("email_draft") or {}
        recipients = [r for r in (draft.get("recipients") or []) if r and str(r).strip()]
        subject = (draft.get("subject") or "Запрос поставщику").strip()

        if not execute:
            step = OrchestrationStep.DONE
            msg = (
                "Отправка писем не выполнялась: выбран режим без отправки. "
                "Сценарий завершён."
            )
            ctx["ui_message"] = msg
            ctx["email_send_executed"] = False
            ctx["email_send_results"] = []
            self._save_session(request_id, step, ctx)

            try:
                update_user_request_status(self._db_path, request_id, step.value)
            except Exception as e:
                logger.warning("Не удалось обновить user_requests.status: %s", e, exc_info=True)

            return {
                "request_id": request_id,
                "step": step.value,
                "ok": True,
                "message_for_user": msg,
                "email_send_results": [],
            }

        body = _try_refine_email_body(draft, ctx)
        if draft.get("body_preview") != body:
            draft = {**draft, "body_preview": body, "stub": False}
            ctx["email_draft"] = draft

        results: List[Dict[str, Any]] = []
        for to_addr in recipients:
            ok = send_email(str(to_addr).strip(), subject, body, dry_run=False)
            results.append({"to": str(to_addr).strip(), "sent": bool(ok)})

        try:
            mark_outbound_email_drafts_sent(
                self._db_path,
                request_id=request_id,
                sent_at_iso=_utc_now_iso(),
            )
        except Exception as e:
            logger.warning("Не удалось обновить sent_at в outbound_email_drafts: %s", e, exc_info=True)

        sent_n = sum(1 for x in results if x.get("sent"))
        total = len(results)
        if total == 0:
            msg = (
                "Отправка не требовалась: в черновике не было адресатов. Сценарий завершён."
            )
        elif sent_n == total:
            msg = (
                f"Попытка отправки завершена: обработано писем — {total}. "
                "Если включён EMAIL_DRY_RUN или не настроен SMTP, реальная доставка не выполнялась — см. журнал сервера."
            )
        elif sent_n == 0:
            msg = (
                f"Письма не были доставлены ({total} адресатов). "
                "Проверьте SMTP, переменную EMAIL_DRY_RUN и журнал сервера."
            )
        else:
            msg = (
                f"Часть писем отправлена: успешно {sent_n} из {total}. "
                "Подробности — в журнале сервера."
            )

        step = OrchestrationStep.DONE
        ctx["ui_message"] = msg
        ctx["email_send_executed"] = True
        ctx["email_send_results"] = results
        self._save_session(request_id, step, ctx)

        try:
            update_user_request_status(self._db_path, request_id, step.value)
        except Exception as e:
            logger.warning("Не удалось обновить user_requests.status: %s", e, exc_info=True)

        return {
            "request_id": request_id,
            "step": step.value,
            "ok": True,
            "message_for_user": msg,
            "email_send_results": results,
        }

    def _suppliers_for_api(self, step_value: str, ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        if step_value == OrchestrationStep.AWAIT_USER_LOCAL_CONFIRM.value:
            return list(ctx.get("local_suppliers") or [])
        if step_value == OrchestrationStep.AWAIT_SEND_CONFIRM.value:
            return list(ctx.get("local_suppliers") or [])
        if step_value == OrchestrationStep.PROPOSE.value:
            return list(ctx.get("discovered_suppliers") or [])
        local = ctx.get("local_suppliers") or []
        disc = ctx.get("discovered_suppliers") or []
        return list(local) + list(disc)

    def get_api_state(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Состояние заявки в формате HTTP API v2."""
        session = self._load_session(request_id)
        if not session:
            return None
        ctx = session["context"]
        step = session["step"]
        out: Dict[str, Any] = {
            "request_id": request_id,
            "step": step,
            "message": ctx.get("ui_message") or "",
            "suppliers": self._suppliers_for_api(step, ctx),
            "query": ctx.get("raw_text") or "",
            "city": ctx.get("city") or "",
            "activity_direction": ctx.get("activity_direction") or "",
            "send_confirmed": ctx.get("send_confirmed"),
        }
        if step == OrchestrationStep.AWAIT_SEND_CONFIRM.value:
            out["email_draft"] = ctx.get("email_draft")
        if step == OrchestrationStep.DONE.value and ctx.get("email_send_results") is not None:
            out["email_send_results"] = ctx.get("email_send_results")
        return out


_default_orchestrator = RequestOrchestrator()


def start_request(query: str, city: str, activity_direction: str) -> Dict[str, Any]:
    """Обёртка для Flask: поле query → raw_text оркестратора."""
    r = _default_orchestrator.start_request(
        raw_text=(query or "").strip(),
        city=city or "",
        activity_direction=activity_direction or "",
    )
    suppliers: List[Dict[str, Any]] = list(r.get("local_suppliers") or [])
    if not suppliers and r.get("discovered_suppliers"):
        suppliers = list(r["discovered_suppliers"])
    return {
        "request_id": r["request_id"],
        "step": r["step"],
        "message": r.get("message_for_user") or "",
        "suppliers": suppliers,
        "query": (query or "").strip(),
        "city": (city or "").strip(),
        "activity_direction": (activity_direction or "").strip(),
        "send_confirmed": None,
    }


def get_request_state(request_id: str) -> Optional[Dict[str, Any]]:
    return _default_orchestrator.get_api_state(request_id)


def confirm_local(request_id: str, send: bool) -> Optional[Dict[str, Any]]:
    session = _default_orchestrator._load_session(request_id)
    if not session:
        return None
    r = _default_orchestrator.user_confirm_local_send(request_id, send)
    if not r.get("ok"):
        return {"_error": True, "message": r.get("message_for_user") or "invalid state"}
    return _default_orchestrator.get_api_state(request_id)


def send_confirmed_emails(request_id: str, execute: bool) -> Optional[Dict[str, Any]]:
    """Обёртка для Flask: то же поведение, что у RequestOrchestrator.confirm_send_emails."""
    session = _default_orchestrator._load_session(request_id)
    if not session:
        return None
    r = _default_orchestrator.confirm_send_emails(request_id, execute)
    if not r.get("ok"):
        return {"_error": True, "message": r.get("message_for_user") or "invalid state"}
    return _default_orchestrator.get_api_state(request_id)


if __name__ == "__main__":
    from app_db import init_db

    logging.basicConfig(level=logging.WARNING)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    def _demo_local_branch() -> None:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        init_db(path)
        orch = RequestOrchestrator(db_path=path)
        with SupplierRepository(db_path=path) as repo:
            repo.insert_or_update(
                {
                    "name": "ООО Трубы",
                    "city": "Москва",
                    "activity_direction": "сантехника",
                    "website_url": "https://example-pipes.ru",
                    "email": "zakaz@example-pipes.ru",
                    "source": "local_db",
                }
            )
        r = orch.start_request(
            raw_text="Нужен опт сантехники",
            city="Москва",
            activity_direction="сантехника",
        )
        print("start_request:", json.dumps(r, ensure_ascii=False, indent=2))
        c = orch.user_confirm_local_send(r["request_id"], True)
        print("user_confirm_local_send(yes):", json.dumps(c, ensure_ascii=False, indent=2))

    _demo_local_branch()
    if os.getenv("ORCHESTRATION_DEMO_WEB", "").lower() in ("1", "true", "yes"):
        print("--- полный веб-поиск (долго) ---")
        orch2 = RequestOrchestrator()
        r2 = orch2.start_request(
            raw_text="Нужен опт сантехники",
            city="Москва",
            activity_direction="сантехника",
        )
        print("start_request (web):", json.dumps(r2, ensure_ascii=False, indent=2))
