"""Тесты integrations.site_product_check и маршрута /api/v2/check-site-product."""

import importlib.util
import json
import unittest
from unittest.mock import MagicMock, patch

import pytest

from integrations import site_product_check

_FLASK = importlib.util.find_spec("flask") is not None


@pytest.fixture
def clear_site_env(monkeypatch):
    monkeypatch.delenv("SITE_CHECK_ENABLED", raising=False)
    monkeypatch.delenv("SITE_CHECK_TIMEOUT_SEC", raising=False)
    monkeypatch.delenv("SITE_CHECK_MAX_CHARS", raising=False)


def test_check_product_mention_disabled_by_default(clear_site_env, monkeypatch):
    monkeypatch.delenv("SITE_CHECK_ENABLED", raising=False)
    out = site_product_check.check_product_mentioned("https://example.com", "гайки")
    assert out["ok"] is False
    assert out["error"] == "site_check_disabled"
    assert out["snippet"] is None


@patch("integrations.site_product_check.complete_json")
@patch("integrations.site_product_check.fetch_url_text")
def test_check_product_mentioned_success(mock_fetch, mock_complete, monkeypatch):
    monkeypatch.setenv("SITE_CHECK_ENABLED", "true")
    mock_fetch.return_value = "ООО Ромашка продаёт метизы и гайки оптом."
    mock_complete.return_value = json.dumps(
        {
            "mentioned": True,
            "confidence": "high",
            "evidence": "гайки оптом",
        }
    )
    out = site_product_check.check_product_mentioned("https://shop.test/", "гайки")
    assert out["ok"] is True
    assert out["error"] is None
    assert out["mentioned"] is True
    assert "гайки" in (out.get("snippet") or "")
    mock_fetch.assert_called_once()
    mock_complete.assert_called_once()


@patch("integrations.site_product_check.requests.get")
def test_fetch_url_text_strips_scripts(mock_get, monkeypatch):
    monkeypatch.setenv("SITE_CHECK_MAX_CHARS", "10000")
    mock_resp = MagicMock()
    mock_resp.text = (
        "<html><head><style>.x{}</style></head><body>"
        "<script>alert(1)</script><p>Hello  world</p></body></html>"
    )
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    text = site_product_check.fetch_url_text("https://example.com/page", timeout=3.0)
    assert "alert" not in text
    assert "Hello" in text
    mock_get.assert_called_once()


@unittest.skipUnless(_FLASK, "flask не установлен")
class TestAvailabilityRoute(unittest.TestCase):
    """Минимальное приложение Flask — без импорта web_app (тяжёлые сайд-эффекты)."""

    def setUp(self):
        from flask import Flask

        from routes.availability_routes import availability_bp

        app = Flask(__name__)
        app.register_blueprint(availability_bp)
        app.config["TESTING"] = True
        self.client = app.test_client()

    @patch("routes.availability_routes.check_product_mentioned")
    def test_post_check_site_product_returns_json(self, mock_check):
        mock_check.return_value = {
            "ok": True,
            "snippet": "demo",
            "error": None,
            "mentioned": False,
            "confidence": "low",
            "evidence": "",
        }
        resp = self.client.post(
            "/api/v2/check-site-product",
            data=json.dumps({"url": "https://a.ru", "product": "болты"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertIsNotNone(body)
        self.assertTrue(body.get("ok"))
        mock_check.assert_called_once_with("https://a.ru", "болты")

    def test_post_check_site_product_validation(self):
        resp = self.client.post(
            "/api/v2/check-site-product",
            data=json.dumps({"url": "", "product": ""}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
