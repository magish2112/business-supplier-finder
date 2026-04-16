"""Опциональные API проверки доступности / контента (v2)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from integrations.site_product_check import check_product_mentioned
from routes.api_errors import api_error

availability_bp = Blueprint("availability", __name__, url_prefix="")


@availability_bp.route("/api/v2/check-site-product", methods=["POST"])
def api_v2_check_site_product():
    data = request.get_json(silent=True) or {}
    url = str(data.get("url") or "").strip()
    product = str(data.get("product") or "").strip()
    if not url or not product:
        return api_error("validation_error", "Поля url и product обязательны", 400)
    result = check_product_mentioned(url, product)
    return jsonify(result)
