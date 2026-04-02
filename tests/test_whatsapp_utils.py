"""
Tests for utils/whatsapp.py — parsing functions only (no HTTP calls).
"""
import pytest
from tests.conftest import make_whatsapp_webhook, make_status_webhook
from utils.whatsapp import parse_incoming, parse_lead_request


class TestParseIncoming:
    def test_extracts_sender_and_text(self):
        payload = make_whatsapp_webhook("Industry: Plumbers\nCity: Cape Town")
        result  = parse_incoming(payload)

        assert result["from"] == "+27821234567"
        assert result["text"] == "Industry: Plumbers\nCity: Cape Town"
        assert result["message_id"] == "wamid.test123"

    def test_returns_none_for_status_update(self):
        payload = make_status_webhook()
        # Status webhooks have no "messages" key → parse_incoming returns None
        result = parse_incoming(payload)
        assert result is None

    def test_returns_none_for_malformed_payload(self):
        assert parse_incoming({}) is None
        assert parse_incoming({"entry": []}) is None
        assert parse_incoming({"entry": [{"changes": []}]}) is None

    def test_strips_whitespace_from_text(self):
        payload = make_whatsapp_webhook("  hello world  ")
        result  = parse_incoming(payload)
        assert result["text"] == "hello world"

    def test_handles_different_sender(self):
        payload = make_whatsapp_webhook("hi", sender="+27839876543")
        result  = parse_incoming(payload)
        assert result["from"] == "+27839876543"


class TestParseLeadRequest:
    def test_parses_valid_request(self):
        text   = "Industry: Plumbers\nCity: Cape Town"
        result = parse_lead_request(text)

        assert result == {"industry": "Plumbers", "city": "Cape Town"}

    def test_parses_request_with_extra_whitespace(self):
        text   = "  Industry:   Electricians  \n  City:   Johannesburg  "
        result = parse_lead_request(text)

        assert result["industry"] == "Electricians"
        assert result["city"] == "Johannesburg"

    def test_returns_none_when_industry_missing(self):
        text   = "City: Cape Town"
        result = parse_lead_request(text)
        assert result is None

    def test_returns_none_when_city_missing(self):
        text   = "Industry: Plumbers"
        result = parse_lead_request(text)
        assert result is None

    def test_returns_none_for_free_text(self):
        assert parse_lead_request("find me plumbers") is None
        assert parse_lead_request("hello") is None
        assert parse_lead_request("") is None

    def test_case_insensitive_keys(self):
        text   = "industry: Plumbers\ncity: Cape Town"
        result = parse_lead_request(text)
        assert result == {"industry": "Plumbers", "city": "Cape Town"}

    def test_city_with_spaces(self):
        text   = "Industry: Restaurants\nCity: East London"
        result = parse_lead_request(text)
        assert result["city"] == "East London"

    def test_industry_with_spaces(self):
        text   = "Industry: Hair Salons\nCity: Durban"
        result = parse_lead_request(text)
        assert result["industry"] == "Hair Salons"
