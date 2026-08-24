from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.project import Project, ProjectMilestone
from app.models.project_component import ProjectCommercialComponent
from app.models.invoice import Invoice, InvoiceTDS
from app.models.payment import Payment
from app.schemas.project_summary import ProjectFinancialSummary
from typing import List

class FinancialIntegrityError(ValueError):
    pass

def get_project_summary(db: Session, project_id: str) -> ProjectFinancialSummary:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise ValueError("Project not found")

    # SQL aggregates for invoices
    # Coalesce to 0 to handle cases with no invoices
    invoice_aggregates = db.query(
        func.coalesce(func.sum(Invoice.subtotal), Decimal('0.00')).label('total_subtotal'),
        func.coalesce(func.sum(Invoice.gross_amount), Decimal('0.00')).label('total_invoiced'),
        func.coalesce(func.sum(InvoiceTDS.tds_amount), Decimal('0.00')).label('total_tds'),
        func.coalesce(func.sum(Invoice.total_payable), Decimal('0.00')).label('total_payable')
    ).outerjoin(
        InvoiceTDS, Invoice.id == InvoiceTDS.invoice_id
    ).filter(
        Invoice.project_id == project_id,
        Invoice.status == 'ISSUED'
    ).first()

    # If the DB driver doesn't return Decimal for coalesce on empty, cast to Decimal
    total_subtotal = Decimal(str(invoice_aggregates.total_subtotal))
    total_invoiced = Decimal(str(invoice_aggregates.total_invoiced))
    total_tds = Decimal(str(invoice_aggregates.total_tds))
    total_payable = Decimal(str(invoice_aggregates.total_payable))

    # SQL aggregate for payments
    # Join Payment to Invoice to ensure we only sum SUCCESS payments for ISSUED invoices
    collected_aggregate = db.query(
        func.coalesce(func.sum(Payment.amount), Decimal('0.00'))
    ).join(
        Invoice, Payment.invoice_id == Invoice.id
    ).filter(
        Invoice.project_id == project_id,
        Invoice.status == 'ISSUED',
        Payment.status == 'SUCCESS'
    ).scalar()

    total_collected = Decimal(str(collected_aggregate))

    # Calculate derived values
    contract_value = project.contract_value or Decimal('0.00')
    outstanding = total_payable - total_collected
    remaining_contract = contract_value - total_subtotal

    # Fetch commercial components
    components = db.query(ProjectCommercialComponent).filter(ProjectCommercialComponent.project_id == project_id).all()
    
    reserved_contingency = Decimal('0.00')
    for comp in components:
        if comp.component_type == 'contingency':
            reserved_contingency += comp.amount

    # Integrity Checks
    if outstanding < 0:
        raise FinancialIntegrityError(f"Negative outstanding detected ({-outstanding}). This indicates an overpayment bypassing the transaction guard.")
        
    if remaining_contract < 0:
        raise FinancialIntegrityError(f"Negative remaining contract detected ({-remaining_contract}). This indicates invoices exceeded the contract ceiling.")

    from app.schemas.project_summary import Financials, MilestoneSimple, CommercialComponentSimple

    financials = Financials(
        contract_value=contract_value,
        total_billed=total_invoiced,
        total_paid=total_collected,
        remaining_contract=remaining_contract,
        reserved_contingency=reserved_contingency,
        outstanding=outstanding,
        total_subtotal=total_subtotal,
        total_invoiced=total_invoiced,
        total_tds=total_tds,
        total_payable=total_payable,
        total_collected=total_collected
    )
    
    milestones = db.query(ProjectMilestone).filter(ProjectMilestone.project_id == project_id).order_by(ProjectMilestone.due_date).all()
    milestone_responses = [
        MilestoneSimple(
            id=m.id,
            name=m.name,
            amount=m.amount,
            target_date=m.due_date,
            status=m.status
        ) for m in milestones
    ]
    
    component_responses = [
        CommercialComponentSimple(
            id=c.id,
            name=c.name,
            amount=c.amount,
            billed_amount=c.billed_amount,
            component_type=c.component_type,
            billing_policy=c.billing_policy,
            status=c.status
        ) for c in components
    ]

    return ProjectFinancialSummary(
        project_id=project.id,
        project_name=project.project_name,
        project_number=project.project_number,
        billing_type=project.billing_type,
        delivery_unit_label=project.billing_config.delivery_unit_label if project.billing_config else "Milestone",
        financials=financials,
        milestones=milestone_responses,
        components=component_responses
    )

def get_project_invoices(db: Session, project_id: str) -> List[Invoice]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise ValueError("Project not found")
    return db.query(Invoice).filter(Invoice.project_id == project_id).order_by(Invoice.created_at.desc()).all()

def get_project_payments(db: Session, project_id: str) -> List[Payment]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise ValueError("Project not found")
    # Fetch payments for all invoices in the project
    return db.query(Payment).join(Invoice).filter(Invoice.project_id == project_id).order_by(Payment.created_at.desc()).all()

def get_project_milestones(db: Session, project_id: str) -> List[ProjectMilestone]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise ValueError("Project not found")
    return db.query(ProjectMilestone).filter(ProjectMilestone.project_id == project_id).order_by(ProjectMilestone.due_date).all()
