from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from typing import Optional
from utils.auth import require_auth
from utils import dashboard_db

router = APIRouter(prefix="/dashboard/clients", tags=["clients"])


class ClientCreate(BaseModel):
    name: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    monthly_fee: Optional[float] = None
    payment_status: Optional[str] = "pending"
    started_at: Optional[str] = None
    notes: Optional[str] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    monthly_fee: Optional[float] = None
    payment_status: Optional[str] = None
    started_at: Optional[str] = None
    notes: Optional[str] = None


class ServiceUpdate(BaseModel):
    status: str


@router.get("")
def list_clients(_=Depends(require_auth)):
    return dashboard_db.get_agency_clients()


@router.post("", status_code=201)
def create_client(body: ClientCreate, _=Depends(require_auth)):
    return dashboard_db.create_agency_client(body.model_dump())


@router.get("/{client_id}")
def get_client(client_id: int, _=Depends(require_auth)):
    client = dashboard_db.get_agency_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.patch("/{client_id}")
def update_client(client_id: int, body: ClientUpdate, _=Depends(require_auth)):
    client = dashboard_db.get_agency_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return dashboard_db.update_agency_client(client_id, body.model_dump(exclude_none=True))


@router.delete("/{client_id}")
def delete_client(client_id: int, _=Depends(require_auth)):
    deleted = dashboard_db.delete_agency_client(client_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Client not found")
    return Response(status_code=204)


@router.get("/{client_id}/services")
def get_services(client_id: int, _=Depends(require_auth)):
    return dashboard_db.get_client_services(client_id)


@router.patch("/{client_id}/services/{service_type}")
def update_service(client_id: int, service_type: str, body: ServiceUpdate, _=Depends(require_auth)):
    valid_services = {"seo", "website", "social_media"}
    if service_type not in valid_services:
        raise HTTPException(status_code=400, detail=f"service_type must be one of: {valid_services}")
    return dashboard_db.upsert_client_service(client_id, service_type, body.status)
