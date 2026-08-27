import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Boolean, Integer, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base


class Estimation(Base):
    __tablename__ = "estimations"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    estimation_number = Column(String(100), unique=True, nullable=False, index=True)
    client_id = Column(String(255), ForeignKey("clients.id"), nullable=False)
    project_name = Column(String(255), nullable=False)
    status = Column(String(50), default="Draft")  # Draft, Processing, Completed, Failed, Approved, Sent, Archived
    timeline_weeks = Column(Float, default=0.0)
    grand_total = Column(Float, default=0.0)
    currency = Column(String(10), default="INR")
    converted_project_id = Column(String(36), nullable=True)
    raw_pipeline_json = Column(JSON, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = relationship("Client", back_populates="estimations")
    documents = relationship("Document", back_populates="estimation", cascade="all, delete-orphan")
    # Invoice.estimation_id is a plain "Legacy V1 Compatibility" FK — Invoice
    # itself already declares estimation = relationship(..., back_populates=
    # "invoices"), so this side must exist too or SQLAlchemy's mapper
    # configuration fails at first use with "no property 'invoices'".
    invoices = relationship("Invoice", back_populates="estimation")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_number = Column(String(100), unique=True, nullable=False, index=True)
    estimation_id = Column(String(255), ForeignKey("estimations.id"), nullable=False)
    type = Column(String(50), nullable=False)  # quotation, brd, srs
    content = Column(Text, nullable=False)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    estimation = relationship("Estimation", back_populates="documents")


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type = Column(String(50), nullable=False)  # e.g., organization, estimation, document
    entity_id = Column(String(255), nullable=False)
    file_name = Column(String(255), nullable=False)
    path = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
