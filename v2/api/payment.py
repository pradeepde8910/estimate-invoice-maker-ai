from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from v2.database import get_db
from v2.api.dependencies import require_roles
from v2.schemas.payment import (
    PaymentInitiateRequest,
    PaymentSuccessRequest,
    PaymentFailureRequest,
    PaymentCorrectionRequest,
    PaymentResponse
)
from v2.services.payment_service import (
    initiate_payment,
    transition_payment_processing,
    record_payment_success,
    record_payment_failure,
    correct_erroneous_payment,
    InvalidStateTransitionError,
    PaymentValidationError
)

router = APIRouter(prefix="/projects", tags=["Payments"])

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
