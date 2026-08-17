import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text
from v2.models.base import Base

class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type = Column(String(100), nullable=False) # e.g., 'Invoice', 'Payment', 'Project'
    entity_id = Column(String(36), nullable=False)
    
    action = Column(String(100), nullable=False) # e.g., 'CREATED', 'STATUS_CHANGED', 'PAYMENT_RECORDED'
    details = Column(Text, nullable=True) # JSON payload or description
    
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(String(36), nullable=True) # Who performed the action
