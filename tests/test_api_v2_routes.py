"""HTTP-тесты blueprint API v2: Flask test_client и unittest.mock.patch (без Redis/БД оркестрации)."""

import json
import unittest
from unittest.mock import patch

import web_app


@patch("web_app.enforce_api_key", return_value=None)
class TestApiV2Routes(unittest.TestCase):
    """Патч API-ключа, чтобы тесты не зависели от переменной окружения API_KEY."""

    def setUp(self):
        web_app.app.config["TESTING"] = True
        self.client = web_app.app.test_client()

    @patch("routes.orchestration_routes.start_request")
    def test_post_requests_returns_201_and_request_id(self, mock_start, _mock_enforce):
        mock_start.return_value = {
            "request_id": "req-test-1",
            "step": "awaiting_confirm_local",
            "message": "Список готов",
            "suppliers": [{"name": "Поставщик А", "relevance_score": 1}],
        }
        resp = self.client.post(
            "/api/v2/requests",
            data=json.dumps(
                {"query": "металлопрокат", "city": "Москва", "activity_direction": "опт"}
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        body = resp.get_json()
        self.assertIsNotNone(body)
        self.assertEqual(body.get("request_id"), "req-test-1")
        mock_start.assert_called_once_with("металлопрокат", "Москва", "опт", message=None)

    @patch("routes.orchestration_routes.get_request_state")
    def test_get_request_returns_200(self, mock_get, _mock_enforce):
        mock_get.return_value = {
            "request_id": "abc-123",
            "step": "done",
            "message": "Готово",
        }
        resp = self.client.get("/api/v2/requests/abc-123")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertIsNotNone(body)
        self.assertEqual(body.get("request_id"), "abc-123")

    @patch("routes.orchestration_routes.get_request_state")
    def test_get_request_missing_returns_404_unified_error(self, mock_get, _mock_enforce):
        mock_get.return_value = None
        resp = self.client.get("/api/v2/requests/missing")
        self.assertEqual(resp.status_code, 404)
        body = resp.get_json()
        self.assertIsNotNone(body)
        self.assertEqual(body.get("error", {}).get("code"), "not_found")

    def test_post_requests_empty_query_returns_400_validation(self, _mock_enforce):
        resp = self.client.post(
            "/api/v2/requests",
            data=json.dumps({"query": "", "city": "", "activity_direction": ""}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        body = resp.get_json()
        self.assertIsNotNone(body)
        self.assertEqual(body.get("error", {}).get("code"), "validation_error")

    @patch("routes.orchestration_routes.start_request")
    def test_post_requests_message_only_ok(self, mock_start, _mock_enforce):
        mock_start.return_value = {
            "request_id": "req-msg-1",
            "step": "AWAIT_CLARIFICATION",
            "message": "Нужны уточнения",
            "suppliers": [],
            "clarification_questions": ["Город?"],
        }
        resp = self.client.post(
            "/api/v2/requests",
            data=json.dumps({"message": "Нужен опт муки 10т", "city": ""}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        mock_start.assert_called_once_with("", "", "", message="Нужен опт муки 10т")
