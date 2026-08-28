from sqlalchemy.orm import Session
from datetime import datetime

from app.schemas.report import ReportFilter, ReportResult
from app.services.reports.base_report import BaseReport
from app.models.payment import Payment
from app.models.invoice import Invoice
from app.services.report_filters import apply_common_filters

class PaymentReport(BaseReport):
    
    def generate(self, db: Session, filters: ReportFilter) -> ReportResult:
        query = db.query(Payment, Invoice).join(Invoice, Payment.invoice_id == Invoice.id)
        
        # Payment specific date filter applies to received_at
        if filters.from_date:
            query = query.filter(Payment.received_at >= filters.from_date)
        if filters.to_date:
            query = query.filter(Payment.received_at <= filters.to_date)
            
        # Apply invoice level filters (like client_id, project_id) by wrapping them
        # Wait, apply_common_filters expects the model. We can pass Invoice for project/client
        # But we must handle 'status' carefully since both have status.
        # Let's handle Payment specific filters manually or partially manually to avoid collisions.
        
        if filters.client_id:
            query = query.filter(Invoice.client_id == filters.client_id)
        if filters.client_ids:
            query = query.filter(Invoice.client_id.in_(filters.client_ids))
        if filters.project_id:
            query = query.filter(Invoice.project_id == filters.project_id)
        if filters.statuses:
            query = query.filter(Payment.status.in_(filters.statuses))
        # billing_type isn't a real column on Invoice (it's a computed
        # @property backed by ProjectBillingConfig via the project), so unlike
        # client_id/project_id/statuses above there's no plain column to
        # filter on here — silently ignored, matching how apply_common_filters
        # treats non-column billing_type elsewhere, rather than referencing a
        # nonexistent attribute and raising.


        query = query.order_by(Payment.received_at.desc().nullslast())
        
        results = query.all()
        
        columns = [
            "Payment Reference", "Invoice Number", "Project Name", "Client Name",
            "Payment Method", "Status", "Initiated At", "Received At", "Amount"
        ]
        
        rows = []
        total_amount = 0
        
        for payment, inv in results:
            rows.append({
                "Payment Reference": payment.payment_reference or payment.id[:8],
                "Invoice Number": inv.invoice_number or "DRAFT",
                "Project Name": inv.project_name or "N/A",
                "Client Name": inv.client_name or "N/A",
                "Payment Method": payment.payment_method or "N/A",
                "Status": payment.status,
                "Initiated At": str(payment.initiated_at),
                "Received At": str(payment.received_at) if payment.received_at else "",
                "Amount": float(payment.amount)
            })
            if payment.status == "SUCCESS":
                total_amount += float(payment.amount)
                
        totals = {
            "Total Successful Collections": total_amount
        }
        
        return ReportResult(
            report_type="PAYMENT",
            columns=columns,
            rows=rows,
            totals=totals,
            generated_at=datetime.utcnow()
        )
