from pydantic import BaseModel, condecimal, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal

class PaymentInitiateRequest(BaseModel):
    amount: condecimal(ge=Decimal('0.01'), decimal_places=2) # type: ignore
    payment_method: Optional[str] = None
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
    payment_method: Optional[str]
    transaction_reference: Optional[str]
    remarks: Optional[str]

    class Config:
        from_attributes = True
