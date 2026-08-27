import re

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator, model_validator
from typing import List, Optional

from app.database import get_db
from app.api.dependencies import require_roles
from app.models.master import Client

router = APIRouter()

# Mirrors frontend/src/utils/validation.ts — the frontend enforces the same
# rules on this same form, but a V2-native creation endpoint (unlike v1's
# validation-free /clients patch) validates server-side too rather than
# trusting the client-side check alone.
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^[6-9]\d{9}$")
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


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


class ClientCreateRequest(BaseModel):
    company_name: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    gstin: Optional[str] = None
    billing_address: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if v and not EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if v:
            digits = re.sub(r"\D", "", v)
            if digits.startswith("91") and len(digits) > 10:
                digits = digits[2:]
            if not PHONE_RE.match(digits):
                raise ValueError("Enter a valid 10-digit Indian mobile number")
        return v

    @field_validator("gstin")
    @classmethod
    def validate_gstin(cls, v):
        if v and not GSTIN_RE.match(v.upper()):
            raise ValueError("Enter a valid GSTIN, e.g. 22AAAAA0000A1Z5")
        return v.upper() if v else v

    @model_validator(mode="after")
    def validate_identity(self):
        if not (self.company_name or "").strip() and not (self.contact_person or "").strip():
            raise ValueError("At least Company Name or Contact Person is required")
        return self


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


@router.post("/clients", response_model=ClientResponse)
def create_client(
    request: ClientCreateRequest,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance"))
):
    client = Client(
        company_name=request.company_name or None,
        contact_person=request.contact_person or None,
        email=request.email or None,
        phone=request.phone or None,
        gstin=request.gstin or None,
        billing_address=request.billing_address or None,
        status="CONFIRMED",
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client
