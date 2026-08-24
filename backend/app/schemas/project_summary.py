from pydantic import BaseModel, ConfigDict
from decimal import Decimal
from typing import List, Optional
from datetime import date

class MilestoneSimple(BaseModel):
    id: str
    name: str
    amount: Decimal
    target_date: date | None = None
    status: str
    
    model_config = ConfigDict(from_attributes=True)

class CommercialComponentSimple(BaseModel):
    id: str
    name: str
    amount: Decimal
    billed_amount: Decimal
    component_type: str
    billing_policy: str
    status: str
    
    model_config = ConfigDict(from_attributes=True)

class Financials(BaseModel):
    contract_value: Decimal
    total_billed: Decimal
    total_paid: Decimal
    remaining_contract: Decimal
    reserved_contingency: Decimal
    outstanding: Decimal
    total_subtotal: Decimal
    total_invoiced: Decimal
    total_tds: Decimal
    total_payable: Decimal
    total_collected: Decimal
    
    model_config = ConfigDict(from_attributes=True)

class ProjectFinancialSummary(BaseModel):
    project_id: str
    project_name: str
    project_number: str
    billing_type: Optional[str] = None
    delivery_unit_label: Optional[str] = "Milestone"
    financials: Financials
    milestones: List[MilestoneSimple]
    components: List[CommercialComponentSimple] = []
    
    model_config = ConfigDict(from_attributes=True)

class BillingPreviewClassification(BaseModel):
    id: str
    hsn_sac: str
    gst_rate: Decimal

class BillingPreviewTask(BaseModel):
    task_key: str
    requirement_name: str | None = None
    description: str
    amount: Decimal
    hours: Optional[Decimal] = None
    classification: Optional[BillingPreviewClassification] = None

class BillingPreviewMilestone(BaseModel):
    id: str
    name: str
    status: str
    tasks: List[BillingPreviewTask]

class BillingPreviewResponse(BaseModel):
    milestones: List[BillingPreviewMilestone]
