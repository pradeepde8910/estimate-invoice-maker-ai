import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Numeric, ForeignKey, Text, Index, text, CheckConstraint, event, Integer
from sqlalchemy.orm import relationship
from v2.models.base import Base

class InvoiceSequence(Base):
    __tablename__ = 'invoice_sequences'
    financial_year = Column(String(20), primary_key=True)
    next_value = Column(Integer, nullable=False, default=1)

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_number = Column(String(100), unique=True, nullable=True, index=True) # Nullable until issued
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False)
    client_id = Column(String(36), ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False)
    milestone_id = Column(String(36), ForeignKey("project_milestones.id", ondelete="RESTRICT"), nullable=True)
    
    # Snapshot Columns for Immutability
    client_name = Column(String(255), nullable=True)
    client_address = Column(Text, nullable=True)
    client_gstin = Column(String(50), nullable=True)
    project_name = Column(String(255), nullable=True)

    billing_type = Column(String(50), nullable=False) # MILESTONE, PERCENTAGE
    billing_percentage = Column(Numeric(5, 2), nullable=True)

    subtotal = Column(Numeric(12, 2), nullable=False, default=0.00)
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
        Index('uix_milestone_invoice', 'milestone_id', unique=True, 
              postgresql_where=text("status != 'CANCELLED'"),
              sqlite_where=text("status != 'CANCELLED'"))
    )

    project = relationship("Project", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    taxes = relationship("InvoiceTax", back_populates="invoice", cascade="all, delete-orphan")
    tds = relationship("InvoiceTDS", back_populates="invoice", uselist=False, cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")

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
    description = Column(String(255), nullable=False)
    hsn_sac = Column(String(50), nullable=True)
    amount = Column(Numeric(12, 2), nullable=False, default=0.00)

    invoice = relationship("Invoice", back_populates="items")


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
