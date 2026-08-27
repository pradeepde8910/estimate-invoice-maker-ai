import json
import re
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from typing import Optional

from app.models.invoice import InvoiceSequence, Invoice, InvoiceItem, InvoiceTax, InvoiceTDS
from app.models.project import Project, ProjectMilestone, ProjectBillingConfig
from app.models.master import Client, BillingClassification, TaxRate
from app.models.audit import AuditLog
from app.models.payment import Payment

from app.services.billing_service import validate_billing_ceiling, calculate_percentage_billing, calculate_invoice_financials
from app.services.tax_service import calculate_gst, calculate_tds
from app.services.billing_classification_service import match_billing_classifications
from app.schemas.invoice import InvoiceCreateRequest, InvoiceItemCreateRequest

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
    """
    Atomically claims the next sequence value for `fy` via a single INSERT ..
    ON CONFLICT DO UPDATE .. RETURNING statement — no separate SELECT-then-UPDATE
    step, so there's no window for two concurrent callers to both see the row
    missing (or both see the same next_value) and mint a duplicate number.
    This matters most for the very first invoice of a financial year, when the
    InvoiceSequence row doesn't exist yet and a plain SELECT FOR UPDATE has
    nothing to lock.
    """
    dialect = session.bind.dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as upsert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as upsert
    else:
        raise NotImplementedError(f"generate_invoice_number: unsupported dialect '{dialect}'")

    stmt = upsert(InvoiceSequence).values(financial_year=fy, next_value=2)
    stmt = stmt.on_conflict_do_update(
        index_elements=["financial_year"],
        set_={"next_value": InvoiceSequence.next_value + 1},
    ).returning(InvoiceSequence.next_value)

    next_value_after = session.execute(stmt).scalar_one()
    current = next_value_after - 1

    # Format: INV/2026-27/0001
    return f"INV/{fy}/{current:04d}"

# Used when the caller doesn't pass explicit payment_terms — the invoice
# still needs a real due_date (for aging/outstanding reports and the PDF's
# "Invoice Details" block, which previously showed nothing at all because
# invoice_date/due_date were never set anywhere in this module), even
# without a client-agreed term to base it on.
DEFAULT_DUE_DAYS = 15
_NET_TERMS_RE = re.compile(r"net\s*-?\s*(\d+)", re.IGNORECASE)


def _compute_invoice_dates(payment_terms: Optional[str]) -> tuple[datetime, datetime]:
    """
    Returns (invoice_date, due_date) for a newly created invoice.
    invoice_date is always "now" — due_date is parsed from payment_terms
    (e.g. "Net 30" -> +30 days) when possible, else DEFAULT_DUE_DAYS out.
    """
    invoice_date = datetime.utcnow()
    days = DEFAULT_DUE_DAYS
    if payment_terms:
        match = _NET_TERMS_RE.search(payment_terms)
        if match:
            days = int(match.group(1))
    return invoice_date, invoice_date + timedelta(days=days)


from app.models.project_component import ProjectCommercialComponent

# Below this keyword-match score, a description is not considered a confident
# enough auto-match to bill against — the caller must pick a classification
# explicitly instead. Prevents a vague/short description silently landing on
# whichever catalog row happens to score 1 by coincidence.
MIN_AUTO_MATCH_SCORE = 2


def _resolve_classification(
    session: Session,
    item_req: InvoiceItemCreateRequest,
    all_classifications: list[BillingClassification],
    source_entity_classification_id: Optional[str] = None
) -> BillingClassification:
    """
    Resolve the HSN/SAC code for one invoice line item — per item, not per
    invoice, since different line items on the same invoice can legitimately
    be different kinds of supply (e.g. a dev-services milestone vs. a GPU
    hardware component). Deliberately fails loudly instead of falling back to
    a generic default: a wrong-but-plausible code on a GST invoice is worse
    than an invoice that didn't get created.
    """
    # 1. Manual override from request
    if item_req.billing_classification_id:
        classification = session.query(BillingClassification).filter_by(
            id=item_req.billing_classification_id, active=True
        ).first()
        if not classification:
            raise ValueError(
                f"billing_classification_id '{item_req.billing_classification_id}' "
                f"for item '{item_req.description}' does not exist or is inactive."
            )
        return classification

    # 2. Inherit from source milestone/component
    if source_entity_classification_id:
        classification = session.query(BillingClassification).filter_by(
            id=source_entity_classification_id, active=True
        ).first()
        if classification:
            return classification

    # 3. Fallback to auto-match
    matches = match_billing_classifications(item_req.description, all_classifications, limit=1)
    if not matches or matches[0]["score"] < MIN_AUTO_MATCH_SCORE:
        raise ValueError(
            f"Could not confidently auto-match an HSN/SAC classification for "
            f"'{item_req.description}'. Pass billing_classification_id explicitly "
            f"for this item (see GET /api/master/billing-classifications/match)."
        )
    
    classification = session.query(BillingClassification).filter_by(
        id=matches[0]["id"]
    ).first()
    return classification


def _build_invoice_items(
    session: Session,
    request,
    all_classifications: list[BillingClassification],
) -> tuple[list[InvoiceItem], Decimal]:
    """
    Resolves each requested line item against its source (milestone, component,
    or a CUSTOM ad-hoc entry) and builds the InvoiceItem rows plus running
    subtotal. Shared between project invoices (which allow all three source
    types) and standalone invoices (which the caller/schema restricts to
    CUSTOM only, since there's no project to hold a milestone/component).
    """
    subtotal = Decimal('0.00')
    invoice_items_to_create: list[InvoiceItem] = []

    for item_req in request.items:
        source_classification_id = None
        milestone = None
        component = None
        if item_req.source_type == 'MILESTONE':
            milestone = session.query(ProjectMilestone).filter_by(id=item_req.source_id).with_for_update().first()
            if not milestone:
                raise ValueError(f"Milestone {item_req.source_id} not found")
            if milestone.status != 'PENDING':
                raise ValueError(f"Milestone {milestone.name} is not in PENDING state")
            source_classification_id = milestone.billing_classification_id
        elif item_req.source_type == 'COMPONENT':
            component = session.query(ProjectCommercialComponent).filter_by(id=item_req.source_id).with_for_update().first()
            if not component:
                raise ValueError(f"Component {item_req.source_id} not found")
            # Check status and billable amounts
            if component.status in ('FULLY_BILLED', 'CANCELLED'):
                raise ValueError(f"Component {component.name} cannot be billed in its current state: {component.status}")
            remaining_amount = component.amount - component.billed_amount
            if item_req.amount > remaining_amount:
                raise ValueError(f"Cannot bill ₹{item_req.amount} for {component.name}, only ₹{remaining_amount} remains.")
            source_classification_id = component.billing_classification_id
        elif item_req.source_type == 'CUSTOM':
            # Ad-hoc line item with no pre-existing milestone/component behind
            # it — for projects with no natural phase/component breakdown
            # (e.g. a flat-requirement SRS with a single lump-sum scope), and
            # for standalone invoices, which have no project at all.
            source_classification_id = None
        else:
            raise ValueError(f"Unknown source type: {item_req.source_type}")

        classification = _resolve_classification(session, item_req, all_classifications, source_classification_id)

        c_source = "UNCLASSIFIED"
        if item_req.billing_classification_id:
            c_source = "MANUAL"
        elif source_classification_id == classification.id:
            # Use whatever the source had, we can just say AUTO_MATCHED if we don't track source's exact method
            c_source = "AUTO_MATCHED"
        else:
            c_source = "AUTO_MATCHED"

        if c_source == "UNCLASSIFIED" or not classification:
            raise ValueError(f"Item '{item_req.description}' remains UNCLASSIFIED. You must assign a classification before generating the invoice.")

        if item_req.source_type == 'MILESTONE':
            # Check for duplicate task_key
            if item_req.task_key:
                existing = session.query(InvoiceItem).filter(
                    InvoiceItem.milestone_id == milestone.id,
                    InvoiceItem.task_key == item_req.task_key
                ).join(InvoiceItem.invoice).filter(
                    Invoice.status.in_(["ISSUED", "DRAFT"])
                ).first()
                if existing:
                    raise ValueError(f"Task '{item_req.task_key}' has already been invoiced for milestone {milestone.name}.")

            # We defer updating the milestone status until we process all items
            # We'll just append it for now
            invoice_items_to_create.append(InvoiceItem(
                milestone_id=milestone.id,
                task_key=item_req.task_key,
                requirement_name=item_req.requirement_name,
                description=item_req.description,
                hours=item_req.hours,
                amount=item_req.amount,
                billing_classification_id=classification.id,
                hsn_sac_code=classification.hsn_sac_code,
                gst_rate=classification.gst_rate,
                classification_source=item_req.classification_source or c_source
            ))
        elif item_req.source_type == 'COMPONENT':
            component.billed_amount += item_req.amount
            if component.billed_amount >= component.amount:
                component.status = 'FULLY_BILLED'
            else:
                component.status = 'PARTIALLY_BILLED'
            invoice_items_to_create.append(InvoiceItem(
                component_id=component.id,
                description=item_req.description,
                hours=item_req.hours,
                amount=item_req.amount,
                billing_classification_id=classification.id,
                hsn_sac_code=classification.hsn_sac_code,
                gst_rate=classification.gst_rate,
                classification_source=item_req.classification_source or c_source
            ))
        elif item_req.source_type == 'CUSTOM':
            invoice_items_to_create.append(InvoiceItem(
                description=item_req.description,
                hours=item_req.hours,
                amount=item_req.amount,
                billing_classification_id=classification.id,
                hsn_sac_code=classification.hsn_sac_code,
                gst_rate=classification.gst_rate,
                classification_source=item_req.classification_source or c_source
            ))
        else:
            raise ValueError(f"Unknown source type: {item_req.source_type}")

        subtotal += item_req.amount

    return invoice_items_to_create, subtotal


def _finalize_and_save_invoice(
    session: Session,
    invoice: Invoice,
    invoice_items_to_create: list[InvoiceItem],
    subtotal: Decimal,
    request,
    client,
) -> Invoice:
    """
    Shared tail end of invoice creation: discount/tax/TDS calculation, persisting
    the invoice + items + tax buckets, and the audit log entry. Milestone status
    bookkeeping (project-only) is handled by the caller before this returns.
    """
    # Discount — reduces the taxable base, not the billed-against-contract
    # subtotal (validate_billing_ceiling and component.billed_amount above
    # must keep tracking the full undiscounted amount).
    discount_amount = request.discount_amount or Decimal('0.00')
    if discount_amount < 0:
        raise ValueError("discount_amount cannot be negative")
    if discount_amount > subtotal:
        raise ValueError(f"discount_amount ({discount_amount}) cannot exceed subtotal ({subtotal})")
    discount_factor = ((subtotal - discount_amount) / subtotal) if subtotal > 0 else Decimal('1.00')

    # Tax logic (Phase 5 Bucketing) — each item's taxable amount is scaled
    # down by the discount factor so GST is charged on the discounted value
    # while preserving the relative mix of GST rates across items.
    from app.services.tax_service import calculate_taxes_by_bucket
    items_for_tax = [
        {"amount": (i.amount * discount_factor).quantize(Decimal('0.01')), "gst_rate": i.gst_rate}
        for i in invoice_items_to_create
    ]

    tax_buckets = calculate_taxes_by_bucket(
        seller_state="Tamil Nadu",
        buyer_state=client.billing_address if client.billing_address else "Tamil Nadu",
        items=items_for_tax
    )

    total_gst = Decimal('0.00')
    for bucket in tax_buckets:
        total_gst += bucket.total_gst

    tds_amount = Decimal('0.00')
    tds_rate = Decimal('10.00')
    if request.tds_applicable:
        tds_amount = calculate_tds(subtotal - discount_amount, tds_rate)

    financials = calculate_invoice_financials(subtotal, total_gst, tds_amount, discount_amount)

    invoice.subtotal = financials["subtotal"]
    invoice.discount_amount = financials["discount_amount"]
    invoice.gross_amount = financials["gross_amount"]
    invoice.total_payable = financials["total_payable"]

    session.add(invoice)
    session.flush()  # flush to get invoice.id

    # Attach and save items (classification snapshot was already resolved per item above)
    for item in invoice_items_to_create:
        item.invoice_id = invoice.id
        session.add(item)

    # Save Tax Buckets
    for bucket in tax_buckets:
        if bucket.cgst > 0:
            session.add(InvoiceTax(invoice_id=invoice.id, tax_type="CGST", percentage=bucket.gst_rate/2, amount=bucket.cgst))
        if bucket.sgst > 0:
            session.add(InvoiceTax(invoice_id=invoice.id, tax_type="SGST", percentage=bucket.gst_rate/2, amount=bucket.sgst))
        if bucket.igst > 0:
            session.add(InvoiceTax(invoice_id=invoice.id, tax_type="IGST", percentage=bucket.gst_rate, amount=bucket.igst))

    if tds_amount > 0:
        session.add(InvoiceTDS(invoice_id=invoice.id, tds_percentage=tds_rate, tds_amount=tds_amount))

    audit = AuditLog(
        action="INVOICE_CREATED",
        details=json.dumps({
            "entity_type": "INVOICE",
            "entity_id": invoice.id,
            "message": f"Invoice created with number {invoice.invoice_number} for {financials['total_payable']}",
        }),
    )
    session.add(audit)

    return invoice


def create_standalone_invoice(session: Session, request) -> Invoice:
    """Creates an invoice with no project behind it — billed directly against
    a client with ad-hoc (CUSTOM) line items. See create_invoice for the
    project-backed equivalent; the two share _build_invoice_items and
    _finalize_and_save_invoice for the classification/tax/persistence logic."""
    try:
        client = session.query(Client).filter_by(id=request.client_id).first()
        if not client:
            raise ValueError("Client not found")

        all_classifications = session.query(BillingClassification).filter_by(active=True).all()

        invoice_items_to_create, subtotal = _build_invoice_items(session, request, all_classifications)

        fy = get_financial_year()
        invoice_number = generate_invoice_number(session, fy)
        invoice_date, due_date = _compute_invoice_dates(request.payment_terms)

        invoice = Invoice(
            invoice_number=invoice_number,
            invoice_type="STANDALONE",
            project_id=None,
            client_id=client.id,
            status="DRAFT",
            invoice_date=invoice_date,
            due_date=due_date,
            client_name=client.company_name,
            client_address=client.billing_address,
            client_gstin=client.gstin,
            client_email=client.email,
            client_phone=client.phone,
            po_number=request.po_number,
            payment_terms=request.payment_terms,
        )

        _finalize_and_save_invoice(session, invoice, invoice_items_to_create, subtotal, request, client)

        session.commit()
        session.refresh(invoice)
        return invoice
    except Exception as e:
        session.rollback()
        raise e


def create_invoice(session: Session, project_id: str, request: InvoiceCreateRequest) -> Invoice:
    try:
        from app.utils.organization import load_profile
        org_profile = load_profile()

        # 1. Fetch project, client, billing config
        project = session.query(Project).filter_by(id=project_id).first()
        if not project:
            raise ValueError("Project not found")

        client = session.query(Client).filter_by(id=project.client_id).first()
        billing_config = session.query(ProjectBillingConfig).filter_by(project_id=project_id).first()

        all_classifications = session.query(BillingClassification).filter_by(active=True).all()

        # 2. Process Line Items and Determine Subtotal
        invoice_items_to_create, subtotal = _build_invoice_items(session, request, all_classifications)

        # 3. Validate ceiling
        validate_billing_ceiling(session, project_id, subtotal)

        # 4. Generate number
        fy = get_financial_year()
        invoice_number = generate_invoice_number(session, fy)
        invoice_date, due_date = _compute_invoice_dates(request.payment_terms)

        # 5. Assemble Invoice
        invoice = Invoice(
            invoice_number=invoice_number,
            invoice_type="PROJECT",
            project_id=project_id,
            client_id=client.id,
            status="DRAFT",
            invoice_date=invoice_date,
            due_date=due_date,
            client_name=client.company_name,
            client_address=client.billing_address,
            client_gstin=client.gstin,
            client_email=client.email,
            client_phone=client.phone,
            project_name=project.project_name,
            project_number=project.project_number,
            project_start_date=project.start_date,
            project_end_date=project.end_date,
            bank_name=org_profile.get("bank_name"),
            bank_account_number=org_profile.get("bank_account_number"),
            bank_ifsc=org_profile.get("bank_ifsc"),
            invoice_terms=org_profile.get("invoice_terms"),
            po_number=request.po_number,
            payment_terms=request.payment_terms,
        )

        _finalize_and_save_invoice(session, invoice, invoice_items_to_create, subtotal, request, client)

        # Update milestone statuses for task-level billing
        milestone_ids = {i.milestone_id for i in invoice_items_to_create if i.milestone_id}
        if milestone_ids:
            from app.models.estimation import Estimation
            est = session.query(Estimation).filter(Estimation.id == project.estimation_id).first()
            if est and est.raw_pipeline_json:
                cost_data = est.raw_pipeline_json.get("cost_estimation", est.raw_pipeline_json)
                unit_estimates = cost_data.get("unit_estimates", [])
                
                for mid in milestone_ids:
                    m = session.query(ProjectMilestone).filter_by(id=mid).first()
                    if m:
                        unit = next((u for u in unit_estimates if u.get("unit_id") == m.source_unit_id), None)
                        if unit:
                            total_tasks = sum(len(r.get("implementation_tasks", [])) for r in unit.get("requirement_estimates", []))
                            billed_tasks = session.query(InvoiceItem).filter(
                                InvoiceItem.milestone_id == m.id,
                                InvoiceItem.task_key.isnot(None)
                            ).join(InvoiceItem.invoice).filter(
                                Invoice.status.in_(["ISSUED", "DRAFT"])
                            ).count()
                            
                            if total_tasks > 0 and billed_tasks >= total_tasks:
                                m.status = "BILLED"
                            else:
                                m.status = "PARTIALLY_BILLED"
            
                
        session.commit()
        session.refresh(invoice)
        return invoice
    except Exception as e:
        session.rollback()
        raise e

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
                action="INVOICE_CANCELLED",
                details=json.dumps({
                    "entity_type": "INVOICE",
                    "entity_id": invoice.id,
                    "message": f"Invoice {invoice.invoice_number} cancelled.",
                }),
            )
            session.add(audit)

        invoice.status = new_status
        session.commit()
        session.refresh(invoice)
        return invoice
    except Exception:
        session.rollback()
        raise
