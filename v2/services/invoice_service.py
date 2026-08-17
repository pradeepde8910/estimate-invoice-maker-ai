from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional

from v2.models.invoice import InvoiceSequence, Invoice, InvoiceItem, InvoiceTax, InvoiceTDS
from v2.models.project import Project, ProjectMilestone, ProjectBillingConfig
from v2.models.master import Client, HSNSACMaster, TaxRate
from v2.models.audit import AuditLog
from v2.models.payment import Payment

from v2.services.billing_service import validate_billing_ceiling, calculate_percentage_billing, calculate_invoice_financials
from v2.services.tax_service import calculate_gst, calculate_tds
from v2.schemas.invoice import InvoiceCreateRequest

class InvalidStateTransitionError(ValueError):
    pass

class InvoiceCreationError(ValueError):
    pass


def get_financial_year() -> str:
    # Standard Indian Financial Year logic for demo
    from datetime import datetime
    now = datetime.now()
    year = now.year
    if now.month < 4:
        return f"{year-1}-{str(year)[-2:]}"
    return f"{year}-{str(year+1)[-2:]}"

def generate_invoice_number(session: Session, fy: str) -> str:
    # Handle SQLite locking mechanism vs native SELECT FOR UPDATE
    if session.bind.dialect.name == "sqlite":
        # Force write lock for sequence table in SQLite to avoid concurrent identical sequences
        session.execute(text("UPDATE invoice_sequences SET financial_year = financial_year WHERE financial_year = :fy"), {"fy": fy})
    
    seq = session.query(InvoiceSequence).filter_by(financial_year=fy).with_for_update().first()
    if not seq:
        seq = InvoiceSequence(financial_year=fy, next_value=1)
        session.add(seq)
        session.flush() # flush to get lock if needed

    current = seq.next_value
    seq.next_value += 1
    
    # Format: INV/2026-27/0001
    return f"INV/{fy}/{current:04d}"

def create_invoice(session: Session, project_id: str, request: InvoiceCreateRequest) -> Invoice:
    try:
        # 1. Fetch project, client, billing config
        project = session.query(Project).filter_by(id=project_id).first()
        if not project:
            raise ValueError("Project not found")
            
        client = session.query(Client).filter_by(id=project.client_id).first()
        billing_config = session.query(ProjectBillingConfig).filter_by(project_id=project_id).first()
    
        # 2. Determine Subtotal
        subtotal = Decimal('0.00')
        description = ""
        if request.billing_type == 'MILESTONE':
            milestone = session.query(ProjectMilestone).filter_by(id=request.milestone_id).with_for_update().first()
            if not milestone:
                raise ValueError("Milestone not found")
            if milestone.status != 'PENDING':
                raise ValueError("Milestone is not in PENDING state")
                
            subtotal = milestone.amount
            description = f"Billing for Milestone: {milestone.name}"
            
            # Mark milestone billed immediately in this tx
            milestone.status = "BILLED"
        else:
            # Percentage
            subtotal = calculate_percentage_billing(project.contract_value, request.billing_percentage)
            description = f"Billing {request.billing_percentage}% of Project {project.project_number}"
    
        # 3. Validate ceiling
        validate_billing_ceiling(session, project_id, subtotal)
    
        # 4. Tax logic
        gst_rate = billing_config.gst_percentage if billing_config else Decimal('18.00')
        tax_result = calculate_gst(
            seller_state="Tamil Nadu", # Assume fixed seller state for demo
            buyer_state=client.billing_address if client.billing_address else "Tamil Nadu", # Assume client address has state
            taxable_amount=subtotal,
            gst_rate=gst_rate
        )
    
        tds_amount = Decimal('0.00')
        if request.tds_applicable:
            tds_rate = Decimal('10.00') # configurable rule
            tds_amount = calculate_tds(subtotal, tds_rate)
    
        financials = calculate_invoice_financials(subtotal, tax_result.total_gst, tds_amount)
    
        # 5. Generate number
        fy = get_financial_year()
        invoice_number = generate_invoice_number(session, fy)
    
        # 6. Assemble Invoice
        hsn_sac = request.hsn_sac_override or (billing_config.hsn_sac_code if billing_config else "9983")
    
        invoice = Invoice(
            invoice_number=invoice_number,
            project_id=project_id,
            client_id=client.id,
            milestone_id=request.milestone_id,
            billing_type=request.billing_type,
            billing_percentage=request.billing_percentage,
            subtotal=financials["subtotal"],
            gross_amount=financials["gross_amount"],
            total_payable=financials["total_payable"],
            status="DRAFT", # Starts as draft always
            
            # Snapshots
            client_name=client.company_name,
            client_address=client.billing_address,
            client_gstin=client.gstin,
            project_name=project.project_name
        )
        session.add(invoice)
        session.flush() # flush to get invoice.id
    
        # Assemble Items
        item = InvoiceItem(
            invoice_id=invoice.id,
            description=description,
            hsn_sac=hsn_sac,
            amount=subtotal
        )
        session.add(item)
    
        # Assemble Taxes
        if tax_result.cgst > 0:
            session.add(InvoiceTax(invoice_id=invoice.id, tax_type="CGST", percentage=gst_rate/2, amount=tax_result.cgst))
        if tax_result.sgst > 0:
            session.add(InvoiceTax(invoice_id=invoice.id, tax_type="SGST", percentage=gst_rate/2, amount=tax_result.sgst))
        if tax_result.igst > 0:
            session.add(InvoiceTax(invoice_id=invoice.id, tax_type="IGST", percentage=gst_rate, amount=tax_result.igst))
    
        # Assemble TDS
        if tds_amount > 0:
            session.add(InvoiceTDS(invoice_id=invoice.id, tds_percentage=tds_rate, tds_amount=tds_amount))
    
        # Assemble AuditLog
        audit = AuditLog(
            entity_type="INVOICE",
            entity_id=invoice.id,
            action="CREATED",
            details=f"Invoice created with number {invoice_number} for {financials['total_payable']}"
        )
        session.add(audit)
        
        session.commit()
        session.refresh(invoice)
        return invoice
    except Exception:
        session.rollback()
        raise

def transition_invoice_status(session: Session, invoice_id: str, new_status: str):
    try:
        # Lock the invoice
        invoice = session.query(Invoice).filter_by(id=invoice_id).with_for_update().first()
        if not invoice:
            raise ValueError("Invoice not found")

        old_status = invoice.status
        
        # State map logic
        if old_status == "CANCELLED":
            raise InvalidStateTransitionError("Cannot transition from CANCELLED state")
        
        if old_status == "ISSUED" and new_status == "DRAFT":
            raise InvalidStateTransitionError("Cannot transition from ISSUED to DRAFT")
    
        if new_status == "CANCELLED":
            # Check for successful payments
            success_payment = session.query(Payment).filter(
                Payment.invoice_id == invoice.id,
                Payment.status == "SUCCESS"
            ).first()
            if success_payment:
                raise InvalidStateTransitionError("Cannot cancel an invoice that has successful payments.")
                
            # Revert milestone
            if invoice.milestone_id:
                milestone = session.query(ProjectMilestone).filter_by(id=invoice.milestone_id).first()
                if milestone:
                    milestone.status = "PENDING"
            
            # Log cancellation
            audit = AuditLog(
                entity_type="INVOICE",
                entity_id=invoice.id,
                action="CANCELLED",
                details=f"Invoice {invoice.invoice_number} cancelled."
            )
            session.add(audit)

        invoice.status = new_status
        session.commit()
        session.refresh(invoice)
        return invoice
    except Exception:
        session.rollback()
        raise
