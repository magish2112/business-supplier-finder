"""
Защита JSON API ключом (A1): если задан API_KEY, запросы к указанным путям
требуют заголовок X-API-Key или Authorization: Bearer <ключ>.

HTML-страницы (/, /search, /flow и т.д.) не требуют ключа.
"""

from __future__ import annotations

import os
from typing import Optional

from flask import Response, jsonify, make_response, request


def expected_api_key() -> str:
    return os.getenv("API_KEY", "").strip()


def api_key_required_at_startup() -> bool:
    return os.getenv("API_KEY_REQUIRED", "").strip().lower() in ("1", "true", "yes", "on")


def extract_provided_key() -> str:
    h = (request.headers.get("X-API-Key") or "").strip()
    if h:
        return h
    auth = request.authorization
    if auth and auth.type and auth.type.lower() == "bearer" and auth.token:
        return (auth.token or "").strip()
    return ""


def path_requires_api_key(path: str) -> bool:
    """Пути, для которых при ненастроенном API_KEY в .env ключ не проверяется (dev)."""
    if path.startswith("/api/v1/health") or path.startswith("/api/v1/config"):
        return False
    if path.startswith("/api/v2/"):
        return True
    if path.startswith("/api/v1/search"):
        return True
    if path.startswith("/api/v1/suppliers"):
        return True
    if path.startswith("/api/v1/stats"):
        return True
    if path.startswith("/api/quick_search/"):
        return True
    if path.startswith("/api/saved_search/"):
        return True
    return False


def enforce_api_key() -> Optional[Response]:
    """
    Вызывать из @app.before_request.
    Возвращает Response 401 при отказе, иначе None.
    """
    exp = expected_api_key()
    if not exp:
        return None
    if not path_requires_api_key(request.path):
        return None
    if extract_provided_key() == exp:
        return None
    body = {"error": {"code": "unauthorized", "message": "Неверный или отсутствующий API-ключ"}}
    return make_response(jsonify(body), 401)


def validate_startup_security() -> None:
    """Вызов при старте приложения: жёсткое требование API_KEY в проде."""
    if api_key_required_at_startup() and not expected_api_key():
        raise RuntimeError(
            "Задан API_KEY_REQUIRED=true, но переменная API_KEY пуста. "
            "Установите API_KEY или отключите API_KEY_REQUIRED."
        )
