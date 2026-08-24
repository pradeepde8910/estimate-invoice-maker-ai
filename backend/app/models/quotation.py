import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, Numeric, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from app.models.base import Base

class Quotation(Base):
    """
    A snapshot of a project quotation. Decoupled from the master catalog
    so Admin edits to a specific quotation don't accidentally override
    global standardized pricing, as requested in the architectural blueprint.
    """
    __tablename__ = "quotations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_name = Column(String(255), nullable=False)
    
    # Workflow status: DRAFT -> PRICING_REVIEW -> ADMIN_APPROVED -> FINALIZED -> ISSUED
    status = Column(String(50), nullable=False, default="DRAFT") 
    
    development_cost = Column(Numeric(12, 2), default=0)
    contingency_amount = Column(Numeric(12, 2), default=0)
    verified_infrastructure_cost = Column(Numeric(12, 2), default=0)
    licenses_cost = Column(Numeric(12, 2), default=0)
    grand_total = Column(Numeric(12, 2), default=0)
    
    quotation_markdown = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    line_items = relationship("QuotationLineItem", back_populates="quotation", cascade="all, delete-orphan")


class QuotationLineItem(Base):
    """
    Individual pricing line items for a Quotation. Retains audit trail of 
    what the AI originally discovered vs what the Admin finalized.
    """
    __tablename__ = "quotation_line_items"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    quotation_id = Column(String(36), ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False)
    
    resource_name = Column(String(255), nullable=False)
    provider_name = Column(String(255), nullable=True)
    model_name = Column(String(255), nullable=True)
    
    quantity = Column(Integer, default=1)
    unit = Column(String(50), nullable=True) # e.g. "month", "project"
    currency = Column(String(10), default="INR")
    
    # Audit tracking: AI price vs Admin price
    original_ai_price = Column(Numeric(12, 2), nullable=True)
    applied_price = Column(Numeric(12, 2), nullable=True)
    
    # Pricing Status: VERIFIED, PENDING_REVIEW, EDITED
    status = Column(String(50), nullable=False, default="PENDING_REVIEW")
    
    source_url = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    
    quotation = relationship("Quotation", back_populates="line_items")
