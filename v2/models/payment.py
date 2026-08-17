import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Numeric, ForeignKey, Text
import sqlalchemy
from sqlalchemy.orm import relationship
from v2.models.base import Base

class Payment(Base):
    __tablename__ = "payments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_id = Column(String(36), ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False)
    
    payment_reference = Column(String(100), nullable=True) # E.g., TXN-12345
    payment_date = Column(DateTime, nullable=True)
    initiated_at = Column(DateTime, default=datetime.utcnow)
    received_at = Column(DateTime, nullable=True)

    amount = Column(Numeric(12, 2), nullable=False, default=0.00)

    payment_method = Column(String(50), nullable=True)
    transaction_reference = Column(String(100), nullable=True)

    status = Column(String(50), default="INITIATED") # INITIATED, PROCESSING, SUCCESS, FAILED
    remarks = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        # Enforce valid states
        sqlalchemy.CheckConstraint(status.in_(['INITIATED', 'PROCESSING', 'SUCCESS', 'FAILED']), name='chk_payment_status_valid'),
        # Enforce received_at rule
        sqlalchemy.CheckConstraint(
            "(status = 'SUCCESS' AND received_at IS NOT NULL) OR (status != 'SUCCESS' AND received_at IS NULL)",
            name="chk_payment_received_at"
        ),
    )

    invoice = relationship("Invoice", back_populates="payments")
