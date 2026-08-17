from pydantic import BaseModel, Field, root_validator
from typing import Optional
from decimal import Decimal

class InvoiceCreateRequest(BaseModel):
    billing_type: str = Field(..., description="Must be MILESTONE or PERCENTAGE")
    milestone_id: Optional[str] = Field(None, description="Required if billing_type is MILESTONE")
    billing_percentage: Optional[Decimal] = Field(None, description="Required if billing_type is PERCENTAGE")
    tds_applicable: bool = Field(False, description="Whether TDS should be applied")
    hsn_sac_override: Optional[str] = Field(None, description="Optional override for HSN/SAC code")

    @root_validator(pre=True)
    def validate_billing_params(cls, values):
        btype = values.get('billing_type')
        if btype == 'MILESTONE' and not values.get('milestone_id'):
            raise ValueError("milestone_id is required for MILESTONE billing")
        if btype == 'PERCENTAGE' and values.get('billing_percentage') is None:
            raise ValueError("billing_percentage is required for PERCENTAGE billing")
        return values

class InvoiceStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="Must be DRAFT, ISSUED, or CANCELLED")
