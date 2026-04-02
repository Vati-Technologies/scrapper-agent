"""
Tests for nodes/analyze_node.py
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from tests.conftest import make_business, make_pipeline_state
from nodes.analyze_node import analyze_node, _analyze_business


GEMINI_RESPONSE = {
    "praise":     "Customers love the fast response and friendly staff.",
    "complaints": "Customers struggle to reach them by phone.",
}


def make_mock_client(response_dict: dict):
    mock_response = MagicMock()
    mock_response.text = json.dumps(response_dict)
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    return mock_client


class TestAnalyzeNode:
    def test_returns_all_businesses(self):
        businesses = [
            make_business({"name": "Biz A", "place_id": "001"}),
            make_business({"name": "Biz B", "place_id": "002"}),
        ]
        state = make_pipeline_state({"new_businesses": businesses})

        with patch("nodes.analyze_node._get_client", return_value=make_mock_client(GEMINI_RESPONSE)):
            result = analyze_node(state)

        assert len(result["analyzed_businesses"]) == 2

    def test_handles_empty_businesses(self):
        state = make_pipeline_state({"new_businesses": []})
        result = analyze_node(state)
        assert result["analyzed_businesses"] == []


class TestAnalyzeBusiness:
    def test_praise_and_complaints_populated_from_gemini(self):
        """Core test: praise and complaints columns get real Gemini content."""
        business = make_business()

        with patch("nodes.analyze_node._get_client", return_value=make_mock_client(GEMINI_RESPONSE)):
            result = _analyze_business(business)

        assert result["praise"]     == "Customers love the fast response and friendly staff."
        assert result["complaints"] == "Customers struggle to reach them by phone."

    def test_no_pitch_key_in_result(self):
        """Pitch angle should no longer be returned."""
        business = make_business()

        with patch("nodes.analyze_node._get_client", return_value=make_mock_client(GEMINI_RESPONSE)):
            result = _analyze_business(business)

        assert "pitch" not in result

    def test_strips_markdown_code_fences(self):
        """Gemini sometimes wraps JSON in ```json ... ``` — must still parse."""
        business  = make_business()
        raw_text  = "```json\n" + json.dumps(GEMINI_RESPONSE) + "\n```"
        mock_resp = MagicMock()
        mock_resp.text = raw_text

        with patch("nodes.analyze_node._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_resp
            mock_get.return_value = mock_client
            result = _analyze_business(business)

        assert result["praise"]     == GEMINI_RESPONSE["praise"]
        assert result["complaints"] == GEMINI_RESPONSE["complaints"]

    def test_praise_and_complaints_fallback_on_gemini_error(self):
        """When Gemini throws, columns get a fallback message (not blank)."""
        business = make_business()

        with patch("nodes.analyze_node._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = Exception("API error")
            mock_get.return_value = mock_client
            result = _analyze_business(business)

        assert result["praise"]     == "Unable to analyze reviews."
        assert result["complaints"] == "Unable to analyze reviews."

    def test_praise_and_complaints_fallback_on_invalid_json(self):
        """When Gemini returns non-JSON, columns get a fallback (not blank)."""
        business  = make_business()
        mock_resp = MagicMock()
        mock_resp.text = "This is not JSON at all."

        with patch("nodes.analyze_node._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_resp
            mock_get.return_value = mock_client
            result = _analyze_business(business)

        assert result["praise"]     == "Unable to analyze reviews."
        assert result["complaints"] == "Unable to analyze reviews."

    def test_no_reviews_skips_gemini_returns_placeholder(self):
        """Businesses with no reviews should not call Gemini and return placeholder text."""
        business = make_business({"reviews": []})

        with patch("nodes.analyze_node._get_client") as mock_get:
            result = _analyze_business(business)

        mock_get.assert_not_called()
        assert result["praise"]     == "No reviews available."
        assert result["complaints"] == "No reviews available."

    def test_score_and_reason_always_present(self):
        """score and reason must always be in the result regardless of Gemini outcome."""
        business = make_business()

        with patch("nodes.analyze_node._get_client", return_value=make_mock_client(GEMINI_RESPONSE)):
            result = _analyze_business(business)

        assert "score"  in result
        assert "reason" in result
        assert result["score"] in ("HOT", "WARM")
