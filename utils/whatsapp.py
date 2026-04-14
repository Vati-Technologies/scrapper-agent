import os
import httpx
import mimetypes
from config import WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID

BASE_URL = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}"
HEADERS  = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}


def send_message(to: str, text: str):
    """Send a plain text WhatsApp message."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text, "preview_url": False},
    }
    _post("/messages", json=payload)


def send_document(to: str, file_path: str, caption: str = ""):
    """Upload a file and send it as a WhatsApp document."""
    media_id = _upload_media(file_path)
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "document",
        "document": {
            "id": media_id,
            "caption": caption,
            "filename": file_path.split("/")[-1],
        },
    }
    _post("/messages", json=payload)


def _upload_media(file_path: str) -> str:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Excel file not found: {file_path}")
    mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    try:
        with open(file_path, "rb") as f:
            response = httpx.post(
                f"{BASE_URL}/media",
                headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"},
                data={"messaging_product": "whatsapp"},
                files={"file": (file_path.split("/")[-1], f, mime_type)},
                timeout=60,
            )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"WhatsApp media upload failed ({e.response.status_code}): {e}"
        ) from e
    return response.json()["id"]


def _post(path: str, json: dict):
    try:
        response = httpx.post(
            f"{BASE_URL}{path}",
            headers={**HEADERS, "Content-Type": "application/json"},
            json=json,
            timeout=30,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"WhatsApp API error ({e.response.status_code}): {e}"
        ) from e
    return response.json()


# ── Message parsing ───────────────────────────────────────────────────────────

def parse_incoming(body: dict) -> dict | None:
    """Extract sender number and text from a WhatsApp webhook payload."""
    try:
        entry   = body["entry"][0]
        changes = entry["changes"][0]
        value   = changes["value"]
        message = value["messages"][0]

        return {
            "from": message["from"],
            "text": message.get("text", {}).get("body", "").strip(),
            "message_id": message["id"],
        }
    except (KeyError, IndexError):
        return None


def parse_lead_request(text: str) -> dict | None:
    """
    Parse structured client request:
        Industry: Plumbers
        City: Cape Town
        Stars: 2-3          ← optional
    Returns dict with 'industry', 'city', 'star_min', 'star_max' or None if invalid.
    """
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    data  = {}
    for line in lines:
        if ":" in line:
            key, _, value = line.partition(":")
            data[key.strip().lower()] = value.strip()

    industry = data.get("industry")
    city     = data.get("city")

    if not (industry and city):
        return None

    result = {"industry": industry, "city": city}

    stars_raw = data.get("stars")
    if stars_raw:
        parsed_stars = _parse_stars(stars_raw)
        if parsed_stars:
            result["star_min"], result["star_max"] = parsed_stars

    return result


def _parse_stars(value: str) -> tuple[float | None, float | None] | None:
    """
    Parse a star rating filter value:
      "2-3"  → (2.0, 3.0)  — range
      "3"    → (None, 3.0) — max only
    Returns None if unparseable or out of range.
    """
    value = value.strip()
    if "-" in value:
        parts = value.split("-", 1)
        try:
            lo = float(parts[0].strip())
            hi = float(parts[1].strip())
            if 1.0 <= lo <= 5.0 and 1.0 <= hi <= 5.0 and lo <= hi:
                return lo, hi
        except ValueError:
            pass
    else:
        try:
            v = float(value)
            if 1.0 <= v <= 5.0:
                return None, v
        except ValueError:
            pass
    return None


ONBOARDING_MSG = """👋 *Welcome to LeadGen Pro!*

To get your daily leads, send a message in this format:

─────────────────────
Industry: Plumbers
City: Cape Town
Stars: 2-3
─────────────────────

The *Stars* line is *optional*. Use it to target businesses by rating:
• `Stars: 1-3` — low-rated businesses (1 to 3 stars)
• `Stars: 4-5` — high-rated businesses (4 to 5 stars)
• `Stars: 2-4` — any custom range
• `Stars: 3` — 3 stars or below (max only)
Omit it to include all star ratings.

You get *1 report per day*.
Reports include 10–20 leads with review summaries and pitch angles.

Send your request any time — we'll get it to you in ~2 minutes."""

FORMAT_ERROR_MSG = """❌ I didn't understand that format.

Please send your request like this:

Industry: Plumbers
City: Cape Town
Stars: 2-3

The *Stars* line is optional. You can also send without it:

Industry: Plumbers
City: Cape Town"""

DAILY_LIMIT_MSG = """⏳ You've already received your leads for today.

Your next report is available tomorrow.
Send your request any time after midnight."""

PROCESSING_MSG = "✅ Got it! Searching for *{industry}* in *{city}*{stars_label}.\nYour report will be ready in ~2 minutes. ⏳"
