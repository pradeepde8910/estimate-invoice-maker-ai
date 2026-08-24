from pydantic import BaseModel, condecimal, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal

class PaymentInitiateRequest(BaseModel):
    amount: condecimal(ge=Decimal('0.01'), decimal_places=2) # type: ignore
    payment_method: Optional[str] = None
    remarks: Optional[str] = None

class PaymentManualRequest(BaseModel):
    """For recording a payment that has already happened outside the app
    (cash handed over, bank transfer received, etc.) — goes straight to
    SUCCESS in one atomic step instead of the initiate/processing/success
    gateway-style lifecycle, which is unnecessary friction for manual entry."""
    amount: condecimal(ge=Decimal('0.01'), decimal_places=2) # type: ignore
    payment_method: str = Field(..., description="e.g. CASH, BANK_TRANSFER, UPI, CHEQUE, CARD, OTHER")
    payment_date: Optional[datetime] = Field(None, description="When the money was actually received; defaults to now")
    transaction_reference: Optional[str] = Field(None, description="External bank/UPI/cheque reference, if any")
    remarks: Optional[str] = None

class PaymentSuccessRequest(BaseModel):
    received_at: datetime
    transaction_reference: Optional[str] = None
    remarks: Optional[str] = None

class PaymentFailureRequest(BaseModel):
    remarks: Optional[str] = None

class PaymentCorrectionRequest(BaseModel):
    corrected_amount: condecimal(ge=Decimal('0.00'), decimal_places=2) # type: ignore
    reason: str = Field(..., min_length=5)

class PaymentResponse(BaseModel):
    id: str
    invoice_id: str
    amount: Decimal
    status: str
    initiated_at: datetime
    received_at: Optional[datetime]
    payment_date: Optional[datetime] = None
    payment_reference: Optional[str] = None
    payment_method: Optional[str]
    transaction_reference: Optional[str]
    remarks: Optional[str]

    class Config:
        from_attributes = True
