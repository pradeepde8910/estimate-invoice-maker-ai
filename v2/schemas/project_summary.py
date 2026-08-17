from pydantic import BaseModel, ConfigDict
from decimal import Decimal

class ProjectFinancialSummary(BaseModel):
    contract_value: Decimal
    total_subtotal: Decimal
    total_invoiced: Decimal
    total_tds: Decimal
    total_payable: Decimal
    total_collected: Decimal
    outstanding: Decimal
    remaining_billable: Decimal
    
    model_config = ConfigDict(from_attributes=True)
