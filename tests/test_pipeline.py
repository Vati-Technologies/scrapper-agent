"""
Tests for pipeline.py — routing logic and _check_leads gate.
"""
import pytest
from tests.conftest import make_pipeline_state, make_analyzed_business
from pipeline import _check_leads


class TestCheckLeads:
    def test_returns_ok_when_businesses_present(self):
        state = make_pipeline_state({
            "analyzed_businesses": [make_analyzed_business()]
        })
        assert _check_leads(state) == "ok"

    def test_returns_empty_when_no_businesses(self):
        state = make_pipeline_state({"analyzed_businesses": []})
        assert _check_leads(state) == "empty"

    def test_returns_empty_when_key_missing(self):
        state = make_pipeline_state()
        state.pop("analyzed_businesses", None)
        assert _check_leads(state) == "empty"


class TestRunPipeline:
    def test_pipeline_ends_early_when_no_new_leads(self):
        """If dedup removes everything, pipeline ends without calling excel/deliver."""
        from unittest.mock import patch, MagicMock
        from pipeline import run_pipeline

        with (
            patch("nodes.scrape_node._search_serper",    return_value=[]),
            patch("nodes.dedup_node.get_sent_place_ids", return_value=set()),
        ):
            result = run_pipeline(
                client_id="test_client",
                whatsapp_number="+27821234567",
                industry="Plumbers",
                city="Cape Town",
                request_id=1,
            )

        # Pipeline ran but nothing to deliver
        assert result["raw_businesses"] == []
        assert result["analyzed_businesses"] == []
        assert result["delivery_status"] == ""

    def test_pipeline_runs_full_flow(self):
        """Full happy path with all nodes mocked."""
        from unittest.mock import patch, MagicMock
        import json
        from tests.conftest import make_business, make_analyzed_business
        from pipeline import run_pipeline

        mock_business   = make_business()
        mock_analyzed   = make_analyzed_business()
        gemini_json     = json.dumps({
            "praise":     "Great service.",
            "complaints": "Slow invoicing.",
            "pitch":      "You need better online presence.",
            "score":      "HOT",
            "reason":     "No website, few reviews.",
        })

        with (
            patch("nodes.scrape_node._search_serper",         return_value=[mock_business]),
            patch("nodes.enrich_node._get_gmaps",             return_value=MagicMock(place=lambda **kw: {"result": {"reviews": [], "rating": 3.2, "user_ratings_total": 8}})),
            patch("nodes.dedup_node.get_sent_place_ids",      return_value=set()),
            patch("nodes.analyze_node._get_client")           as mock_get_client,
            patch("nodes.deliver_node.send_message"),
            patch("nodes.deliver_node.send_document"),
            patch("nodes.deliver_node.save_leads"),
            patch("nodes.deliver_node.mark_request_complete"),
        ):
            mock_resp = MagicMock()
            mock_resp.text = gemini_json
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_resp
            mock_get_client.return_value = mock_client

            result = run_pipeline(
                client_id="test_client",
                whatsapp_number="+27821234567",
                industry="Plumbers",
                city="Cape Town",
                request_id=1,
            )

        assert result["delivery_status"] == "sent"
        assert len(result["analyzed_businesses"]) == 1
        assert result["analyzed_businesses"][0]["score"] == "HOT"
