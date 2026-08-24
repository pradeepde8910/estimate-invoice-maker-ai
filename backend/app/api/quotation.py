from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.api.dependencies import require_roles
from app.models.quotation import Quotation, QuotationLineItem
from pydantic import BaseModel
from decimal import Decimal

router = APIRouter()

# Schemas
class QuotationLineItemUpdate(BaseModel):
    applied_price: Decimal
    quantity: int
    unit: str
    status: str
    notes: Optional[str] = None

class QuotationStatusUpdate(BaseModel):
    status: str

# ── Quotation API ────────────────────────────────────────────────────────

@router.get("/quotations")
def list_quotations(db: Session = Depends(get_db), user=Depends(require_roles("Admin", "Finance"))):
    return db.query(Quotation).order_by(Quotation.created_at.desc()).all()

@router.get("/quotations/{id}")
def get_quotation(id: str, db: Session = Depends(get_db), user=Depends(require_roles("Admin", "Finance"))):
    q = db.query(Quotation).options(joinedload(Quotation.line_items)).filter(Quotation.id == id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return q

@router.put("/quotations/{id}/lines/{line_id}")
def update_quotation_line_item(
    id: str,
    line_id: str,
    data: QuotationLineItemUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin"))
):
    """Admin endpoint to edit a specific pending or verified price."""
    quotation = db.query(Quotation).options(joinedload(Quotation.line_items)).filter(Quotation.id == id).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
        
    line_item = next((li for li in quotation.line_items if li.id == line_id), None)
    if not line_item:
        raise HTTPException(status_code=404, detail="Line item not found")
        
    # Apply updates
    line_item.applied_price = data.applied_price
    line_item.quantity = data.quantity
    line_item.unit = data.unit
    line_item.status = data.status  # e.g., PENDING -> VERIFIED or EDITED
    line_item.notes = data.notes
    
    # Recalculate Grand Total
    # First, separate the components
    verified_infra_cost = Decimal('0.0')
    licenses_cost = Decimal('0.0')
    
    for item in quotation.line_items:
        # Only include in total if it's considered verified or edited-verified
        if item.status in ["VERIFIED", "EDITED", "ADMIN_APPROVED"]:
            # Basic calculation: applied_price * quantity. (6 months is a default assumption if unit is month)
            multiplier = Decimal('6') if item.unit and "month" in item.unit.lower() else Decimal('1')
            cost = (item.applied_price or Decimal('0')) * item.quantity * multiplier
            verified_infra_cost += cost

    quotation.verified_infrastructure_cost = verified_infra_cost
    quotation.grand_total = quotation.development_cost + quotation.contingency_amount + quotation.verified_infrastructure_cost + quotation.licenses_cost
    
    db.commit()
    db.refresh(quotation)
    return quotation

@router.post("/quotations/{id}/status")
def update_quotation_status(
    id: str,
    data: QuotationStatusUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin"))
):
    """Transition quotation status (e.g. DRAFT -> ADMIN_APPROVED)"""
    quotation = db.query(Quotation).filter(Quotation.id == id).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
        
    quotation.status = data.status
    db.commit()
    db.refresh(quotation)
    return quotation
