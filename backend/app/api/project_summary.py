from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.api.dependencies import require_roles
from app.schemas.project_summary import ProjectFinancialSummary
from app.api.invoice import InvoiceResponse
from app.schemas.payment import PaymentResponse
# Assuming we have a MilestoneResponse schema in project schemas, otherwise just returning dicts or generic responses.
# I will use a local simple schema for milestones if not available, or just dicts for now to meet the requirements.
from pydantic import BaseModel
from decimal import Decimal
from datetime import date

class MilestoneSimpleResponse(BaseModel):
    id: str
    milestone_name: str
    amount: Decimal
    target_date: date
    status: str

    class Config:
        from_attributes = True

from app.services.project_summary_service import (
    get_project_summary,
    get_project_invoices,
    get_project_payments,
    get_project_milestones,
    FinancialIntegrityError
)

router = APIRouter(prefix="/{project_id}")

@router.get("/summary", response_model=ProjectFinancialSummary)
def read_project_summary(
    project_id: str, 
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance"))
):
    try:
        return get_project_summary(db, project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FinancialIntegrityError as e:
        raise HTTPException(status_code=500, detail=f"Financial Integrity Error: {str(e)}")

@router.get("/invoices", response_model=List[InvoiceResponse])
def read_project_invoices(
    project_id: str, 
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance"))
):
    try:
        return get_project_invoices(db, project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/payments", response_model=List[PaymentResponse])
def read_project_payments(
    project_id: str, 
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance"))
):
    try:
        return get_project_payments(db, project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/milestones", response_model=List[MilestoneSimpleResponse])
def read_project_milestones(
    project_id: str, 
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance"))
):
    try:
        return get_project_milestones(db, project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
