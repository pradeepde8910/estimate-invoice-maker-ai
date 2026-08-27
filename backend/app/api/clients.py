from fastapi import APIRouter, Depends

from app.api.dependencies import require_roles
from app.models.user import User
from app.services import client_service

router = APIRouter()


@router.get("/api/clients")
async def list_clients(user: User = Depends(require_roles("Admin", "Developer", "Finance"))):
    return {"clients": client_service.list_derived_clients()}


@router.get("/api/db-clients")
async def list_db_clients(user: User = Depends(require_roles("Admin", "Developer", "Finance"))):
    return {"clients": client_service.list_db_clients()}
