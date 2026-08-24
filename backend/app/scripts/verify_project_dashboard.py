import sys
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import text

# Add the project root to the path so we can import v2
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.database import SessionLocal, engine
from app.models.base import Base
from app.models.project import Project
from app.models.master import Client
from app.schemas.invoice import InvoiceCreateRequest
from app.schemas.payment import PaymentInitiateRequest, PaymentSuccessRequest
from app.services.invoice_service import create_invoice, transition_invoice_status
from app.services.payment_service import initiate_payment, transition_payment_processing, record_payment_success
from app.services.project_summary_service import get_project_summary
from datetime import datetime

def run_verification():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Get a project that has invoices
        project_id_row = db.execute(text("SELECT project_id FROM invoices LIMIT 1")).fetchone()
        
        if not project_id_row:
            print("No projects with invoices found. Seeding mock data...")
            import uuid
            uid = str(uuid.uuid4())[:8]
            client = Client(company_name=f"Verify Client {uid}")
            db.add(client)
            db.flush()
            project = Project(client_id=client.id, project_number=f"P-VERIFY-{uid}", project_name="Verify Dashboard", contract_value=Decimal('500000.00'))
            db.add(project)
            db.commit()
            
            # Create an invoice
            req = InvoiceCreateRequest(billing_type="PERCENTAGE", billing_percentage=Decimal('50.00'), tds_applicable=True, tds_rate=Decimal('10.00'))
            inv = create_invoice(db, project.id, req)
            transition_invoice_status(db, inv.id, "ISSUED")
            
            # Make a payment
            p = initiate_payment(db, inv.id, PaymentInitiateRequest(amount=Decimal('100000.00')))
            transition_payment_processing(db, p.id)
            record_payment_success(db, p.id, PaymentSuccessRequest(received_at=datetime.utcnow()))
            
            project_id = project.id
        else:
            project_id = project_id_row[0]
            
        # 1. Fetch via Service Layer (the dashboard output)
        print(f"Fetching summary for project: {project_id}")
        summary = get_project_summary(db, project_id)
        
        # 2. Independent Raw SQL Calculation
        # Raw Subtotal, Gross, Payable
        sql_invoices = text("""
            SELECT 
                COALESCE(SUM(subtotal), 0) as total_subtotal,
                COALESCE(SUM(gross_amount), 0) as total_gross,
                COALESCE(SUM(total_payable), 0) as total_payable
            FROM invoices
            WHERE project_id = :pid AND status = 'ISSUED'
        """)
        inv_row = db.execute(sql_invoices, {"pid": project_id}).fetchone()
        
        # Raw TDS
        sql_tds = text("""
            SELECT COALESCE(SUM(t.tds_amount), 0) as total_tds
            FROM invoice_tds t
            JOIN invoices i ON t.invoice_id = i.id
            WHERE i.project_id = :pid AND i.status = 'ISSUED'
        """)
        tds_row = db.execute(sql_tds, {"pid": project_id}).fetchone()
        
        # Raw Collected
        sql_collected = text("""
            SELECT COALESCE(SUM(p.amount), 0) as total_collected
            FROM payments p
            JOIN invoices i ON p.invoice_id = i.id
            WHERE i.project_id = :pid AND i.status = 'ISSUED' AND p.status = 'SUCCESS'
        """)
        collected_row = db.execute(sql_collected, {"pid": project_id}).fetchone()
        
        # Project Contract Value
        sql_project = text("SELECT COALESCE(contract_value, 0) FROM projects WHERE id = :pid")
        contract_val = db.execute(sql_project, {"pid": project_id}).scalar()
        
        # Compare
        raw_contract = Decimal(str(contract_val))
        raw_subtotal = Decimal(str(inv_row[0]))
        raw_gross = Decimal(str(inv_row[1]))
        raw_payable = Decimal(str(inv_row[2]))
        raw_tds = Decimal(str(tds_row[0]))
        raw_collected = Decimal(str(collected_row[0]))
        raw_outstanding = raw_payable - raw_collected
        raw_remaining = raw_contract - raw_subtotal
        
        print("--- Dashboard Output ---")
        print(summary.model_dump_json(indent=2))
        
        print("\n--- Raw SQL Output ---")
        print(f"Contract: {raw_contract}")
        print(f"Subtotal: {raw_subtotal}")
        print(f"Invoiced (Gross): {raw_gross}")
        print(f"TDS: {raw_tds}")
        print(f"Payable: {raw_payable}")
        print(f"Collected: {raw_collected}")
        print(f"Outstanding: {raw_outstanding}")
        print(f"Remaining Billable: {raw_remaining}")
        
        # Assertions
        assert summary.contract_value == raw_contract, "Contract value mismatch"
        assert summary.total_subtotal == raw_subtotal, "Subtotal mismatch"
        assert summary.total_invoiced == raw_gross, "Gross invoiced mismatch"
        assert summary.total_tds == raw_tds, "TDS mismatch"
        assert summary.total_payable == raw_payable, "Total payable mismatch"
        assert summary.total_collected == raw_collected, "Total collected mismatch"
        assert summary.outstanding == raw_outstanding, "Outstanding mismatch"
        assert summary.remaining_billable == raw_remaining, "Remaining billable mismatch"
        
        print("\n[SUCCESS] Verification Successful: Dashboard output perfectly matches raw SQL aggregates.")
        
    finally:
        db.close()

if __name__ == "__main__":
    run_verification()
