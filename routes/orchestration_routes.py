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
)

orchestration_bp = Blueprint(
    "orchestration",
    __name__,
    url_prefix="",
)


@orchestration_bp.route("/flow")
def flow_page():
    return render_template("orchestration.html")


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
    if not str(query).strip():
        return api_error("validation_error", "Поле query обязательно", 400)
    payload = start_request(query, city, activity_direction)
    return jsonify(payload), 201


@orchestration_bp.route("/api/v2/requests/<request_id>", methods=["GET"])
def api_v2_get_request(request_id: str):
    state = get_request_state(request_id)
    if state is None:
        return api_error("not_found", "Заявка не найдена", 404)
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
