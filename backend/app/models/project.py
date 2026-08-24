import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Numeric, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.models.base import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id = Column(String(36), ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False)
    project_number = Column(String(100), unique=True, nullable=False, index=True)
    project_name = Column(String(255), nullable=False)
    status = Column(String(50), default="Active")
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    contract_value = Column(Numeric(12, 2), nullable=False, default=0.00)
    estimation_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    client = relationship("Client")
    billing_config = relationship("ProjectBillingConfig", back_populates="project", uselist=False, cascade="all, delete-orphan")
    milestones = relationship("ProjectMilestone", back_populates="project", cascade="all, delete-orphan")
    commercial_components = relationship("ProjectCommercialComponent", back_populates="project", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="project", cascade="all, delete-orphan")

    @property
    def billing_type(self) -> str | None:
        """The project-level billing arrangement (e.g. Milestone, Percentage)
        from ProjectBillingConfig.billing_type — same source Invoice.billing_model
        reads from, so the projects list and each project's invoice list agree."""
        if self.billing_config and self.billing_config.billing_type:
            return self.billing_config.billing_type.code
        return None

    @property
    def client_name(self) -> str | None:
        return self.client.company_name if self.client else None


class ProjectBillingConfig(Base):
    __tablename__ = "project_billing_config"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True)
    billing_type_id = Column(String(36), ForeignKey("billing_types.id", ondelete="RESTRICT"), nullable=False)
    gst_percentage = Column(Numeric(5, 2), nullable=False, default=18.00)
    tds_applicable = Column(String(50), default="NO") # YES / NO
    hsn_sac_code = Column(String(50), nullable=True)
    delivery_unit_label = Column(String(50), default="Milestone")

    project = relationship("Project", back_populates="billing_config")
    billing_type = relationship("BillingType")


class ProjectMilestone(Base):
    __tablename__ = "project_milestones"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    amount = Column(Numeric(12, 2), nullable=False, default=0.00)
    due_date = Column(DateTime, nullable=True)
    status = Column(String(50), default="PENDING") # PENDING, IN_PROGRESS, COMPLETED, BILLED
    source_unit_id = Column(String(100), nullable=True)
    billing_classification_id = Column(String(36), ForeignKey("billing_classifications.id", ondelete="RESTRICT"), nullable=True)
    classification_source = Column(String(50), nullable=True) # AUTO_MATCHED, MANUAL, UNCLASSIFIED

    project = relationship("Project", back_populates="milestones")
    # Link to invoice handled on the invoice side
