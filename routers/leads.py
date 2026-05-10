from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from utils.auth import require_auth
from utils import dashboard_db

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
