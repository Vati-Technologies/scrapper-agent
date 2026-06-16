import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from utils.auth import require_auth
from utils import dashboard_db
from utils.brief import generate_brief

router = APIRouter(prefix="/dashboard/leads", tags=["leads"])


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
def get_or_generate_brief(lead_id: int, force: bool = False, _=Depends(require_auth)):
    lead = dashboard_db.get_lead_by_id(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if not lead.get("business_name"):
        raise HTTPException(status_code=422, detail="Lead has insufficient data to generate a brief")

    if not force and lead.get("brief"):
        brief = lead["brief"]
        if isinstance(brief, dict) and "gemini_error" not in brief.get("data_flags", []):
            return {"brief": brief, "cached": True}

    try:
        brief = generate_brief(lead)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Brief generation temporarily unavailable: {type(e).__name__}")

    if "gemini_error" not in brief.get("data_flags", []):
        dashboard_db.save_lead_brief(lead_id, json.dumps(brief))

    return {"brief": brief, "cached": False}
