from fastapi import Header, HTTPException, status
from config import DASHBOARD_API_KEY


def require_auth(x_api_key: str | None = Header(default=None)):
    if not x_api_key or x_api_key != DASHBOARD_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
