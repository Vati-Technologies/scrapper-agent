"""
Tests for nodes/dedup_node.py
"""
import pytest
from unittest.mock import patch
from tests.conftest import make_business, make_pipeline_state
from nodes.dedup_node import dedup_node


class TestDedupNode:
    def test_removes_already_sent_businesses(self):
        businesses = [
            make_business({"place_id": "ChIJ_001", "name": "Already Sent"}),
            make_business({"place_id": "ChIJ_002", "name": "New Business"}),
        ]
        state = make_pipeline_state({"enriched_businesses": businesses})

        with patch("nodes.dedup_node.get_sent_place_ids", return_value={"ChIJ_001"}):
            result = dedup_node(state)

        assert len(result["new_businesses"]) == 1
        assert result["new_businesses"][0]["name"] == "New Business"

    def test_returns_all_when_no_history(self):
        businesses = [
            make_business({"place_id": "ChIJ_001"}),
            make_business({"place_id": "ChIJ_002"}),
        ]
        state = make_pipeline_state({"enriched_businesses": businesses})

        with patch("nodes.dedup_node.get_sent_place_ids", return_value=set()):
            result = dedup_node(state)

        assert len(result["new_businesses"]) == 2

    def test_returns_empty_when_all_already_sent(self):
        businesses = [
            make_business({"place_id": "ChIJ_001"}),
            make_business({"place_id": "ChIJ_002"}),
        ]
        state = make_pipeline_state({"enriched_businesses": businesses})

        with patch("nodes.dedup_node.get_sent_place_ids", return_value={"ChIJ_001", "ChIJ_002"}):
            result = dedup_node(state)

        assert result["new_businesses"] == []

    def test_handles_businesses_without_place_id(self):
        businesses = [
            make_business({"place_id": ""}),
            make_business({"place_id": "ChIJ_002"}),
        ]
        state = make_pipeline_state({"enriched_businesses": businesses})

        # Empty string not in sent_ids — both pass through
        with patch("nodes.dedup_node.get_sent_place_ids", return_value={"ChIJ_001"}):
            result = dedup_node(state)

        assert len(result["new_businesses"]) == 2

    def test_uses_correct_client_id(self):
        state = make_pipeline_state({
            "client_id": "client_xyz",
            "enriched_businesses": [],
        })

        with patch("nodes.dedup_node.get_sent_place_ids", return_value=set()) as mock_get:
            dedup_node(state)

        mock_get.assert_called_once_with("client_xyz")
