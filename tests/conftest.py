"""
Shared fixtures and factory functions for all tests.
"""
import os
import pytest

# ── Set dummy env vars before any imports touch config ────────────────────────
os.environ.setdefault("GEMINI_API_KEY",            "test-gemini-key")
os.environ.setdefault("SERPER_API_KEY",            "test-serper-key")
os.environ.setdefault("GOOGLE_PLACES_API_KEY",     "test-places-key")
os.environ.setdefault("WHATSAPP_TOKEN",            "test-wa-token")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID",  "123456789")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN",     "test-verify-token")
os.environ.setdefault("DATABASE_URL",              "postgresql://test:test@localhost/test")


# ── Factories ─────────────────────────────────────────────────────────────────

def make_business(overrides: dict = None) -> dict:
    """Factory: a single enriched business dict."""
    base = {
        "name":         "Joe's Plumbing",
        "address":      "12 Main Rd, Cape Town",
        "rating":       3.2,
        "review_count": 8,
        "place_id":     "ChIJ_test_001",
        "phone":        "021 555 1234",
        "website":      "",
        "category":     "Plumber",
        "reviews": [
            {"author": "Alice", "rating": 5, "text": "Fast and friendly service!", "time": "2 months ago"},
            {"author": "Bob",   "rating": 2, "text": "Hard to reach by phone.",    "time": "3 months ago"},
        ],
    }
    return {**base, **(overrides or {})}


def make_analyzed_business(overrides: dict = None) -> dict:
    """Factory: a business with Gemini analysis fields added."""
    base = {
        **make_business(),
        "praise":      "Customers love the fast response and friendly staff.",
        "complaints":  "Customers struggle to reach them by phone.",
        "pitch":       "Your customers love your work but can't reach you online.",
        "score":       "HOT",
        "reason":      "No website, low reviews, and a sub-4 rating.",
    }
    return {**base, **(overrides or {})}


def make_pipeline_state(overrides: dict = None) -> dict:
    """Factory: a full LeadGenState dict."""
    base = {
        "client_id":            "client_001",
        "whatsapp_number":      "+27821234567",
        "industry":             "Plumbers",
        "city":                 "Cape Town",
        "request_id":           1,
        "raw_businesses":       [],
        "enriched_businesses":  [],
        "new_businesses":       [],
        "analyzed_businesses":  [],
        "excel_path":           "",
        "delivery_status":      "",
        "errors":               [],
    }
    return {**base, **(overrides or {})}


def make_whatsapp_webhook(text: str, sender: str = "+27821234567") -> dict:
    """Factory: a WhatsApp Cloud API webhook payload."""
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": sender,
                        "id":   "wamid.test123",
                        "text": {"body": text},
                        "type": "text",
                    }]
                }
            }]
        }]
    }


def make_status_webhook() -> dict:
    """Factory: a WhatsApp status update (should be ignored)."""
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "statuses": [{"id": "wamid.test", "status": "delivered"}]
                }
            }]
        }]
    }
