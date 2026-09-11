from fastapi import APIRouter, Depends, Query
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, condecimal
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

# gst_rate is stored as Numeric(5, 2) (see BillingClassification model), so it
# can hold at most 999.99 - constrain it to a sane percentage range up front
# instead of letting an out-of-range value fall through to a raw DB error.
GstRate = condecimal(ge=0, le=100, decimal_places=2)

class BillingClassificationCreate(BaseModel):
    category: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1)
    item_type: str = Field("SERVICE", max_length=20)
    hsn_sac_code: str = Field(..., min_length=1, max_length=50)
    hsn_sac_type: str = Field(..., max_length=10)
    gst_rate: GstRate
    keywords: Optional[str] = None
    active: bool = True

class BillingClassificationUpdate(BaseModel):
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, min_length=1)
    item_type: Optional[str] = Field(None, max_length=20)
    hsn_sac_code: Optional[str] = Field(None, min_length=1, max_length=50)
    hsn_sac_type: Optional[str] = Field(None, max_length=10)
    gst_rate: Optional[GstRate] = None
    keywords: Optional[str] = None
    active: Optional[bool] = None

@router.post("", response_model=BillingClassificationResponse)
def create_billing_classification(
    data: BillingClassificationCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    # Enforce uniqueness on category + description
    existing = db.query(BillingClassification).filter(
        BillingClassification.category == data.category,
        BillingClassification.description == data.description
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="A billing classification with this exact category and description already exists.")

    classification = BillingClassification(**data.dict())
    db.add(classification)
    try:
        db.commit()
    except (DataError, IntegrityError):
        db.rollback()
        raise HTTPException(status_code=400, detail="Could not save classification - please check the values entered.")
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
    
    check_cat = update_data.get('category', classification.category)
    check_desc = update_data.get('description', classification.description)
    if 'category' in update_data or 'description' in update_data:
        existing = db.query(BillingClassification).filter(
            BillingClassification.category == check_cat,
            BillingClassification.description == check_desc,
            BillingClassification.id != id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="A billing classification with this exact category and description already exists.")

    for key, value in update_data.items():
        setattr(classification, key, value)

    try:
        db.commit()
    except (DataError, IntegrityError):
        db.rollback()
        raise HTTPException(status_code=400, detail="Could not save classification - please check the values entered.")
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
