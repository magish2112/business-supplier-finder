"""HTTP API v2 и страница потока оркестрации."""

import os
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request

from routes.api_errors import api_error
from orchestration.service import (
    confirm_local,
    get_request_state,
    send_confirmed_emails,
    start_request,
    submit_clarification_answers,
    submit_recipient_selection_state,
)

orchestration_bp = Blueprint(
    "orchestration",
    __name__,
    url_prefix="",
)


@orchestration_bp.route("/flow")
def flow_page():
    return render_template("orchestration.html")


@orchestration_bp.route("/flow-react")
def flow_react_page():
    """SPA (Vite + React + Tailwind v4): собрать `cd frontend && npm run build`."""
    return render_template("orch_react.html")


@orchestration_bp.route("/api/v2/llm-config", methods=["GET"])
def api_v2_llm_config():
    """Публичные сведения о провайдере LLM и Excel (A2: без абсолютного пути к файлу)."""
    from integrations.llm_config import describe_active_provider, load_llm_settings

    s = load_llm_settings()
    excel_raw = os.getenv("SUPPLIER_EXCEL_PATH", str(Path("data") / "baza postavshiki.xlsx"))
    excel_path = Path(excel_raw)
    if not excel_path.is_absolute():
        root = Path(__file__).resolve().parents[1]
        excel_path = (root / excel_path).resolve()
    exists = excel_path.is_file()
    return jsonify(
        {
            "llm_provider": s.provider_normalized,
            "llm_description": describe_active_provider(),
            "supplier_excel_filename": excel_path.name,
            "supplier_excel_exists": exists,
            "supplier_excel_configured": bool(excel_raw.strip()),
        }
    )


@orchestration_bp.route("/api/v2/requests", methods=["POST"])
def api_v2_create_request():
    data = request.get_json(silent=True) or {}
    query = data.get("query", "")
    city = data.get("city", "")
    activity_direction = data.get("activity_direction", "")
    message = data.get("message")
    if isinstance(message, str):
        message = message.strip() or None
    else:
        message = None
    q = str(query).strip() if query is not None else ""
    if not q and not message:
        return api_error(
            "validation_error",
            "Укажите поле query и/или message",
            400,
        )
    payload = start_request(q, city, activity_direction, message=message)
    return jsonify(payload), 201


@orchestration_bp.route("/api/v2/requests/<request_id>", methods=["GET"])
def api_v2_get_request(request_id: str):
    state = get_request_state(request_id)
    if state is None:
        return api_error("not_found", "Заявка не найдена", 404)
    return jsonify(state)


@orchestration_bp.route("/api/v2/requests/<request_id>/clarify", methods=["POST"])
def api_v2_clarify(request_id: str):
    data = request.get_json(silent=True) or {}
    if "answers" not in data:
        return api_error("validation_error", "Требуется поле answers (объект или массив)", 400)
    state = submit_clarification_answers(request_id, data.get("answers"))
    if state is None:
        return api_error("not_found", "Заявка не найдена", 404)
    if state.get("_error"):
        return api_error("invalid_state", state.get("message", "Недопустимое состояние"), 400)
    return jsonify(state)


@orchestration_bp.route("/api/v2/requests/<request_id>/recipients", methods=["POST", "PATCH"])
def api_v2_select_recipients(request_id: str):
    data = request.get_json(silent=True) or {}
    ids = data.get("supplier_ids")
    if ids is None:
        ids = data.get("selected_supplier_ids")
    if not isinstance(ids, list) or not ids:
        return api_error(
            "validation_error",
            "Требуется непустой массив supplier_ids (или selected_supplier_ids)",
            400,
        )
    state = submit_recipient_selection_state(request_id, [str(x) for x in ids])
    if state is None:
        return api_error("not_found", "Заявка не найдена", 404)
    if state.get("_error"):
        return api_error("invalid_state", state.get("message", "Недопустимое состояние"), 400)
    return jsonify(state)


@orchestration_bp.route("/api/v2/requests/<request_id>/confirm-local", methods=["POST"])
def api_v2_confirm_local(request_id: str):
    data = request.get_json(silent=True) or {}
    if "send" not in data:
        return api_error("validation_error", "Требуется поле send (boolean)", 400)
    send = bool(data["send"])
    state = confirm_local(request_id, send)
    if state is None:
        return api_error("not_found", "Заявка не найдена", 404)
    if state.get("_error"):
        return api_error("invalid_state", state.get("message", "Недопустимое состояние"), 400)
    return jsonify(state)


@orchestration_bp.route("/api/v2/requests/<request_id>/send-emails", methods=["POST"])
def api_v2_send_emails(request_id: str):
    data = request.get_json(silent=True) or {}
    if "execute" not in data:
        return api_error("validation_error", "Требуется поле execute (boolean)", 400)
    execute = bool(data["execute"])
    state = send_confirmed_emails(request_id, execute)
    if state is None:
        return api_error("not_found", "Заявка не найдена", 404)
    if state.get("_error"):
        return api_error("invalid_state", state.get("message", "Недопустимое состояние"), 400)
    return jsonify(state)
