from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from decimal import Decimal
from typing import Optional

from app.database import get_db
from app.api.dependencies import require_roles
from app.models.master import BillingClassification
from app.services.billing_classification_service import match_billing_classifications

router = APIRouter()


class BillingClassificationResponse(BaseModel):
    id: str
    category: str
    description: str
    item_type: str
    hsn_sac_code: str
    hsn_sac_type: str
    gst_rate: Decimal
    keywords: Optional[str]
    active: bool

    class Config:
        from_attributes = True


class BillingClassificationMatchResponse(BillingClassificationResponse):
    score: int


@router.get("", response_model=list[BillingClassificationResponse])
def list_billing_classifications(
    category: Optional[str] = None,
    item_type: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance")),
):
    """Full catalog listing, for an admin management screen or a line-item picker dropdown."""
    q = db.query(BillingClassification)
    if active_only:
        q = q.filter(BillingClassification.active.is_(True))
    if category:
        q = q.filter(BillingClassification.category == category)
    if item_type:
        q = q.filter(BillingClassification.item_type == item_type)
    return q.order_by(BillingClassification.category, BillingClassification.description).all()


@router.get("/match", response_model=list[BillingClassificationMatchResponse])
def match_billing_classification(
    description: str = Query(..., min_length=2, description="Free-text description of what's being billed"),
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance")),
):
    """
    Keyword-scored candidates for a given line-item description, so a caller
    (invoice line-item form, or later the estimation pipeline) can resolve an
    HSN/SAC code from free text instead of guessing or hardcoding one.
    """
    classifications = db.query(BillingClassification).filter(BillingClassification.active.is_(True)).all()
    return match_billing_classifications(description, classifications, limit=limit)

from fastapi import HTTPException

class BillingClassificationCreate(BaseModel):
    category: str
    description: str
    item_type: str = "SERVICE"
    hsn_sac_code: str
    hsn_sac_type: str
    gst_rate: Decimal
    keywords: Optional[str] = None
    active: bool = True

class BillingClassificationUpdate(BaseModel):
    category: Optional[str] = None
    description: Optional[str] = None
    item_type: Optional[str] = None
    hsn_sac_code: Optional[str] = None
    hsn_sac_type: Optional[str] = None
    gst_rate: Optional[Decimal] = None
    keywords: Optional[str] = None
    active: Optional[bool] = None

@router.post("", response_model=BillingClassificationResponse)
def create_billing_classification(
    data: BillingClassificationCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    classification = BillingClassification(**data.dict())
    db.add(classification)
    db.commit()
    db.refresh(classification)
    return classification

@router.put("/{id}", response_model=BillingClassificationResponse)
def update_billing_classification(
    id: str,
    data: BillingClassificationUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    classification = db.query(BillingClassification).filter(BillingClassification.id == id).first()
    if not classification:
        raise HTTPException(status_code=404, detail="Billing classification not found")
        
    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(classification, key, value)
        
    db.commit()
    db.refresh(classification)
    return classification

@router.delete("/{id}")
def delete_billing_classification(
    id: str,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    classification = db.query(BillingClassification).filter(BillingClassification.id == id).first()
    if not classification:
        raise HTTPException(status_code=404, detail="Billing classification not found")
        
    classification.active = False
    db.commit()
    return {"message": "Billing classification disabled"}
