from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db
from app.api.dependencies import require_roles
from app.models.master import Client

router = APIRouter()


class ClientResponse(BaseModel):
    id: str
    company_name: Optional[str]
    contact_person: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    gstin: Optional[str]
    billing_address: Optional[str]

    class Config:
        from_attributes = True


@router.get("/clients", response_model=List[ClientResponse])
def list_clients(
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance"))
):
    """
    V2's own client roster (the `clients` table backing Invoice.client_id and
    Project.client_id), as opposed to v1's /api/db-clients — a separate
    endpoint over v1's legacy estimation database, which is a distinct
    SQLite file and does not share client ids with this one.
    """
    return db.query(Client).order_by(Client.company_name).all()
