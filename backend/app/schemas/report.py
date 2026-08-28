from pydantic import BaseModel, ConfigDict, Field, model_validator
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from enum import Enum

class ReportType(str, Enum):
    PROJECT = "PROJECT"
    INVOICE = "INVOICE"
    PAYMENT = "PAYMENT"
    OUTSTANDING = "OUTSTANDING"
    MILESTONE = "MILESTONE"
    TEST = "TEST" # For testing the 6th report extensibility

class ExportFormat(str, Enum):
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"

class ReportFilter(BaseModel):
    project_id: Optional[str] = None
    project_ids: Optional[List[str]] = None  # exact multi-select, e.g. "export exactly what I filtered on screen"
    client_id: Optional[str] = None
    client_ids: Optional[List[str]] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    statuses: Optional[List[str]] = None
    billing_type: Optional[str] = None # Using string here to avoid circular import if BillingType enum isn't easily accessible, or we can use the exact Enum.

    @model_validator(mode='after')
    def validate_dates(self):
        if self.from_date and self.to_date:
            if self.from_date > self.to_date:
                raise ValueError("from_date cannot be greater than to_date")
        return self

class ReportResult(BaseModel):
    report_type: str
    columns: List[str]
    rows: List[Dict[str, Any]]
    totals: Dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=datetime.utcnow)

class ReportRequest(BaseModel):
    filters: ReportFilter
    format: ExportFormat
    selected_columns: Optional[List[str]] = None  # subset of the report's default columns, in the caller's chosen order
