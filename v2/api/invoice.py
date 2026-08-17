from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from pydantic import BaseModel
from decimal import Decimal
from typing import List

from v2.database import get_db
from v2.api.dependencies import require_roles
from v2.schemas.invoice import InvoiceCreateRequest, InvoiceStatusUpdateRequest
from v2.services.invoice_service import create_invoice, transition_invoice_status, InvalidStateTransitionError, InvoiceCreationError
from v2.services.billing_service import OverBillingError
from v2.services.pdf_service import generate_invoice_pdf
from fastapi.responses import Response

router = APIRouter(prefix="/v2/api", tags=["Invoices"])

# Schemas for response
class InvoiceItemResponse(BaseModel):
    description: str
    amount: Decimal

class InvoiceResponse(BaseModel):
    id: str
    invoice_number: str | None
    status: str
    subtotal: Decimal
    gross_amount: Decimal
    total_payable: Decimal

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


@router.put("/invoices/{invoice_id}/status", response_model=InvoiceResponse)
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


@router.get("/invoices/{invoice_id}/pdf")
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
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to generate PDF")
