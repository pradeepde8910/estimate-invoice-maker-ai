import uuid
from sqlalchemy import Column, String, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base

class ProjectCommercialComponent(Base):
    __tablename__ = "project_commercial_components"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False, default=0.00)
    
    # infrastructure, licenses, contingency
    component_type = Column(String(50), nullable=False)
    
    # recurring, upfront, conditional
    billing_policy = Column(String(50), nullable=False)
    
    # AVAILABLE, RESERVED, PARTIALLY_BILLED, FULLY_BILLED, CANCELLED
    status = Column(String(50), nullable=False, default="AVAILABLE")
    
    billed_amount = Column(Numeric(12, 2), nullable=False, default=0.00)
    
    billing_classification_id = Column(String(36), ForeignKey("billing_classifications.id", ondelete="RESTRICT"), nullable=True)
    classification_source = Column(String(50), nullable=True) # AUTO_MATCHED, MANUAL, UNCLASSIFIED

    project = relationship("Project", back_populates="commercial_components")
