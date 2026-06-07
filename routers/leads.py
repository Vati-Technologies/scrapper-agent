import json
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from google import genai
from config import GEMINI_API_KEY
from utils.auth import require_auth
from utils import dashboard_db

router = APIRouter(prefix="/dashboard/leads", tags=["leads"])

_gemini_client: genai.Client | None = None


def _get_gemini() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    return _gemini_client


def _parse_json(text: str) -> dict | None:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _generate_brief(lead: dict) -> dict:
    name       = lead.get("business_name") or "this business"
    category   = lead.get("category") or "Unknown"
    city       = lead.get("city") or "Unknown"
    rating     = lead.get("rating")
    website    = lead.get("website")
    praise     = lead.get("praise")
    complaints = lead.get("complaints")
    score      = lead.get("score") or "WARM"

    data_flags = []
    if not praise and not complaints:
        data_flags.append("no_reviews")

    rating_str     = f"{rating}★" if rating else "No rating"
    website_str    = website if website else "No website"
    praise_str     = praise if praise else "No review data available."
    complaints_str = complaints if complaints else "No review data available."

    prompt = (
        f"You are a sales assistant for a digital marketing agency. "
        f"Given the details below about a local business, write a sales brief in JSON.\n\n"
        f"Business: {name}\n"
        f"Category: {category}\n"
        f"Location: {city}\n"
        f"Rating: {rating_str}\n"
        f"Website: {website_str}\n"
        f"What customers praise: {praise_str}\n"
        f"What customers complain about: {complaints_str}\n"
        f"Lead score: {score}\n\n"
        f"Return ONLY a JSON object with exactly three keys:\n"
        f'  "about": 2-3 sentences describing what this business does and its current digital situation.\n'
        f'  "pain_points": 2-3 sentences on the specific pain points our agency can solve for them.\n'
        f'  "why_a_fit": 2-3 bullet points (•) on why our digital marketing services are a strong fit.\n'
        f"No markdown, no extra keys, no explanation."
    )

    try:
        response = _get_gemini().models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
        )
        parsed = _parse_json(response.text)
        if parsed and all(k in parsed for k in ("about", "pain_points", "why_a_fit")):
            return {
                "about":       parsed["about"],
                "pain_points": parsed["pain_points"],
                "why_a_fit":   parsed["why_a_fit"],
                "data_flags":  data_flags,
            }
        print(f"⚠️ Unexpected Gemini brief response for lead {lead.get('id')}: {response.text[:120]}")
        data_flags.append("gemini_error")
    except Exception as e:
        print(f"⚠️ Gemini brief error for lead {lead.get('id')}: {type(e).__name__}: {e}")
        data_flags.append("gemini_error")

    return {
        "about":       f"{name} is a {category} business in {city} with a {rating_str} Google rating and {'no website' if not website else 'an existing website'}.",
        "pain_points": "AI generation is temporarily unavailable. Please regenerate the brief.",
        "why_a_fit":   "AI generation is temporarily unavailable. Please regenerate the brief.",
        "data_flags":  data_flags,
    }


class LeadUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


@router.get("")
def list_leads(
    status: Optional[str] = None,
    score: Optional[str] = None,
    _=Depends(require_auth),
):
    return dashboard_db.get_all_leads(status=status, score=score)


@router.patch("/{lead_id}")
def update_lead(lead_id: int, body: LeadUpdate, _=Depends(require_auth)):
    try:
        return dashboard_db.update_lead(lead_id, body.status, body.notes)
    except Exception:
        raise HTTPException(status_code=404, detail="Lead not found")


@router.post("/{lead_id}/brief")
def generate_brief(lead_id: int, force: bool = False, _=Depends(require_auth)):
    lead = dashboard_db.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    cached = lead.get("brief")
    if not force and cached and "gemini_error" not in cached.get("data_flags", []):
        return {"brief": cached, "cached": True}

    brief = _generate_brief(lead)
    dashboard_db.save_lead_brief(lead_id, brief)
    return {"brief": brief, "cached": False}
