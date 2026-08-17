import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Numeric, Text
from v2.models.base import Base

class Client(Base):
    __tablename__ = "clients"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_name = Column(String(255), unique=True, nullable=False, index=True)
    contact_person = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    gstin = Column(String(50), nullable=True)
    billing_address = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class HSNSACMaster(Base):
    __tablename__ = "hsn_sac_master"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=False)
    service_type = Column(String(100), nullable=False)
    gst_rate = Column(Numeric(5, 2), nullable=False)  # Example: 18.00
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

class User(Base):
    __tablename__ = "users"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="Admin")  # Admin, PM, Finance, Developer
    created_at = Column(DateTime, default=datetime.utcnow)
