"""Юнит-тесты для routes.api_security (path_requires_api_key, extract_provided_key)."""

from flask import Flask

from routes.api_security import extract_provided_key, path_requires_api_key


def _minimal_app() -> Flask:
    return Flask(__name__)


def test_path_requires_api_key_true_for_v2_and_search_paths():
    assert path_requires_api_key("/api/v2/foo") is True
    assert path_requires_api_key("/api/v1/search") is True
    assert path_requires_api_key("/api/v1/search/uuid") is True


def test_path_requires_api_key_false_for_health_root_and_html_search():
    assert path_requires_api_key("/api/v1/health") is False
    assert path_requires_api_key("/") is False
    assert path_requires_api_key("/search") is False


def test_extract_provided_key_from_x_api_key_header():
    app = _minimal_app()
    with app.test_request_context("/", headers={"X-API-Key": "  secret-key  "}):
        assert extract_provided_key() == "secret-key"


def test_extract_provided_key_from_authorization_bearer():
    app = _minimal_app()
    with app.test_request_context(
        "/",
        headers={"Authorization": "Bearer my-bearer-token"},
    ):
        assert extract_provided_key() == "my-bearer-token"


def test_extract_provided_key_prefers_x_api_key_over_bearer():
    app = _minimal_app()
    with app.test_request_context(
        "/",
        headers={
            "X-API-Key": "from-header",
            "Authorization": "Bearer from-bearer",
        },
    ):
        assert extract_provided_key() == "from-header"


def test_extract_provided_key_empty_without_credentials():
    app = _minimal_app()
    with app.test_request_context("/"):
        assert extract_provided_key() == ""
