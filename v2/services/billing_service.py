from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session
from sqlalchemy import func
from v2.models.project import Project
from v2.models.invoice import Invoice

class OverBillingError(ValueError):
    """Raised when a billing request exceeds the project's contract value."""
    pass

def calculate_percentage_billing(contract_value: Decimal, percentage: Decimal) -> Decimal:
    """Calculates billable amount based on percentage."""
    cv = Decimal(str(contract_value))
    pct = Decimal(str(percentage))
    amount = (cv * (pct / Decimal('100.0'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return amount

def calculate_invoice_financials(subtotal: Decimal, total_gst: Decimal, tds_amount: Decimal) -> dict:
    """
    Computes the final invoice totals.
    Subtotal + GST = Gross Amount
    Gross Amount - TDS = Net Receivable (Total Payable)
    """
    subtotal = Decimal(str(subtotal))
    total_gst = Decimal(str(total_gst))
    tds_amount = Decimal(str(tds_amount))

    gross_amount = subtotal + total_gst
    total_payable = gross_amount - tds_amount

    return {
        "subtotal": subtotal,
        "gross_amount": gross_amount,
        "total_payable": total_payable
    }

def validate_billing_ceiling(session: Session, project_id: str, requested_amount: Decimal) -> Decimal:
    """
    Validates that the requested billing amount does not exceed the remaining contract value.
    Uses SELECT FOR UPDATE to prevent race conditions during concurrent billing events.
    """
    requested_amount = Decimal(str(requested_amount))
    
    from sqlalchemy import text
    if session.bind.dialect.name == "sqlite":
        session.execute(text("UPDATE projects SET id = id WHERE id = :id"), {"id": project_id})
        
    # Lock the project row (native Postgres/MySQL)
    project = session.query(Project).filter(Project.id == project_id).with_for_update().one()
    
    # Calculate already billed amounts (excluding cancelled invoices)
    billed_sum_val = session.query(func.sum(Invoice.subtotal)).filter(
        Invoice.project_id == project_id,
        Invoice.status != 'CANCELLED'
    ).scalar()
    
    billed_sum = Decimal(str(billed_sum_val)) if billed_sum_val is not None else Decimal('0.00')
    remaining_billable = project.contract_value - billed_sum
    
    if requested_amount > remaining_billable:
        raise OverBillingError(
            f"Over-billing attempt. Contract value: {project.contract_value}, "
            f"Already billed: {billed_sum}, Remaining: {remaining_billable}. "
            f"Requested: {requested_amount}"
        )
        
    return remaining_billable
