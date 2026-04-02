"""
Tests for nodes/scrape_node.py
"""
import pytest
from unittest.mock import patch, MagicMock
from tests.conftest import make_pipeline_state
from nodes.scrape_node import scrape_node, _search_serper


SERPER_RESPONSE = {
    "places": [
        {
            "title":       "Joe's Plumbing",
            "address":     "12 Main Rd, Cape Town",
            "rating":      3.2,
            "ratingCount": 8,
            "placeId":     "ChIJ_001",
            "phoneNumber": "021 555 1234",
            "website":     "",
            "category":    "Plumber",
        },
        {
            "title":       "Cape Drain Masters",
            "address":     "45 Long St, Cape Town",
            "rating":      4.1,
            "ratingCount": 42,
            "placeId":     "ChIJ_002",
            "phoneNumber": "021 555 9876",
            "website":     "https://capedrains.co.za",
            "category":    "Plumber",
        },
    ]
}


class TestScrapeNode:
    def test_returns_raw_businesses_list(self):
        state = make_pipeline_state({"industry": "Plumbers", "city": "Cape Town"})

        with patch("nodes.scrape_node.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: SERPER_RESPONSE,
                raise_for_status=lambda: None,
            )
            result = scrape_node(state)

        assert "raw_businesses" in result
        assert len(result["raw_businesses"]) == 2

    def test_maps_fields_correctly(self):
        state = make_pipeline_state({"industry": "Plumbers", "city": "Cape Town"})

        with patch("nodes.scrape_node.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: SERPER_RESPONSE,
                raise_for_status=lambda: None,
            )
            result = scrape_node(state)

        first = result["raw_businesses"][0]
        assert first["name"]         == "Joe's Plumbing"
        assert first["place_id"]     == "ChIJ_001"
        assert first["rating"]       == 3.2
        assert first["review_count"] == 8
        assert first["phone"]        == "021 555 1234"
        assert first["website"]      == ""

    def test_handles_empty_results(self):
        state = make_pipeline_state({"industry": "Plumbers", "city": "Cape Town"})

        with patch("nodes.scrape_node.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"places": []},
                raise_for_status=lambda: None,
            )
            result = scrape_node(state)

        assert result["raw_businesses"] == []

    def test_builds_correct_query(self):
        state = make_pipeline_state({"industry": "Electricians", "city": "Johannesburg"})

        with patch("nodes.scrape_node.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"places": []},
                raise_for_status=lambda: None,
            )
            scrape_node(state)

        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"]
        assert payload["q"] == "Electricians in Johannesburg"

    def test_raises_on_http_error(self):
        state = make_pipeline_state()

        with patch("nodes.scrape_node.httpx.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = Exception("HTTP 429")
            mock_post.return_value = mock_response

            with pytest.raises(Exception, match="HTTP 429"):
                scrape_node(state)
