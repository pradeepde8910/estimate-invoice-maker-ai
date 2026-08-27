from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime
from typing import List

from app.database import get_db
from app.api.dependencies import require_roles
from app.schemas.invoice import InvoiceCreateRequest, InvoiceStatusUpdateRequest, StandaloneInvoiceCreateRequest
from app.services.invoice_service import create_invoice, create_standalone_invoice, transition_invoice_status, InvalidStateTransitionError, InvoiceCreationError
from app.services.billing_service import OverBillingError
from app.services.pdf_service import generate_invoice_pdf
from fastapi.responses import Response

router = APIRouter()

# Schemas for response
class InvoiceItemResponse(BaseModel):
    description: str
    amount: Decimal

class InvoiceResponse(BaseModel):
    id: str
    invoice_number: str | None
    invoice_type: str = "PROJECT"
    status: str
    payment_status: str = "UNPAID"
    subtotal: Decimal
    gross_amount: Decimal
    total_payable: Decimal
    amount_paid: Decimal = Decimal('0.00')
    balance_due: Decimal = Decimal('0.00')
    created_at: datetime
    invoice_date: datetime | None = None
    billing_model: str | None = None
    billing_sources: List[str] = []

    class Config:
        from_attributes = True

@router.post("/projects/{project_id}/invoices", response_model=InvoiceResponse)
def create_project_invoice(
    project_id: str, 
    request: InvoiceCreateRequest, 
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance"))
):
    try:
        invoice = create_invoice(db, project_id, request)
        return invoice
    except OverBillingError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error during invoice creation")


class StandaloneInvoiceListItem(BaseModel):
    id: str
    invoice_number: str | None
    status: str
    payment_status: str = "UNPAID"
    client_name: str | None = None
    total_payable: Decimal
    balance_due: Decimal = Decimal('0.00')
    created_at: datetime
    invoice_date: datetime | None = None

    class Config:
        from_attributes = True


@router.get("/standalone", response_model=List[StandaloneInvoiceListItem])
def list_standalone_invoices(
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance"))
):
    from app.models.invoice import Invoice as InvoiceModel
    return (
        db.query(InvoiceModel)
        .filter(InvoiceModel.invoice_type == "STANDALONE")
        .order_by(InvoiceModel.created_at.desc())
        .all()
    )


@router.post("/standalone", response_model=InvoiceResponse)
def create_standalone_invoice_endpoint(
    request: StandaloneInvoiceCreateRequest,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance"))
):
    try:
        invoice = create_standalone_invoice(db, request)
        return invoice
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error during invoice creation")


@router.put("/{invoice_id}/status", response_model=InvoiceResponse)
def update_invoice_status(
    invoice_id: str, 
    request: InvoiceStatusUpdateRequest, 
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance"))
):
    try:
        invoice = transition_invoice_status(db, invoice_id, request.status)
        return invoice
    except InvalidStateTransitionError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")


from app.models.invoice import Invoice
from app.schemas.invoice import InvoiceDetailResponse

@router.get("/{invoice_id}", response_model=InvoiceDetailResponse)
def get_invoice_detail(
    invoice_id: str, 
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance"))
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.get("/{invoice_id}/pdf")
def download_invoice_pdf(
    invoice_id: str, 
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance"))
):
    try:
        pdf_bytes = generate_invoice_pdf(db, invoice_id)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="invoice_{invoice_id}.pdf"'}
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        import traceback
        with open("pdf_generation_error.log", "w") as f:
            f.write(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to generate PDF")
