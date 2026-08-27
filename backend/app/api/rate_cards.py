from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.dependencies import require_roles
from app.models.user import User
from app.services import rate_card_service

router = APIRouter()


@router.get("/api/rate-card")
async def get_rate_card(user: User = Depends(require_roles("Admin", "Developer", "Finance"))):
    return {"rates": rate_card_service.get_rates()}


class RateCardUpdate(BaseModel):
    rates: dict[str, dict]


@router.put("/api/rate-card")
async def update_rate_card(payload: RateCardUpdate, user: User = Depends(require_roles("Admin"))):
    return {"rates": rate_card_service.update_rates(payload.rates)}
