"""Optional admin token auth for write endpoints."""
import os
from fastapi import Header, HTTPException

from app.config import ADMIN_TOKEN


def require_admin(x_admin_token: str | None = Header(None, alias="X-Admin-Token")):
    """Require X-Admin-Token when ADMIN_TOKEN is configured."""
    if not ADMIN_TOKEN:
        return
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing admin token")
