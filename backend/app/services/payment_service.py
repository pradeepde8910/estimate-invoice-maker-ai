import json
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.invoice import Invoice
from app.models.payment import Payment, PaymentSequence
from app.models.audit import AuditLog
from app.schemas.payment import (
    PaymentInitiateRequest,
    PaymentManualRequest,
    PaymentSuccessRequest,
    PaymentFailureRequest,
    PaymentCorrectionRequest
)

class InvalidStateTransitionError(ValueError):
    pass

class PaymentValidationError(ValueError):
    pass


def get_invoice_balance(db: Session, invoice_id: str) -> Decimal:
    """Computes the remaining balance dynamically based on SUCCESS payments."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise ValueError("Invoice not found")
        
    success_total = db.query(func.sum(Payment.amount)).filter(
        Payment.invoice_id == invoice_id,
        Payment.status == "SUCCESS"
    ).scalar() or Decimal('0.00')
    
    return invoice.total_payable - success_total


def _derive_payment_status(total_payable: Decimal, success_total: Decimal) -> str:
    if success_total == Decimal('0.00'):
        return "UNPAID"
    elif success_total < total_payable:
        return "PARTIALLY_PAID"
    elif success_total == total_payable:
        return "PAID"
    else:
        raise PaymentValidationError("Financial Integrity Violation: Successful payments exceed total payable.")


def generate_payment_reference(db: Session) -> str:
    """Atomic per-financial-year voucher number (PAY/2026-27/00001), same
    upsert pattern as invoice_service.generate_invoice_number — a single
    INSERT .. ON CONFLICT DO UPDATE .. RETURNING avoids the SELECT-then-UPDATE
    race that would otherwise let two concurrent payments mint the same number."""
    from app.services.invoice_service import get_financial_year
    fy = get_financial_year()

    dialect = db.bind.dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as upsert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as upsert
    else:
        raise NotImplementedError(f"generate_payment_reference: unsupported dialect '{dialect}'")

    stmt = upsert(PaymentSequence).values(financial_year=fy, next_value=2)
    stmt = stmt.on_conflict_do_update(
        index_elements=["financial_year"],
        set_={"next_value": PaymentSequence.next_value + 1},
    ).returning(PaymentSequence.next_value)

    next_value_after = db.execute(stmt).scalar_one()
    current = next_value_after - 1
    return f"PAY/{fy}/{current:05d}"


def record_manual_payment(db: Session, invoice_id: str, request: PaymentManualRequest, user_id: str = "system") -> Payment:
    """Records a payment that already happened outside the app (cash, bank
    transfer, UPI, cheque) as a single atomic operation — validates against
    the outstanding balance and goes straight to SUCCESS, instead of forcing
    manual entry through the initiate/processing/success gateway lifecycle
    that only makes sense when an actual payment gateway is driving the
    transitions asynchronously."""
    try:
        if db.bind.dialect.name == "sqlite":
            # Force a write lock on the invoice row for SQLite (see record_payment_success
            # for the same pattern/rationale — SQLAlchemy's with_for_update() is a no-op
            # SELECT on SQLite, so a real write is needed to serialize concurrent callers).
            from sqlalchemy import text
            db.execute(text("UPDATE invoices SET id = id WHERE id = :inv_id"), {"inv_id": invoice_id})

        invoice = db.query(Invoice).with_for_update().filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise ValueError("Invoice not found")

        if invoice.status != "ISSUED":
            raise InvalidStateTransitionError("Payments can only be recorded against an ISSUED invoice.")

        if invoice.payment_status == "PAID":
            raise InvalidStateTransitionError("Cannot record payment: Invoice is already PAID.")

        success_total = db.query(func.sum(Payment.amount)).filter(
            Payment.invoice_id == invoice.id,
            Payment.status == "SUCCESS"
        ).scalar() or Decimal('0.00')

        new_success_total = success_total + request.amount

        if new_success_total > invoice.total_payable:
            balance = invoice.total_payable - success_total
            raise PaymentValidationError(
                f"Payment rejected: ₹{request.amount} exceeds the outstanding balance of ₹{balance}."
            )

        received_at = datetime.utcnow()
        payment = Payment(
            invoice_id=invoice.id,
            amount=request.amount,
            payment_method=request.payment_method,
            payment_date=request.payment_date or received_at,
            payment_reference=generate_payment_reference(db),
            transaction_reference=request.transaction_reference,
            remarks=request.remarks,
            status="SUCCESS",
            received_at=received_at,
        )
        db.add(payment)
        db.flush()

        invoice.payment_status = _derive_payment_status(invoice.total_payable, new_success_total)
        db.add(invoice)

        audit = AuditLog(
            action="PAYMENT_RECORDED_MANUAL",
            user_id=user_id,
            details=json.dumps({
                "entity_type": "PAYMENT",
                "entity_id": payment.id,
                "amount": str(request.amount),
                "payment_method": request.payment_method,
                "payment_reference": payment.payment_reference,
                "new_invoice_payment_status": invoice.payment_status,
            })
        )
        db.add(audit)

        db.commit()
        db.refresh(payment)
        return payment
    except Exception:
        db.rollback()
        raise


def list_payments(db: Session, invoice_id: str) -> list[Payment]:
    return (
        db.query(Payment)
        .filter(Payment.invoice_id == invoice_id)
        .order_by(Payment.created_at.desc())
        .all()
    )


def initiate_payment(db: Session, invoice_id: str, request: PaymentInitiateRequest, user_id: str = "system") -> Payment:
    try:
        # We do NOT lock the invoice here because initiation doesn't change the invoice state,
        # but we must validate the invoice is ISSUED.
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise ValueError("Invoice not found")
            
        if invoice.status != "ISSUED":
            raise InvalidStateTransitionError("Payments can only be initiated against an ISSUED invoice.")
            
        if invoice.payment_status == "PAID":
            raise InvalidStateTransitionError("Cannot initiate payment: Invoice is already PAID.")
            
        payment = Payment(
            invoice_id=invoice.id,
            amount=request.amount,
            payment_method=request.payment_method,
            remarks=request.remarks,
            status="INITIATED"
        )
        db.add(payment)
        db.flush()
        
        audit = AuditLog(
            action="PAYMENT_INITIATED",
            user_id=user_id,
            details=json.dumps({"entity_type": "PAYMENT", "entity_id": payment.id, "amount": str(request.amount)})
        )
        db.add(audit)
        db.commit()
        db.refresh(payment)
        return payment
    except Exception:
        db.rollback()
        raise


def transition_payment_processing(db: Session, payment_id: str, user_id: str = "system") -> Payment:
    try:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            raise ValueError("Payment not found")
            
        if payment.status != "INITIATED":
            raise InvalidStateTransitionError(f"Cannot transition to PROCESSING from {payment.status}")
            
        payment.status = "PROCESSING"
        db.add(payment)
        
        audit = AuditLog(
            action="PAYMENT_PROCESSING",
            user_id=user_id,
            details=json.dumps({"entity_type": "PAYMENT", "entity_id": payment.id, "status": "PROCESSING"})
        )
        db.add(audit)
        db.commit()
        db.refresh(payment)
        return payment
    except Exception:
        db.rollback()
        raise


def record_payment_success(db: Session, payment_id: str, request: PaymentSuccessRequest, user_id: str = "system") -> Payment:
    try:
        # 1. Lock Invoice FOR UPDATE
        # 2. Lock Payment FOR UPDATE
        # The order of locking matters to avoid deadlocks. We lock the Payment first, get the invoice_id, then lock Invoice.
        
        payment = db.query(Payment).with_for_update().filter(Payment.id == payment_id).first()
        if not payment:
            raise ValueError("Payment not found")
            
        from sqlalchemy import text
        if db.bind.dialect.name == "sqlite":
            # Force write lock in SQLite for concurrency safety
            db.execute(text("UPDATE invoices SET id = id WHERE id = :inv_id"), {"inv_id": payment.invoice_id})
            # MUST refresh payment state because another thread might have updated it while we were waiting for the lock
            db.refresh(payment)
            
        invoice = db.query(Invoice).with_for_update().filter(Invoice.id == payment.invoice_id).first()
        if not invoice:
            raise ValueError("Invoice not found")
            
        # Validations
        if invoice.status != "ISSUED":
            raise InvalidStateTransitionError("Cannot record payment success against a non-ISSUED invoice.")
            
        if payment.status not in ("INITIATED", "PROCESSING"):
            raise InvalidStateTransitionError(f"Cannot transition to SUCCESS from {payment.status}")
            
        # Compute current SUCCESS total
        success_total = db.query(func.sum(Payment.amount)).filter(
            Payment.invoice_id == invoice.id,
            Payment.status == "SUCCESS"
        ).scalar() or Decimal('0.00')
        
        new_success_total = success_total + payment.amount
        
        # Overpayment Guard
        if new_success_total > invoice.total_payable:
            raise PaymentValidationError("Payment rejected: Amount exceeds outstanding invoice balance.")
            
        # Mark SUCCESS
        payment.status = "SUCCESS"
        payment.received_at = request.received_at
        if request.transaction_reference:
            payment.transaction_reference = request.transaction_reference
        if request.remarks:
            payment.remarks = request.remarks
            
        db.add(payment)
        
        # Derive Invoice Status
        invoice.payment_status = _derive_payment_status(invoice.total_payable, new_success_total)
        db.add(invoice)
        
        audit = AuditLog(
            action="PAYMENT_SUCCESS",
            user_id=user_id,
            details=json.dumps({
                "entity_type": "PAYMENT",
                "entity_id": payment.id,
                "amount": str(payment.amount),
                "new_invoice_status": invoice.payment_status,
                "received_at": request.received_at.isoformat()
            })
        )
        db.add(audit)
        
        db.commit()
        db.refresh(payment)
        return payment
    except Exception:
        db.rollback()
        raise


def record_payment_failure(db: Session, payment_id: str, request: PaymentFailureRequest, user_id: str = "system") -> Payment:
    try:
        payment = db.query(Payment).with_for_update().filter(Payment.id == payment_id).first()
        if not payment:
            raise ValueError("Payment not found")
            
        if payment.status not in ("INITIATED", "PROCESSING"):
            raise InvalidStateTransitionError(f"Cannot transition to FAILED from {payment.status}")
            
        payment.status = "FAILED"
        if request.remarks:
            payment.remarks = request.remarks
        db.add(payment)
        
        audit = AuditLog(
            action="PAYMENT_FAILED",
            user_id=user_id,
            details=json.dumps({"entity_type": "PAYMENT", "entity_id": payment.id, "remarks": request.remarks})
        )
        db.add(audit)
        db.commit()
        db.refresh(payment)
        return payment
    except Exception:
        db.rollback()
        raise


def correct_erroneous_payment(db: Session, payment_id: str, request: PaymentCorrectionRequest, user_id: str = "system") -> Payment:
    try:
        # This acts as an admin override with strict auditing
        # It must lock everything precisely like success transition if it alters SUCCESS amounts.
        
        payment = db.query(Payment).with_for_update().filter(Payment.id == payment_id).first()
        if not payment:
            raise ValueError("Payment not found")
            
        invoice = db.query(Invoice).with_for_update().filter(Invoice.id == payment.invoice_id).first()
        if not invoice:
            raise ValueError("Invoice not found")
            
        old_amount = payment.amount
        
        # If it was a SUCCESS payment, changing its amount affects the invoice balance.
        if payment.status == "SUCCESS":
            # Calculate what the total *would* be without this payment
            other_success_total = db.query(func.sum(Payment.amount)).filter(
                Payment.invoice_id == invoice.id,
                Payment.status == "SUCCESS",
                Payment.id != payment.id
            ).scalar() or Decimal('0.00')
            
            new_success_total = other_success_total + request.corrected_amount
            
            if new_success_total > invoice.total_payable:
                raise PaymentValidationError("Correction rejected: Amount exceeds outstanding invoice balance.")
                
            invoice.payment_status = _derive_payment_status(invoice.total_payable, new_success_total)
            db.add(invoice)
            
        payment.amount = request.corrected_amount
        db.add(payment)
        
        audit = AuditLog(
            action="PAYMENT_CORRECTION",
            user_id=user_id,
            details=json.dumps({
                "entity_type": "PAYMENT",
                "entity_id": payment.id,
                "old_amount": str(old_amount),
                "new_amount": str(request.corrected_amount),
                "reason": request.reason
            })
        )
        db.add(audit)
        
        db.commit()
        db.refresh(payment)
        return payment
    except Exception:
        db.rollback()
        raise
