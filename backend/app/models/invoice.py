import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Numeric, ForeignKey, Text, Index, text, CheckConstraint, event, Integer
from sqlalchemy.orm import relationship
from app.models.base import Base

class InvoiceSequence(Base):
    __tablename__ = 'invoice_sequences'
    financial_year = Column(String(20), primary_key=True)
    next_value = Column(Integer, nullable=False, default=1)

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_number = Column(String(100), unique=True, nullable=True, index=True) # Nullable until issued
    invoice_type = Column(String(20), nullable=False, default="PROJECT") # PROJECT, STANDALONE
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="RESTRICT"), nullable=True)
    client_id = Column(String(36), ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False)
    
    # Client Snapshot
    client_name = Column(String(255), nullable=True)
    client_address = Column(Text, nullable=True)
    client_gstin = Column(String(50), nullable=True)
    client_email = Column(String(100), nullable=True)
    client_phone = Column(String(50), nullable=True)
    
    # Project Snapshot
    project_name = Column(String(255), nullable=True)
    project_number = Column(String(100), nullable=True)
    project_start_date = Column(DateTime, nullable=True)
    project_end_date = Column(DateTime, nullable=True)

    # Organization Payment Snapshot
    bank_name = Column(String(255), nullable=True)
    bank_account_number = Column(String(100), nullable=True)
    bank_ifsc = Column(String(50), nullable=True)
    invoice_terms = Column(Text, nullable=True)

    po_number = Column(String(100), nullable=True)
    payment_terms = Column(String(100), nullable=True)

    subtotal = Column(Numeric(12, 2), nullable=False, default=0.00)
    discount_amount = Column(Numeric(12, 2), nullable=False, default=0.00)
    gross_amount = Column(Numeric(12, 2), nullable=False, default=0.00)
    total_payable = Column(Numeric(12, 2), nullable=False, default=0.00)

    invoice_date = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)

    status = Column(String(50), nullable=False, default="DRAFT") # DRAFT, ISSUED, CANCELLED
    payment_status = Column(String(50), nullable=False, default="UNPAID") # UNPAID, INITIATED, PARTIALLY_PAID, PAID

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(status.in_(['DRAFT', 'ISSUED', 'CANCELLED']), name='chk_invoice_status'),
        CheckConstraint(payment_status.in_(['UNPAID', 'INITIATED', 'PARTIALLY_PAID', 'PAID']), name='chk_payment_status'),
        CheckConstraint(invoice_type.in_(['PROJECT', 'STANDALONE']), name='chk_invoice_type'),
    )

    project = relationship("Project", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    taxes = relationship("InvoiceTax", back_populates="invoice", cascade="all, delete-orphan")
    tds = relationship("InvoiceTDS", back_populates="invoice", uselist=False, cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")

    @property
    def billing_sources(self) -> list[str]:
        """
        Distinct billing sources represented on this invoice's line items —
        derived from each InvoiceItem's milestone_id/component_id rather than
        a denormalized column, since a single invoice can legitimately mix a
        milestone payment with a commercial component (e.g. infrastructure)
        in one go. Used by the invoice list UI so each row shows what it's
        actually billing for (Milestone, Infrastructure, Licenses, Custom, ...)
        instead of a generic "Invoice".
        """
        labels: set[str] = set()
        for item in self.items:
            if item.milestone_id:
                labels.add("Milestone")
            elif item.component_id:
                component = item.component
                labels.add(component.component_type.replace("_", " ").title() if component and component.component_type else "Component")
            else:
                # No milestone/component behind it — an ad-hoc CUSTOM line item
                # (see InvoiceItemCreateRequest), used for flat-scope projects
                # with no natural milestone/component breakdown.
                labels.add("Custom")
        return sorted(labels)

    @property
    def billing_model(self) -> str | None:
        """The project-level billing arrangement (e.g. Milestone, Percentage)
        this invoice was raised under — from Project.billing_type, not to be
        confused with billing_sources (the per-line-item mix). None for a
        STANDALONE invoice, which has no project to inherit an arrangement from."""
        return self.project.billing_type if self.project else None

    @property
    def amount_paid(self):
        """Sum of SUCCESS payments — the invoice never stores this directly;
        it's always derived from the payment ledger (see payment_service.py's
        _derive_payment_status, which this mirrors for read paths that only
        need the amount, not the derived UNPAID/PARTIALLY_PAID/PAID label)."""
        from decimal import Decimal
        return sum((p.amount for p in self.payments if p.status == "SUCCESS"), Decimal("0.00"))

    @property
    def balance_due(self):
        return self.total_payable - self.amount_paid

@event.listens_for(Invoice.invoice_number, 'set', active_history=True)
def receive_set(target, value, oldvalue, initiator):
    # App-layer guard: immutable once set
    # active_history=True ensures oldvalue is loaded from the DB if expired
    from sqlalchemy.orm.base import NO_VALUE, NEVER_SET
    if oldvalue not in (None, NO_VALUE, NEVER_SET) and value != oldvalue:
        raise ValueError("invoice_number is immutable and cannot be changed once set.")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_id = Column(String(36), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    
    milestone_id = Column(String(36), ForeignKey("project_milestones.id", ondelete="RESTRICT"), nullable=True)
    component_id = Column(String(36), ForeignKey("project_commercial_components.id", ondelete="RESTRICT"), nullable=True)
    
    task_key = Column(String(100), nullable=True)
    requirement_name = Column(String(255), nullable=True)

    description = Column(String(255), nullable=False)
    hours = Column(Numeric(10, 2), nullable=True)
    amount = Column(Numeric(12, 2), nullable=False, default=0.00)
    
    # Classification Snapshot
    billing_classification_id = Column(String(36), ForeignKey("billing_classifications.id", ondelete="RESTRICT"), nullable=True)
    hsn_sac_code = Column(String(50), nullable=True)
    gst_rate = Column(Numeric(5, 2), nullable=True)
    classification_source = Column(String(50), nullable=True) # AUTO_MATCHED, MANUAL, UNCLASSIFIED

    invoice = relationship("Invoice", back_populates="items")
    milestone = relationship("ProjectMilestone")
    component = relationship("ProjectCommercialComponent")

    @property
    def milestone_name(self):
        return self.milestone.name if self.milestone else None

    @property
    def hsn_sac(self):
        return self.hsn_sac_code


class InvoiceTax(Base):
    __tablename__ = "invoice_tax"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_id = Column(String(36), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    tax_type = Column(String(50), nullable=False) # CGST, SGST, IGST
    percentage = Column(Numeric(5, 2), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False, default=0.00)

    invoice = relationship("Invoice", back_populates="taxes")


class InvoiceTDS(Base):
    __tablename__ = "invoice_tds"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_id = Column(String(36), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, unique=True)
    tds_percentage = Column(Numeric(5, 2), nullable=False)
    tds_amount = Column(Numeric(12, 2), nullable=False, default=0.00)

    invoice = relationship("Invoice", back_populates="tds")
