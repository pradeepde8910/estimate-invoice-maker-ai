import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Integer, UniqueConstraint
from app.models.base import Base

class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type = Column(String(50), nullable=False) # e.g. 'MILESTONE', 'INVOICE'
    entity_id = Column(String(36), nullable=False)
    alert_rule = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    
    status = Column(String(50), nullable=False, default="TRIGGERED") # TRIGGERED, SENT, FAILED
    attempt_count = Column(Integer, nullable=False, default=0)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_attempt_at = Column(DateTime, nullable=True)
    next_retry_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    failure_reason = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "alert_rule", name="uix_alert_entity_rule"),
    )
