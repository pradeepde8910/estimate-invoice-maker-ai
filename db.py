import uuid
import datetime
from sqlalchemy import (
    create_engine, Column, String, Float, DateTime, Boolean, ForeignKey, Integer, Text, JSON
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import config

# Use DATABASE_URL from configuration
engine = create_engine(
    config.DATABASE_URL,
    # SQLite-specific connection args (ignored by other databases like PostgreSQL)
    connect_args={"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="Admin")  # Admin, PM, Finance, Developer
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    audit_logs = relationship("AuditLog", back_populates="user")


class OrganizationProfile(Base):
    __tablename__ = "organization_profiles"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), default="Pixous Technologies Pvt Ltd")
    tagline = Column(String(255), default="")
    address = Column(Text, default="")
    email = Column(String(100), default="")
    phone = Column(String(50), default="")
    website = Column(String(100), default="")
    gstin = Column(String(50), default="")
    registration_number = Column(String(50), default="")
    certifications = Column(Text, default="")
    bank_name = Column(String(100), default="")
    bank_account_number = Column(String(100), default="")
    bank_ifsc = Column(String(50), default="")
    bank_branch = Column(String(100), default="")
    signatory_name = Column(String(100), default="")
    signatory_title = Column(String(100), default="Authorized Signatory")
    logo_path = Column(String(255), nullable=True)
    signature_path = Column(String(255), nullable=True)
    seal_path = Column(String(255), nullable=True)


class RateCard(Base):
    __tablename__ = "rate_cards"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    role_key = Column(String(100), nullable=False, index=True)
    role_label = Column(String(100), nullable=False)
    rate_per_hour = Column(Float, nullable=False)
    effective_from = Column(DateTime, default=datetime.datetime.utcnow)
    effective_to = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)


class Client(Base):
    __tablename__ = "clients"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_name = Column(String(255), unique=True, nullable=False, index=True)
    contact_person = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    gstin = Column(String(50), nullable=True)
    billing_address = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    estimations = relationship("Estimation", back_populates="client")


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
    raw_pipeline_json = Column(JSON, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    client = relationship("Client", back_populates="estimations")
    documents = relationship("Document", back_populates="estimation", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="estimation", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_number = Column(String(100), unique=True, nullable=False, index=True)
    estimation_id = Column(String(255), ForeignKey("estimations.id"), nullable=False)
    type = Column(String(50), nullable=False)  # quotation, brd, srs
    content = Column(Text, nullable=False)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    estimation = relationship("Estimation", back_populates="documents")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_number = Column(String(100), unique=True, nullable=False, index=True)
    estimation_id = Column(String(255), ForeignKey("estimations.id"), nullable=False)
    subtotal = Column(Float, default=0.0)
    gst_amount = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    total = Column(Float, default=0.0)
    status = Column(String(50), default="Draft")  # Draft, Sent, Paid, Overdue, Cancelled
    due_date = Column(DateTime, nullable=False)
    paid_on = Column(DateTime, nullable=True)
    payment_mode = Column(String(50), nullable=True)
    invoice_html = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    estimation = relationship("Estimation", back_populates="invoices")


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type = Column(String(50), nullable=False)  # e.g., organization, estimation, document
    entity_id = Column(String(255), nullable=False)
    file_name = Column(String(255), nullable=False)
    path = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(255), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="audit_logs")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_next_serial(prefix: str, session) -> str:
    year = datetime.datetime.utcnow().year
    match_pattern = f"{prefix}-{year}-%"
    
    from sqlalchemy import desc
    if prefix == "EST":
        row = session.query(Estimation).filter(Estimation.estimation_number.like(match_pattern)).order_by(desc(Estimation.estimation_number)).first()
        max_val = row.estimation_number if row else None
    elif prefix == "INV":
        row = session.query(Invoice).filter(Invoice.invoice_number.like(match_pattern)).order_by(desc(Invoice.invoice_number)).first()
        max_val = row.invoice_number if row else None
    else: # e.g. QUT, BRD, SRS
        row = session.query(Document).filter(Document.document_number.like(match_pattern)).order_by(desc(Document.document_number)).first()
        max_val = row.document_number if row else None

    if max_val:
        try:
            parts = max_val.split("-")
            num = int(parts[-1])
            next_num = num + 1
        except Exception:
            next_num = 1
    else:
        next_num = 1
    
    return f"{prefix}-{year}-{next_num:06d}"


def sync_rate_card():
    """Sync static DEVELOPER_RATES in config.py with database rate_cards table."""
    db = SessionLocal()
    try:
        # Load all active rates
        active_db_rates = db.query(RateCard).filter(RateCard.is_active == True).all()
        
        if not active_db_rates:
            # Table is empty, initialize it with defaults from config.py
            for key, val in config.DEVELOPER_RATES.items():
                db_rate = RateCard(
                    role_key=key,
                    role_label=val["label"],
                    rate_per_hour=val["rate_per_hour"],
                    effective_from=datetime.datetime.utcnow(),
                    is_active=True
                )
                db.add(db_rate)
            db.commit()
        else:
            # Sync config.DEVELOPER_RATES with DB values
            for db_rate in active_db_rates:
                if db_rate.role_key in config.DEVELOPER_RATES:
                    config.DEVELOPER_RATES[db_rate.role_key]["rate_per_hour"] = db_rate.rate_per_hour
    except Exception as e:
        print(f"Error syncing rate card: {e}")
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    sync_rate_card()
