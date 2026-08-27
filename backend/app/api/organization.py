import re

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field, field_validator
from typing import Optional

from app.api.dependencies import require_roles
from app.models.user import User
from app.models.invoice import Invoice
from app.models.estimation import Document
from app.core.database import SessionLocal
from app.services import organization_service as organization
from app.services.invoice_builder import build_invoice
from app.utils.letterhead import apply_letterhead

router = APIRouter()

EMAIL_RE = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
PHONE_RE = re.compile(r'^\d{10}$')
GSTIN_RE = re.compile(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$')


class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field("Your Company Name", max_length=255)
    tagline: Optional[str] = Field("", max_length=255)
    address: Optional[str] = Field("", max_length=300)
    email: Optional[str] = Field("", max_length=100)
    phone: Optional[str] = Field("", max_length=10)
    website: Optional[str] = Field("", max_length=100)
    gstin: Optional[str] = Field("", max_length=15)
    registration_number: Optional[str] = Field("", max_length=50)
    certifications: Optional[str] = Field("", max_length=500)
    signatory_name: Optional[str] = Field("", max_length=100)
    signatory_title: Optional[str] = Field("Authorized Signatory", max_length=100)
    bank_name: Optional[str] = Field("", max_length=100)
    bank_account_number: Optional[str] = Field("", max_length=30)
    bank_ifsc: Optional[str] = Field("", max_length=11)
    bank_branch: Optional[str] = Field("", max_length=100)
    upi_id: Optional[str] = Field("", max_length=100)
    invoice_terms: Optional[str] = Field("", max_length=2000)

    @field_validator(
        'name', 'tagline', 'address', 'email', 'phone', 'website',
        'gstin', 'registration_number', 'certifications', 'signatory_name',
        'signatory_title', 'bank_name', 'bank_account_number', 'bank_ifsc',
        'bank_branch', 'upi_id', 'invoice_terms',
        mode='before'
    )
    @classmethod
    def coerce_none_to_str(cls, v):
        return v if v is not None else ""

    @field_validator('upi_id')
    @classmethod
    def validate_upi_id(cls, v):
        if v and not re.match(r'^[\w.\-]{2,256}@[a-zA-Z]{2,64}$', v):
            raise ValueError('Invalid UPI ID format (expected e.g. name@bank)')
        return v

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v and not EMAIL_RE.match(v):
            raise ValueError('Invalid email address')
        return v

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        if v and not PHONE_RE.match(v):
            raise ValueError('Phone number must be exactly 10 digits')
        return v

    @field_validator('gstin')
    @classmethod
    def validate_gstin(cls, v):
        if v and not GSTIN_RE.match(v.upper()):
            raise ValueError('Invalid GSTIN format (expected e.g. 22AAAAA0000A1Z5)')
        return v.upper() if v else v


@router.get("/api/organization")
async def get_organization():
    return {"profile": organization.get_organization_profile()}


@router.put("/api/organization")
async def update_organization(
    payload: OrganizationUpdate,
    user: User = Depends(require_roles("Admin")),
):
    profile = organization.update_organization_profile(payload.model_dump())
    return {"profile": profile}


@router.post("/api/organization/apply-branding-history")
async def apply_branding_history(user: User = Depends(require_roles("Admin"))):
    db = SessionLocal()
    try:
        profile = organization.get_organization_profile()

        # Process Invoices — restamp the header/footer of every already-
        # generated invoice with the current branding, without touching the
        # line items or totals.
        dummy_html, _ = build_invoice({}, profile, "DUMMY")
        header_match = re.search(r'<header[^>]*>.*?</header>', dummy_html, re.DOTALL)
        footer_match = re.search(r'<footer[^>]*>.*?</footer>', dummy_html, re.DOTALL)

        if header_match and footer_match:
            new_header = header_match.group(0)
            new_footer = footer_match.group(0)

            invoices = db.query(Invoice).filter(Invoice.invoice_html.isnot(None)).all()
            for inv in invoices:
                html = inv.invoice_html
                html = re.sub(r'<header[^>]*>.*?</header>', new_header, html, flags=re.DOTALL)
                html = re.sub(r'<footer[^>]*>.*?</footer>', new_footer, html, flags=re.DOTALL)
                inv.invoice_html = html

        # Process Documents (Markdown) — re-letterhead quotation/BRD/SRS docs.
        documents = db.query(Document).filter(Document.type.in_(["quotation", "brd", "srs"])).all()
        for doc in documents:
            if doc.content:
                lines = doc.content.split('\n')
                for i in range(min(15, len(lines))):
                    if lines[i].strip() == '---':
                        lines = lines[i + 1:]
                        break
                for i in range(len(lines) - 1, max(-1, len(lines) - 15), -1):
                    if lines[i].strip() == '---':
                        lines = lines[:i]
                        break

                stripped = '\n'.join(lines).strip()
                doc.content = apply_letterhead(stripped, profile)

        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Failed to apply branding history: {e}")
    finally:
        db.close()


@router.post("/api/organization/{slot}")
async def upload_organization_asset(
    slot: str,
    file: UploadFile = File(...),
    user: User = Depends(require_roles("Admin")),
):
    if slot not in ("logo", "signature", "seal"):
        raise HTTPException(400, "Unknown branding asset slot")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds the 5MB limit.")
    try:
        profile = organization.upload_branding_asset(slot, file.filename or f"{slot}.png", content)
    except organization.InvalidBrandingAssetError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")
    return {"profile": profile}
