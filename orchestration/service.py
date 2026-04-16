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
from typing import Any, Dict, List, Optional, Tuple

import sys

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from integrations.llm_client import complete_json
from integrations.email_service import send_email
from app_db.connection import DEFAULT_DB_PATH
from app_db.orchestration_repositories import (
    append_clarification,
    insert_audit_event,
    insert_outbound_email_drafts,
    insert_user_request,
    mark_outbound_email_drafts_sent,
    update_user_request_selected_supplier_ids,
    update_user_request_status,
    update_user_request_structured,
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
    st = ctx.get("structured") if isinstance(ctx.get("structured"), dict) else {}
    user_payload = json.dumps(
        {
            "tema_pisma": draft.get("subject") or "",
            "gorod": (st.get("city") or ctx.get("city") or ""),
            "napravlenie": (st.get("activity_direction") or ctx.get("activity_direction") or ""),
            "product_query": (st.get("product_query") or ""),
            "quantity": (st.get("quantity") or ""),
            "delivery_address": (st.get("delivery_address") or ""),
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
        "id": row.get("id"),
        "name": (row.get("name") or "").strip() or "Без названия",
        "website": row.get("website_url"),
        "email": row.get("email"),
        "city": row.get("city"),
        "phone": row.get("phone"),
        "source": row.get("source") or "local_db",
    }


def _audit(db_path: Optional[str], request_id: str, event_type: str, payload: Optional[Dict[str, Any]] = None) -> None:
    try:
        insert_audit_event(db_path, request_id=request_id, event_type=event_type, payload=payload)
    except Exception as e:
        logger.warning("audit %s: %s", event_type, e, exc_info=True)


def _llm_system_procurement() -> str:
    return (
        "Отвечай только валидным JSON-объектом без markdown и без пояснений. Поля:\n"
        '- "product_query": string — что закупают;\n'
        '- "city": string — город поставки/поиска;\n'
        '- "region": string — регион (может быть пустым);\n'
        '- "activity_direction": string — отрасль/категория поставщика;\n'
        '- "quantity": string — объём (может быть пустым);\n'
        '- "delivery_address": string — адрес доставки (может быть пустым);\n'
        '- "needs_clarification": boolean — true, если без ответов на вопросы рискованно подбирать поставщиков;\n'
        '- "clarification_questions": array of string — короткие вопросы пользователю (0–5 элементов).\n'
        "Если данных достаточно, needs_clarification=false и clarification_questions=[]."
    )


def _normalize_structured(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    qs = data.get("clarification_questions")
    if not isinstance(qs, list):
        qs = []
    qs = [str(q).strip() for q in qs if str(q).strip()][:8]
    return {
        "product_query": str(data.get("product_query") or data.get("product") or "").strip(),
        "city": str(data.get("city") or "").strip(),
        "region": str(data.get("region") or "").strip(),
        "activity_direction": str(data.get("activity_direction") or data.get("activity") or "").strip(),
        "quantity": str(data.get("quantity") or "").strip(),
        "delivery_address": str(data.get("delivery_address") or "").strip(),
        "needs_clarification": bool(data.get("needs_clarification")),
        "clarification_questions": qs,
    }


def _merge_explicit_fields_into_structured(
    structured: Dict[str, Any],
    *,
    raw_text: str,
    city: str,
    activity_direction: str,
    message: Optional[str],
) -> Dict[str, Any]:
    out = dict(structured)
    if (city or "").strip():
        out["city"] = city.strip()
    if (activity_direction or "").strip():
        out["activity_direction"] = activity_direction.strip()
    hint = (message or "").strip() or (raw_text or "").strip()
    if hint and not (out.get("product_query") or "").strip():
        out["product_query"] = hint[:500]
    return out


def _extract_structured_via_llm(
    *,
    raw_text: str,
    city: str,
    activity_direction: str,
    message: Optional[str],
) -> Dict[str, Any]:
    user_obj = {
        "form_query": (raw_text or "").strip(),
        "form_city": (city or "").strip(),
        "form_activity_direction": (activity_direction or "").strip(),
        "user_message": (message or "").strip(),
    }
    user = "Извлеки поля закупки из входа (JSON):\n" + json.dumps(user_obj, ensure_ascii=False)
    raw = complete_json(_llm_system_procurement(), user, max_tokens=1200)
    try:
        data = json.loads(_strip_json_fence(raw))
    except (json.JSONDecodeError, TypeError, ValueError):
        data = {}
    base = _normalize_structured(data)
    merged = _merge_explicit_fields_into_structured(
        base, raw_text=raw_text, city=city, activity_direction=activity_direction, message=message
    )
    if not merged.get("product_query") and not merged.get("activity_direction"):
        hint = (message or "").strip() or (raw_text or "").strip()
        if hint:
            merged["product_query"] = hint[:500]
    return merged


def _fallback_structured(
    *,
    raw_text: str,
    city: str,
    activity_direction: str,
    message: Optional[str],
) -> Dict[str, Any]:
    hint = (message or "").strip() or (raw_text or "").strip()
    return {
        "product_query": (activity_direction or "").strip() or hint[:500],
        "city": (city or "").strip(),
        "region": "",
        "activity_direction": (activity_direction or "").strip(),
        "quantity": "",
        "delivery_address": "",
        "needs_clarification": False,
        "clarification_questions": [],
        "_extraction": "fallback_no_llm",
    }


def _email_subject_body_from_structured(structured: Dict[str, Any], *, product_fallback: str) -> Tuple[str, str]:
    pq = (structured.get("product_query") or "").strip() or product_fallback
    qty = (structured.get("quantity") or "").strip()
    addr = (structured.get("delivery_address") or "").strip()
    city = (structured.get("city") or "").strip()
    parts_subj = [f"Запрос поставки — {pq or 'без темы'}"]
    if qty:
        parts_subj.append(f"объём: {qty}")
    if city:
        parts_subj.append(city)
    subject = " · ".join(parts_subj)[:500]
    lines = [
        "Здравствуйте.",
        "",
        f"Тема закупки: {pq or '—'}",
    ]
    if qty:
        lines.append(f"Объём / количество: {qty}")
    if addr:
        lines.append(f"Адрес доставки: {addr}")
    elif city:
        lines.append(f"Регион / город: {city}")
    lines.extend(
        [
            "",
            "Просим направить коммерческое предложение по указанным параметрам. "
            "Полный текст заявки хранится в системе. Отправка из тестового контура могла быть отключена.",
        ]
    )
    body = "\n".join(lines)
    return subject, body


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

    def _local_suppliers_structured(self, structured: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Локальные кандидаты: find_for_request + карточки с id для выбора получателей."""
        try:
            with SupplierRepository(db_path=self._db_path) as repo:
                rows = repo.find_for_request(structured or {}, limit=50)
            return [_supplier_card_from_supplier_row(r) for r in rows]
        except sqlite3.OperationalError as e:
            if "no such table" in str(e).lower():
                logger.info("Таблица suppliers отсутствует — локальный список пуст.")
                return []
            raise

    def _upsert_discovered_cards(self, cards: List[Dict[str, Any]], structured: Dict[str, Any]) -> int:
        n = 0
        city_hint = (structured.get("city") or "").strip() or None
        act_hint = (structured.get("activity_direction") or "").strip() or None
        for card in cards:
            payload = dict(card)
            if city_hint and not (payload.get("city") or "").strip():
                payload["city"] = city_hint
            if act_hint and not (payload.get("activity_direction") or "").strip():
                payload["activity_direction"] = act_hint
            try:
                with SupplierRepository(db_path=self._db_path) as repo:
                    repo.upsert_from_discovery(payload)
                n += 1
            except Exception as e:
                logger.debug("upsert_from_discovery пропущен: %s", e)
        return n

    def _run_web_discovery(self, structured: Dict[str, Any], request_id: str) -> List[Dict[str, Any]]:
        product = (
            (structured.get("product_query") or "").strip()
            or (structured.get("activity_direction") or "").strip()
            or (structured.get("raw_text") or "")[:200]
        )
        region = (
            (structured.get("city") or "").strip()
            or (structured.get("region") or "").strip()
        )
        try:
            from business_supplier_finder import BusinessSupplierFinder

            raw = BusinessSupplierFinder().search_suppliers(
                product=product, region=region, quantity=(structured.get("quantity") or "")
            )
            cards = [_supplier_card_from_finder(x) for x in raw]
            upserted = self._upsert_discovered_cards(cards, structured)
            if upserted and request_id:
                _audit(self._db_path, request_id, "web_discovery_upserted", {"count": upserted})
            return cards
        except Exception as e:
            logger.exception("Ошибка веб-поиска поставщиков: %s", e)
            return []

    def _sync_context_from_structured(self, ctx: Dict[str, Any], structured: Dict[str, Any]) -> None:
        ctx["structured"] = structured
        ctx["city"] = (structured.get("city") or "").strip()
        ctx["activity_direction"] = (structured.get("activity_direction") or "").strip()

    def _branch_search_and_message(
        self, request_id: str, structured: Dict[str, Any], context: Dict[str, Any]
    ) -> Tuple[OrchestrationStep, str]:
        local = self._local_suppliers_structured(structured)
        context["local_suppliers"] = local
        context["discovered_suppliers"] = []
        product_fb = (
            (structured.get("product_query") or "").strip()
            or (structured.get("activity_direction") or "").strip()
            or (context.get("raw_text") or "")[:200]
        )
        _audit(
            self._db_path,
            request_id,
            "local_search_completed",
            {"hits": len(local)},
        )
        if local:
            return (
                OrchestrationStep.AWAIT_USER_LOCAL_CONFIRM,
                "Найдены локальные поставщики по параметрам заявки. "
                "Подтвердите, нужно ли подготовить рассылку по этому списку.",
            )
        discovered = self._run_web_discovery(structured, request_id)
        context["discovered_suppliers"] = discovered
        _audit(
            self._db_path,
            request_id,
            "web_discovery_completed",
            {"hits": len(discovered)},
        )
        if discovered:
            return (
                OrchestrationStep.PROPOSE,
                "В локальном каталоге подходящих записей нет. Ниже — предварительный список "
                "из открытых источников (проверьте контакты перед использованием).",
            )
        return (
            OrchestrationStep.PROPOSE,
            "Локальных поставщиков не найдено, а автоматический поиск в сети "
            "сейчас не дал результатов. Попробуйте уточнить город или формулировку запроса.",
        )

    def start_request(
        self,
        raw_text: str = "",
        city: str = "",
        activity_direction: str = "",
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Создаёт заявку: извлечение полей через LLM (complete_json), сохранение structured,
        при необходимости — шаг уточнений; иначе локальный поиск и ветка веб-поиска.
        """
        request_id = str(uuid.uuid4())
        raw_combined = ((message or "").strip() or (raw_text or "").strip())
        extracted = _extract_structured_via_llm(
            raw_text=raw_text,
            city=city,
            activity_direction=activity_direction,
            message=message,
        )
        if not (extracted.get("product_query") or extracted.get("activity_direction") or extracted.get("city")):
            extracted = _fallback_structured(
                raw_text=raw_text,
                city=city,
                activity_direction=activity_direction,
                message=message,
            )

        context: Dict[str, Any] = {
            "raw_text": raw_text,
            "message": message or "",
            "city": city,
            "activity_direction": activity_direction,
            "local_suppliers": [],
            "discovered_suppliers": [],
            "email_draft": None,
            "ui_message": "",
            "send_confirmed": None,
            "clarification_questions": list(extracted.get("clarification_questions") or []),
        }
        self._sync_context_from_structured(context, extracted)

        needs = bool(extracted.get("needs_clarification")) and bool(context["clarification_questions"])
        if needs:
            step = OrchestrationStep.AWAIT_CLARIFICATION
            msg = (
                "Нужны уточнения по заявке. Пожалуйста, ответьте на вопросы ниже — "
                "после этого подбор поставщиков продолжится автоматически."
            )
            context["ui_message"] = msg
            self._save_session(request_id, step, context)
            try:
                insert_user_request(
                    self._db_path,
                    request_id=request_id,
                    raw_query=raw_combined or (extracted.get("product_query") or "—"),
                    city=(extracted.get("city") or "").strip() or None,
                    activity_direction=(extracted.get("activity_direction") or "").strip() or None,
                    status=step.value,
                    structured_json=None,
                )
                update_user_request_structured(
                    self._db_path, request_id, extracted, sync_geo_columns=True
                )
            except Exception as e:
                logger.warning("Не удалось записать user_requests: %s", e, exc_info=True)
            _audit(self._db_path, request_id, "request_created", {"step": step.value})
            _audit(
                self._db_path,
                request_id,
                "clarification_requested",
                {"questions": context["clarification_questions"]},
            )
            try:
                update_user_request_status(self._db_path, request_id, step.value)
            except Exception as e:
                logger.warning("Не удалось обновить user_requests.status: %s", e, exc_info=True)
            return {
                "request_id": request_id,
                "step": step.value,
                "local_suppliers": [],
                "message_for_user": msg,
                "clarification_questions": context["clarification_questions"],
                "structured": extracted,
            }

        step, msg = self._branch_search_and_message(request_id, extracted, context)
        context["ui_message"] = msg
        self._save_session(request_id, step, context)

        try:
            insert_user_request(
                self._db_path,
                request_id=request_id,
                raw_query=raw_combined or (extracted.get("product_query") or "—"),
                city=(extracted.get("city") or "").strip() or None,
                activity_direction=(extracted.get("activity_direction") or "").strip() or None,
                status=step.value,
                structured_json=None,
            )
            update_user_request_structured(
                self._db_path, request_id, extracted, sync_geo_columns=True
            )
        except Exception as e:
            logger.warning("Не удалось записать user_requests: %s", e, exc_info=True)

        _audit(self._db_path, request_id, "request_created", {"step": step.value})

        out: Dict[str, Any] = {
            "request_id": request_id,
            "step": step.value,
            "local_suppliers": context["local_suppliers"],
            "message_for_user": msg,
            "structured": extracted,
        }
        if not context["local_suppliers"]:
            out["discovered_suppliers"] = context["discovered_suppliers"]
        return out

    def submit_clarification(self, request_id: str, answers: Any) -> Dict[str, Any]:
        """Принимает ответы на вопросы уточнения, обновляет structured, повторяет локальный поиск."""
        session = self._load_session(request_id)
        if not session or session["step"] != OrchestrationStep.AWAIT_CLARIFICATION.value:
            return {
                "request_id": request_id,
                "step": session["step"] if session else "UNKNOWN",
                "ok": False,
                "message_for_user": "Заявка не найдена или уточнения сейчас не ожидаются.",
            }

        ctx = session["context"]
        structured: Dict[str, Any] = dict(ctx.get("structured") or {})
        questions: List[str] = list(ctx.get("clarification_questions") or [])

        norm_answers: Dict[str, str] = {}
        if isinstance(answers, dict):
            for k, v in answers.items():
                norm_answers[str(k)] = str(v).strip()
        elif isinstance(answers, list):
            for i, q in enumerate(questions):
                if i < len(answers):
                    norm_answers[f"q{i}"] = str(answers[i]).strip()

        merged_responses = dict(structured.get("clarification_responses") or {})
        merged_responses.update(norm_answers)
        structured["clarification_responses"] = merged_responses
        structured["needs_clarification"] = False
        structured["clarification_questions"] = []

        try:
            append_clarification(
                self._db_path,
                request_id,
                {"questions": questions, "answers": norm_answers},
            )
        except Exception as e:
            logger.warning("append_clarification: %s", e, exc_info=True)
        _audit(self._db_path, request_id, "clarification_submitted", {"keys": list(norm_answers.keys())})

        ctx["clarification_questions"] = []
        self._sync_context_from_structured(ctx, structured)

        step, msg = self._branch_search_and_message(request_id, structured, ctx)
        ctx["ui_message"] = msg
        self._save_session(request_id, step, ctx)

        try:
            update_user_request_structured(
                self._db_path, request_id, structured, sync_geo_columns=True
            )
            update_user_request_status(self._db_path, request_id, step.value)
        except Exception as e:
            logger.warning("Не удалось обновить user_requests: %s", e, exc_info=True)

        out: Dict[str, Any] = {
            "request_id": request_id,
            "step": step.value,
            "ok": True,
            "message_for_user": msg,
            "local_suppliers": ctx["local_suppliers"],
            "structured": structured,
        }
        if not ctx["local_suppliers"]:
            out["discovered_suppliers"] = ctx.get("discovered_suppliers", [])
        return out

    def submit_recipient_selection(self, request_id: str, supplier_ids: List[str]) -> Dict[str, Any]:
        """Фильтрация локальных получателей перед подтверждением отправки (шаг AWAIT_RECIPIENT_SELECTION)."""
        session = self._load_session(request_id)
        if not session or session["step"] != OrchestrationStep.AWAIT_RECIPIENT_SELECTION.value:
            return {
                "request_id": request_id,
                "step": session["step"] if session else "UNKNOWN",
                "ok": False,
                "message_for_user": "Сейчас не требуется выбор получателей для этой заявки.",
            }

        ctx = session["context"]
        want = {str(x).strip() for x in supplier_ids if str(x).strip()}
        candidates: List[Dict[str, Any]] = list(ctx.get("recipient_candidates") or [])
        picked = [c for c in candidates if str(c.get("id") or "").strip() in want]
        if not picked:
            return {
                "request_id": request_id,
                "step": OrchestrationStep.AWAIT_RECIPIENT_SELECTION.value,
                "ok": False,
                "message_for_user": "Выберите хотя бы одного поставщика из списка (по id).",
            }
        emails = [s.get("email") for s in picked if s.get("email")]
        structured: Dict[str, Any] = dict(ctx.get("structured") or {})
        product_fb = (
            (structured.get("product_query") or "").strip()
            or (structured.get("activity_direction") or "").strip()
            or (ctx.get("raw_text") or "")[:200]
        )
        subject, body_preview = _email_subject_body_from_structured(structured, product_fallback=product_fb)
        ctx["email_draft"] = {
            "stub": True,
            "recipients": emails,
            "subject": subject,
            "body_preview": body_preview,
        }
        ctx["local_suppliers"] = picked
        step = OrchestrationStep.AWAIT_SEND_CONFIRM
        msg = (
            "Список получателей обновлён по вашему выбору. "
            "Подтвердите отправку писем, когда будете готовы."
        )
        ctx["ui_message"] = msg
        self._save_session(request_id, step, ctx)

        try:
            update_user_request_selected_supplier_ids(
                self._db_path, request_id, [str(c.get("id")) for c in picked if c.get("id")]
            )
            update_user_request_status(self._db_path, request_id, step.value)
            ed = ctx["email_draft"]
            insert_outbound_email_drafts(
                self._db_path,
                request_id=request_id,
                recipients=list(ed.get("recipients") or []),
                subject=(ed.get("subject") or "").strip() or "Запрос поставщику",
                body=(ed.get("body_preview") or "").strip(),
            )
        except Exception as e:
            logger.warning("persist recipient selection: %s", e, exc_info=True)

        _audit(self._db_path, request_id, "recipients_selected", {"count": len(picked)})
        return {
            "request_id": request_id,
            "step": step.value,
            "ok": True,
            "message_for_user": msg,
            "email_draft": ctx.get("email_draft"),
        }

    def user_confirm_local_send(self, request_id: str, yes: bool) -> Dict[str, Any]:
        """
        Ответ пользователя на предложение рассылки локальным поставщикам.
        При согласии — выбор получателей (если несколько e-mail) или сразу черновик письма.
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
        structured: Dict[str, Any] = dict(ctx.get("structured") or {})
        product_fb = (
            (structured.get("product_query") or "").strip()
            or (structured.get("activity_direction") or "").strip()
            or (ctx.get("raw_text") or "")[:200]
        )

        if yes:
            with_email = [
                x
                for x in (ctx.get("local_suppliers") or [])
                if x.get("email") and str(x.get("email")).strip()
            ]
            multi = len(with_email) > 1
            if multi:
                ctx["recipient_candidates"] = with_email
                ctx["email_draft"] = None
                step = OrchestrationStep.AWAIT_RECIPIENT_SELECTION
                msg = (
                    "Выберите одного или нескольких поставщиков с e-mail для рассылки, "
                    "затем подтвердите черновик письма."
                )
                _audit(
                    self._db_path,
                    request_id,
                    "recipient_selection_required",
                    {"candidates": len(with_email)},
                )
            else:
                emails = [s.get("email") for s in (ctx.get("local_suppliers") or []) if s.get("email")]
                subject, body_preview = _email_subject_body_from_structured(
                    structured, product_fallback=product_fb
                )
                ctx["email_draft"] = {
                    "stub": True,
                    "recipients": emails,
                    "subject": subject,
                    "body_preview": body_preview,
                }
                step = OrchestrationStep.AWAIT_SEND_CONFIRM
                msg = (
                    "Черновик письма для локальных поставщиков подготовлен (отправка ещё не выполнялась). "
                    "Подтвердите отправку через API отправки писем, когда будете готовы."
                )
                _audit(self._db_path, request_id, "email_draft_created", {"recipients": len(emails)})
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
            discovered = self._run_web_discovery(structured, request_id)
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
            _audit(self._db_path, request_id, "local_confirm_declined_web", {"web_hits": len(discovered)})

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
            if step == OrchestrationStep.AWAIT_SEND_CONFIRM:
                result["email_draft"] = ctx.get("email_draft")
            else:
                result["recipient_candidates"] = ctx.get("recipient_candidates")
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
            _audit(self._db_path, request_id, "send_skipped", {"execute": False})

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

        _audit(
            self._db_path,
            request_id,
            "send_attempted",
            {"recipients": len(recipients), "execute": True},
        )

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

        _audit(
            self._db_path,
            request_id,
            "send_completed",
            {"sent": sum(1 for x in results if x.get("sent")), "total": len(results)},
        )

        return {
            "request_id": request_id,
            "step": step.value,
            "ok": True,
            "message_for_user": msg,
            "email_send_results": results,
        }

    def _suppliers_for_api(self, step_value: str, ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        if step_value == OrchestrationStep.AWAIT_CLARIFICATION.value:
            return []
        if step_value == OrchestrationStep.AWAIT_RECIPIENT_SELECTION.value:
            return list(ctx.get("recipient_candidates") or [])
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
        st = ctx.get("structured")
        if isinstance(st, dict) and st:
            out["structured"] = st
        if step == OrchestrationStep.AWAIT_CLARIFICATION.value:
            out["clarification_questions"] = list(ctx.get("clarification_questions") or [])
        if step == OrchestrationStep.AWAIT_RECIPIENT_SELECTION.value:
            out["recipient_candidates"] = list(ctx.get("recipient_candidates") or [])
        if step == OrchestrationStep.AWAIT_SEND_CONFIRM.value:
            out["email_draft"] = ctx.get("email_draft")
        if step == OrchestrationStep.DONE.value and ctx.get("email_send_results") is not None:
            out["email_send_results"] = ctx.get("email_send_results")
        return out


_default_orchestrator = RequestOrchestrator()


def start_request(
    query: str = "",
    city: str = "",
    activity_direction: str = "",
    message: Optional[str] = None,
) -> Dict[str, Any]:
    """Обёртка для Flask: query/message → raw_text и опционально отдельное сообщение для LLM."""
    r = _default_orchestrator.start_request(
        raw_text=(query or "").strip(),
        city=city or "",
        activity_direction=activity_direction or "",
        message=(message.strip() if message else None),
    )
    suppliers: List[Dict[str, Any]] = list(r.get("local_suppliers") or [])
    if not suppliers and r.get("discovered_suppliers"):
        suppliers = list(r["discovered_suppliers"])
    out: Dict[str, Any] = {
        "request_id": r["request_id"],
        "step": r["step"],
        "message": r.get("message_for_user") or "",
        "suppliers": suppliers,
        "query": (query or "").strip(),
        "city": (city or "").strip(),
        "activity_direction": (activity_direction or "").strip(),
        "send_confirmed": None,
    }
    if r.get("structured") is not None:
        out["structured"] = r["structured"]
    if r.get("clarification_questions"):
        out["clarification_questions"] = r["clarification_questions"]
    return out


def submit_clarification_answers(request_id: str, answers: Any) -> Optional[Dict[str, Any]]:
    session = _default_orchestrator._load_session(request_id)
    if not session:
        return None
    r = _default_orchestrator.submit_clarification(request_id, answers)
    if not r.get("ok"):
        return {"_error": True, "message": r.get("message_for_user") or "invalid state"}
    return _default_orchestrator.get_api_state(request_id)


def submit_recipient_selection_state(request_id: str, supplier_ids: List[str]) -> Optional[Dict[str, Any]]:
    session = _default_orchestrator._load_session(request_id)
    if not session:
        return None
    r = _default_orchestrator.submit_recipient_selection(request_id, supplier_ids)
    if not r.get("ok"):
        return {"_error": True, "message": r.get("message_for_user") or "invalid state"}
    return _default_orchestrator.get_api_state(request_id)


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
            message=None,
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
            message=None,
        )
        print("start_request (web):", json.dumps(r2, ensure_ascii=False, indent=2))
