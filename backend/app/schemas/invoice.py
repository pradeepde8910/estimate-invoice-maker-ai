from pydantic import BaseModel, Field, model_validator, root_validator
from typing import Optional
from decimal import Decimal

from typing import List

class InvoiceItemCreateRequest(BaseModel):
    source_type: str = Field(..., description="Must be MILESTONE, COMPONENT, or CUSTOM")
    source_id: Optional[str] = Field(
        None,
        description="ID of the milestone or component. Not applicable (and not required) for CUSTOM line items.",
    )
    task_key: Optional[str] = Field(None, description="Stable identifier for the specific task within the milestone")
    requirement_name: Optional[str] = Field(None, description="Name of the parent requirement")
    amount: Decimal = Field(..., description="Amount to bill for this line item")
    description: str = Field(..., description="Description for this line item")
    hours: Optional[Decimal] = Field(None, description="Estimated hours for this specific task")
    billing_classification_id: Optional[str] = Field(
        None,
        description=(
            "ID of the chosen entry in the billing_classifications catalog "
            "(from GET /api/master/billing-classifications/match). If omitted, "
            "the server auto-matches from `description`; if that yields no "
            "confident match, invoice creation fails rather than silently "
            "applying a generic fallback code."
        ),
    )
    classification_source: Optional[str] = Field(None, description="AUTO_MATCHED, MANUAL, or UNCLASSIFIED")

    @model_validator(mode='after')
    def validate_source_id(self):
        if self.source_type in ('MILESTONE', 'COMPONENT') and not self.source_id:
            raise ValueError(f"source_id is required for source_type '{self.source_type}'")
        return self

class InvoiceCreateRequest(BaseModel):
    items: List[InvoiceItemCreateRequest] = Field(..., min_items=1)
    tds_applicable: bool = Field(False, description="Whether TDS should be applied")
    po_number: Optional[str] = Field(None, description="Client purchase order reference, if any")
    payment_terms: Optional[str] = Field(None, description="e.g. 'Net 30'")
    discount_amount: Optional[Decimal] = Field(None, description="Flat discount applied to the taxable value before GST")

    @root_validator(pre=True)
    def validate_billing_params(cls, values):
        items = values.get('items', [])
        if not items:
            raise ValueError("At least one invoice item is required")
        return values


class StandaloneInvoiceCreateRequest(BaseModel):
    """Same commercial shape as InvoiceCreateRequest, but for an invoice with
    no project behind it — every item is CUSTOM since there's no
    milestone/component to bill against."""
    client_id: str = Field(..., description="Client to bill")
    items: List[InvoiceItemCreateRequest] = Field(..., min_items=1)
    tds_applicable: bool = Field(False, description="Whether TDS should be applied")
    po_number: Optional[str] = Field(None, description="Client purchase order reference, if any")
    payment_terms: Optional[str] = Field(None, description="e.g. 'Net 30'")
    discount_amount: Optional[Decimal] = Field(None, description="Flat discount applied to the taxable value before GST")

    @model_validator(mode='after')
    def validate_items_are_custom(self):
        non_custom = [i.description for i in self.items if i.source_type != 'CUSTOM']
        if non_custom:
            raise ValueError(
                f"Standalone invoices can only contain CUSTOM line items (no project to bill "
                f"a milestone/component against): {', '.join(non_custom)}"
            )
        return self

class InvoiceStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="Must be DRAFT, ISSUED, or CANCELLED")

from datetime import datetime

class InvoiceItemSchema(BaseModel):
    id: str
    description: str
    amount: Decimal
    hours: Optional[Decimal] = None
    hsn_sac: Optional[str] = Field(None, validation_alias="hsn_sac_code")
    milestone_id: Optional[str] = None
    component_id: Optional[str] = None
    task_key: Optional[str] = None
    requirement_name: Optional[str] = None
    milestone_name: Optional[str] = None

    class Config:
        from_attributes = True

class InvoiceTaxSchema(BaseModel):
    id: str
    tax_type: str
    percentage: Decimal
    amount: Decimal

    class Config:
        from_attributes = True

class InvoiceTDSSchema(BaseModel):
    id: str
    tds_percentage: Decimal
    tds_amount: Decimal

    class Config:
        from_attributes = True

from app.schemas.payment import PaymentResponse

class InvoiceDetailResponse(BaseModel):
    id: str
    invoice_number: Optional[str]
    invoice_type: str = "PROJECT"
    status: str
    payment_status: str = "UNPAID"
    invoice_date: Optional[datetime]
    due_date: Optional[datetime]

    client_id: str
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    project_number: Optional[str] = None
    project_start_date: Optional[datetime] = None
    project_end_date: Optional[datetime] = None
    
    client_name: Optional[str]
    client_address: Optional[str]
    client_gstin: Optional[str]
    client_email: Optional[str] = None
    client_phone: Optional[str] = None
    
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_ifsc: Optional[str] = None
    invoice_terms: Optional[str] = None

    po_number: Optional[str] = None
    payment_terms: Optional[str] = None

    subtotal: Decimal
    discount_amount: Decimal = Decimal('0.00')
    gross_amount: Decimal
    total_payable: Decimal
    amount_paid: Decimal = Decimal('0.00')
    balance_due: Decimal = Decimal('0.00')

    items: list[InvoiceItemSchema] = []
    taxes: list[InvoiceTaxSchema] = []
    tds: Optional[InvoiceTDSSchema] = None
    payments: list[PaymentResponse] = []

    class Config:
        from_attributes = True
