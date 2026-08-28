import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime
from app.models.base import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    # user_id is a loose string identifier (supports user UUIDs, "bootstrap-admin", "system", etc.)
    user_id = Column(String(255), nullable=True)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

