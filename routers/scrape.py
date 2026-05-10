import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from pipeline import run_pipeline
from utils.auth import require_auth
from utils import dashboard_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard/scrape", tags=["scrape"])

_executor = ThreadPoolExecutor(max_workers=1)
_scrape_state: dict = {
    "running":      False,
    "last_status":  "idle",
    "last_run_at":  None,
    "industry":     None,
    "city":         None,
}


class ScrapeRequest(BaseModel):
    industry: str
    city: str


@router.post("")
async def trigger_scrape(body: ScrapeRequest, _=Depends(require_auth)):
    if _scrape_state["running"]:
        raise HTTPException(status_code=409, detail="A scrape run is already in progress")

    _scrape_state.update(running=True, last_status="running", industry=body.industry, city=body.city)

    def _run():
        try:
            client_id  = dashboard_db.DASHBOARD_CLIENT_ID
            request_id = dashboard_db.save_dashboard_request(body.industry, body.city)
            run_pipeline(
                client_id=client_id,
                whatsapp_number="dashboard",
                industry=body.industry,
                city=body.city,
                request_id=request_id,
                skip_whatsapp=True,
            )
            _scrape_state["last_status"] = "completed"
        except Exception as e:
            logger.error("Dashboard scrape failed: %s: %s", type(e).__name__, e)
            _scrape_state["last_status"] = "failed"
        finally:
            _scrape_state["running"]    = False
            _scrape_state["last_run_at"] = datetime.now(timezone.utc).isoformat()

    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _run)

    return {"status": "started"}


@router.get("/status")
def scrape_status(_=Depends(require_auth)):
    return _scrape_state
