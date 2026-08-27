import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Numeric, Text
from sqlalchemy.orm import relationship
from app.models.base import Base

class Client(Base):
    __tablename__ = "clients"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_name = Column(String(255), unique=False, nullable=True, index=True)
    contact_person = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    gstin = Column(String(50), nullable=True)
    billing_address = Column(Text, nullable=True)
    status = Column(String(50), default="DRAFT", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    estimations = relationship("Estimation", back_populates="client")

class BillingClassification(Base):
    """
    Catalog of approved billing classifications ("what we actually sell"),
    each mapped to an HSN/SAC code. Deliberately NOT unique on hsn_sac_code:
    many distinct classifications (e.g. "Backend development", "UI design")
    legitimately share one SAC code (998314), so the code can't be the
    identity of a row — the classification (category + description) is.
    """
    __tablename__ = "billing_classifications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    category = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=False)
    item_type = Column(String(20), nullable=False, default="SERVICE")  # SERVICE | HARDWARE
    hsn_sac_code = Column(String(50), nullable=False, index=True)
    hsn_sac_type = Column(String(10), nullable=False)  # SAC | HSN
    gst_rate = Column(Numeric(5, 2), nullable=False)  # Example: 18.00
    keywords = Column(Text, nullable=True)  # comma-separated, used for keyword matching
    active = Column(Boolean, default=True)
    effective_from = Column(DateTime, default=datetime.utcnow)
    effective_to = Column(DateTime, nullable=True)

class TaxRate(Base):
    __tablename__ = "tax_rates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tax_type = Column(String(50), nullable=False, unique=True)  # CGST, SGST, IGST, TDS
    percentage = Column(Numeric(5, 2), nullable=False)
    active = Column(Boolean, default=True)

class BillingType(Base):
    __tablename__ = "billing_types"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(50), unique=True, nullable=False)  # MILESTONE, PERCENTAGE
    description = Column(String(255), nullable=True)
    active = Column(Boolean, default=True)
