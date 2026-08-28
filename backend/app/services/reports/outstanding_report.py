from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date

from app.schemas.report import ReportFilter, ReportResult
from app.services.reports.base_report import BaseReport
from app.models.invoice import Invoice
from app.models.payment import Payment

class OutstandingReport(BaseReport):
    
    def generate(self, db: Session, filters: ReportFilter) -> ReportResult:
        query = db.query(Invoice)
        
        # As of date semantics
        as_of_date = filters.to_date if filters.to_date else datetime.utcnow().date()
        
        # Only include invoices issued on or before the as_of_date
        # In SQL, comparing DateTime to Date is tricky if time is not midnight, but typically invoice_date is fine.
        query = query.filter(Invoice.status == "ISSUED")
        query = query.filter(func.date(Invoice.invoice_date) <= as_of_date)
        
        if filters.client_id:
            query = query.filter(Invoice.client_id == filters.client_id)
        if filters.client_ids:
            query = query.filter(Invoice.client_id.in_(filters.client_ids))
        if filters.project_id:
            query = query.filter(Invoice.project_id == filters.project_id)
        if filters.billing_type:
            query = query.filter(Invoice.billing_type == filters.billing_type)
            
        # Statuses: typically we don't filter invoice status here because it's always ISSUED for outstanding.
        
        invoices = query.all()
        
        columns = [
            "Invoice Number", "Project Name", "Client Name",
            "Invoice Date", "Total Payable", "Collected (As Of)", "Outstanding (As Of)"
        ]
        
        rows = []
        total_outstanding = 0
        
        for inv in invoices:
            # Re-use Phase 5 logic: collected is sum of SUCCESS payments
            # BUT bounded by as_of_date
            collected = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
                Payment.invoice_id == inv.id,
                Payment.status == "SUCCESS",
                func.date(Payment.received_at) <= as_of_date
            ).scalar()
            
            payable = float(inv.total_payable)
            collected = float(collected)
            outstanding = payable - collected
            
            if outstanding > 0:
                rows.append({
                    "Invoice Number": inv.invoice_number,
                    "Project Name": inv.project_name or "N/A",
                    "Client Name": inv.client_name or "N/A",
                    "Invoice Date": str(inv.invoice_date.date()) if inv.invoice_date else "",
                    "Total Payable": payable,
                    "Collected (As Of)": collected,
                    "Outstanding (As Of)": outstanding
                })
                total_outstanding += outstanding
                
        totals = {
            "Total Outstanding": total_outstanding
        }
        
        return ReportResult(
            report_type="OUTSTANDING",
            columns=columns,
            rows=rows,
            totals=totals,
            generated_at=datetime.utcnow()
        )
