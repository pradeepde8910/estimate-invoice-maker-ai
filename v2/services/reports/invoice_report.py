from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from v2.schemas.report import ReportFilter, ReportResult
from v2.services.reports.base_report import BaseReport
from v2.models.invoice import Invoice
from v2.services.report_filters import apply_common_filters

class InvoiceReport(BaseReport):
    
    def generate(self, db: Session, filters: ReportFilter) -> ReportResult:
        query = db.query(Invoice)
        query = apply_common_filters(query, filters, Invoice, Invoice.invoice_date)
        
        # Order by invoice_date descending
        query = query.order_by(Invoice.invoice_date.desc().nullslast())
        
        invoices = query.all()
        
        columns = [
            "Invoice Number", "Project Name", "Client Name", "Billing Type",
            "Invoice Date", "Due Date", "Status", "Payment Status",
            "Subtotal", "Gross Amount", "Total Payable"
        ]
        
        rows = []
        total_subtotal = 0
        total_gross = 0
        total_payable = 0
        
        for inv in invoices:
            rows.append({
                "Invoice Number": inv.invoice_number or "DRAFT",
                "Project Name": inv.project_name or "N/A",
                "Client Name": inv.client_name or "N/A",
                "Billing Type": inv.billing_type,
                "Invoice Date": str(inv.invoice_date.date()) if inv.invoice_date else "",
                "Due Date": str(inv.due_date.date()) if inv.due_date else "",
                "Status": inv.status,
                "Payment Status": inv.payment_status,
                "Subtotal": float(inv.subtotal),
                "Gross Amount": float(inv.gross_amount),
                "Total Payable": float(inv.total_payable)
            })
            total_subtotal += float(inv.subtotal)
            total_gross += float(inv.gross_amount)
            total_payable += float(inv.total_payable)
            
        totals = {
            "Subtotal": total_subtotal,
            "Gross Amount": total_gross,
            "Total Payable": total_payable
        }
        
        return ReportResult(
            report_type="INVOICE",
            columns=columns,
            rows=rows,
            totals=totals,
            generated_at=datetime.utcnow()
        )
