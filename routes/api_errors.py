"""Единый JSON-формат ошибок API: {\"error\": {\"code\", \"message\"}}."""

from __future__ import annotations

from flask import Response, jsonify, make_response


def api_error(code: str, message: str, http_status: int = 400) -> Response:
    return make_response(jsonify({"error": {"code": code, "message": message}}), http_status)
