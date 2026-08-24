from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.dependencies import require_roles
from app.schemas.payment import (
    PaymentInitiateRequest,
    PaymentManualRequest,
    PaymentSuccessRequest,
    PaymentFailureRequest,
    PaymentCorrectionRequest,
    PaymentResponse
)
from app.services.payment_service import (
    initiate_payment,
    record_manual_payment,
    list_payments,
    transition_payment_processing,
    record_payment_success,
    record_payment_failure,
    correct_erroneous_payment,
    InvalidStateTransitionError,
    PaymentValidationError
)

router = APIRouter()

@router.get("/{project_id}/invoices/{invoice_id}/payments", response_model=List[PaymentResponse])
def api_list_payments(
    project_id: str,
    invoice_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance"))
):
    return list_payments(db, invoice_id)

@router.post("/{project_id}/invoices/{invoice_id}/payments/manual", response_model=PaymentResponse)
def api_record_manual_payment(
    project_id: str,
    invoice_id: str,
    request: PaymentManualRequest,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance"))
):
    try:
        payment = record_manual_payment(db, invoice_id, request)
        return payment
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PaymentValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{project_id}/invoices/{invoice_id}/payments", response_model=PaymentResponse)
def api_initiate_payment(
    project_id: str, 
    invoice_id: str, 
    request: PaymentInitiateRequest, 
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance"))
):
    try:
        # Note: In a real app we would query the invoice and verify project_id == invoice.project_id
        # The service layer checks if invoice exists.
        payment = initiate_payment(db, invoice_id, request)
        return payment
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{project_id}/invoices/{invoice_id}/payments/{payment_id}/processing", response_model=PaymentResponse)
def api_transition_processing(
    project_id: str, 
    invoice_id: str, 
    payment_id: str, 
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance"))
):
    try:
        payment = transition_payment_processing(db, payment_id)
        return payment
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{project_id}/invoices/{invoice_id}/payments/{payment_id}/success", response_model=PaymentResponse)
def api_record_success(
    project_id: str, 
    invoice_id: str, 
    payment_id: str, 
    request: PaymentSuccessRequest, 
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance"))
):
    try:
        payment = record_payment_success(db, payment_id, request)
        return payment
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PaymentValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{project_id}/invoices/{invoice_id}/payments/{payment_id}/failure", response_model=PaymentResponse)
def api_record_failure(
    project_id: str, 
    invoice_id: str, 
    payment_id: str, 
    request: PaymentFailureRequest, 
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance"))
):
    try:
        payment = record_payment_failure(db, payment_id, request)
        return payment
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.put("/{project_id}/invoices/{invoice_id}/payments/{payment_id}/correct", response_model=PaymentResponse)
def api_correct_payment(
    project_id: str, 
    invoice_id: str, 
    payment_id: str, 
    request: PaymentCorrectionRequest, 
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance"))
):
    try:
        payment = correct_erroneous_payment(db, payment_id, request)
        return payment
    except PaymentValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
