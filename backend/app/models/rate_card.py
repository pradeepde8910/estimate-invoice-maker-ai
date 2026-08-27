import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Boolean
from app.models.base import Base


class RateCard(Base):
    __tablename__ = "rate_cards"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    role_key = Column(String(100), nullable=False, index=True)
    role_label = Column(String(100), nullable=False)
    rate_per_hour = Column(Float, nullable=False)
    effective_from = Column(DateTime, default=datetime.utcnow)
    effective_to = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
