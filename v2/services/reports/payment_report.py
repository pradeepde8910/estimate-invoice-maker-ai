from sqlalchemy.orm import Session
from datetime import datetime

from v2.schemas.report import ReportFilter, ReportResult
from v2.services.reports.base_report import BaseReport
from v2.models.payment import Payment
from v2.models.invoice import Invoice
from v2.services.report_filters import apply_common_filters

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
        if filters.project_id:
            query = query.filter(Invoice.project_id == filters.project_id)
        if filters.statuses:
            query = query.filter(Payment.status.in_(filters.statuses))
        if filters.billing_type:
            query = query.filter(Invoice.billing_type == filters.billing_type)
            
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
                "Payment Reference": payment.reference_number or payment.id[:8],
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
