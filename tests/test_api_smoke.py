"""Дымовые проверки API через Flask test_client (без живого сервера)."""

from web_app import app


def test_api_health():
    app.config["TESTING"] = True
    with app.test_client() as client:
        r = client.get("/api/v1/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data is not None
    assert data.get("status") == "healthy"


def test_api_unknown_route_unified_error():
    app.config["TESTING"] = True
    with app.test_client() as client:
        r = client.get("/api/nope")
    assert r.status_code == 404
    data = r.get_json()
    assert data is not None
    assert data.get("error", {}).get("code") == "not_found"
