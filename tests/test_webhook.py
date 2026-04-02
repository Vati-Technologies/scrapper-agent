"""
Tests for main.py — FastAPI webhook endpoints.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from tests.conftest import make_whatsapp_webhook, make_status_webhook


@pytest.fixture
def client():
    with (
        patch("main.validate_config"),
        patch("main.run_migrations"),
    ):
        from main import app
        return TestClient(app, raise_server_exceptions=False)


class TestWebhookVerification:
    def test_valid_verification_returns_challenge(self, client):
        response = client.get("/webhook", params={
            "hub.mode":         "subscribe",
            "hub.verify_token": "test-verify-token",
            "hub.challenge":    "abc123",
        })
        assert response.status_code == 200
        assert response.text == "abc123"

    def test_wrong_verify_token_returns_403(self, client):
        response = client.get("/webhook", params={
            "hub.mode":         "subscribe",
            "hub.verify_token": "wrong-token",
            "hub.challenge":    "abc123",
        })
        assert response.status_code == 403

    def test_missing_mode_returns_403(self, client):
        response = client.get("/webhook", params={
            "hub.verify_token": "test-verify-token",
            "hub.challenge":    "abc123",
        })
        assert response.status_code == 403


class TestHealthCheck:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestIncomingMessages:
    def test_status_update_is_ignored(self, client):
        payload  = make_status_webhook()
        response = client.post("/webhook", json=payload)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_new_client_gets_onboarding_message(self, client):
        payload = make_whatsapp_webhook("Industry: Plumbers\nCity: Cape Town")

        with (
            patch("main.get_client_by_whatsapp", return_value=None),
            patch("main.create_client"),
            patch("main.send_message") as mock_send,
        ):
            response = client.post("/webhook", json=payload)

        assert response.status_code == 200
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        assert "Welcome" in call_args[1]

    def test_client_over_daily_limit_gets_limit_message(self, client):
        payload = make_whatsapp_webhook("Industry: Plumbers\nCity: Cape Town")

        with (
            patch("main.get_client_by_whatsapp", return_value={"id": "client_001"}),
            patch("main.has_used_daily_request",  return_value=True),
            patch("main.send_message") as mock_send,
        ):
            response = client.post("/webhook", json=payload)

        assert response.status_code == 200
        call_args = mock_send.call_args[0]
        assert "already received" in call_args[1]

    def test_bad_format_gets_format_error(self, client):
        payload = make_whatsapp_webhook("find me some plumbers please")

        with (
            patch("main.get_client_by_whatsapp", return_value={"id": "client_001"}),
            patch("main.has_used_daily_request",  return_value=False),
            patch("main.send_message") as mock_send,
        ):
            response = client.post("/webhook", json=payload)

        assert response.status_code == 200
        call_args = mock_send.call_args[0]
        assert "didn't understand" in call_args[1]

    def test_valid_request_triggers_pipeline(self, client):
        payload = make_whatsapp_webhook("Industry: Plumbers\nCity: Cape Town")

        with (
            patch("main.get_client_by_whatsapp", return_value={"id": "client_001"}),
            patch("main.has_used_daily_request",  return_value=False),
            patch("main.save_request",            return_value=42),
            patch("main.send_message")            as mock_send,
            patch("main.run_pipeline"),
        ):
            response = client.post("/webhook", json=payload)

        assert response.status_code == 200
        # Acknowledgement sent
        call_args = mock_send.call_args[0]
        assert "Plumbers" in call_args[1]
        assert "Cape Town" in call_args[1]

    def test_malformed_body_returns_ok(self, client):
        response = client.post("/webhook", json={})
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
