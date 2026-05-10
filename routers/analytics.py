from fastapi import APIRouter, Depends
from utils.auth import require_auth
from utils import dashboard_db

router = APIRouter(prefix="/dashboard/analytics", tags=["analytics"])


@router.get("/home")
def home_summary(_=Depends(require_auth)):
    return dashboard_db.get_home_summary()


@router.get("/leads")
def lead_analytics(_=Depends(require_auth)):
    return dashboard_db.get_lead_funnel()


@router.get("/revenue")
def revenue_analytics(_=Depends(require_auth)):
    return dashboard_db.get_revenue_analytics()


@router.get("/services")
def service_analytics(_=Depends(require_auth)):
    return dashboard_db.get_service_analytics()
