"""
Database infrastructure only — engine, session factory, and the schema
bootstrap/migration helpers. Model classes used to live in this file
directly (a leftover from an earlier single-file schema); they've moved to
their proper homes under app/models/ (app.models.master.Client,
app.models.user.User, app.models.organization.OrganizationProfile /
BrandingAsset, app.models.rate_card.RateCard, app.models.estimation.
Estimation / Document / Attachment, app.models.invoice.Invoice,
app.models.audit.AuditLog) so there is exactly one class per table instead
of two competing definitions registered on the same SQLAlchemy metadata
(that duplication is what caused the "Table 'clients' is already defined"
startup crash this file used to produce).

Base is still defined here and re-exported via app.models.base — every
model module imports it from there, not from this file directly, but the
underlying object is the same one either way.
"""
import datetime
from sqlalchemy import create_engine
from sqlalchemy import text as sa_text
from sqlalchemy.orm import declarative_base, sessionmaker
from app import config

engine = create_engine(
    config.DATABASE_URL,
    # SQLite-specific connection args (ignored by other databases like PostgreSQL)
    connect_args={"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_next_serial(prefix: str, session) -> str:
    from app.models.estimation import Estimation, Document
    from app.models.invoice import Invoice

    year = datetime.datetime.utcnow().year
    match_pattern = f"{prefix}-{year}-%"

    from sqlalchemy import desc
    if prefix == "EST":
        row = session.query(Estimation).filter(Estimation.estimation_number.like(match_pattern)).order_by(desc(Estimation.estimation_number)).first()
        max_val = row.estimation_number if row else None
    elif prefix == "INV":
        row = session.query(Invoice).filter(Invoice.invoice_number.like(match_pattern)).order_by(desc(Invoice.invoice_number)).first()
        max_val = row.invoice_number if row else None
    else:  # e.g. QUT, BRD, SRS
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
    from app.models.rate_card import RateCard

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
            # The DB is the absolute source of truth. We load all active rates into the config.
            config.DEVELOPER_RATES.clear()
            for db_rate in active_db_rates:
                config.DEVELOPER_RATES[db_rate.role_key] = {
                    "label": db_rate.role_label,
                    "rate_per_hour": db_rate.rate_per_hour,
                    "is_custom": db_rate.role_key not in config.SYSTEM_ROLE_KEYS
                }
    except Exception as e:
        print(f"Error syncing rate card: {e}")
    finally:
        db.close()


def restore_branding_assets():
    """Restore branding assets from the database to the local ephemeral filesystem."""
    import base64
    from app.utils.organization import BRANDING_DIR
    from app.models.organization import BrandingAsset

    BRANDING_DIR.mkdir(exist_ok=True)
    db = SessionLocal()
    try:
        assets = db.query(BrandingAsset).all()
        for asset in assets:
            dest = BRANDING_DIR / asset.file_name
            try:
                dest.write_bytes(base64.b64decode(asset.data))
            except Exception as e:
                print(f"Failed to restore branding asset {asset.file_name}: {e}")
    except Exception as e:
        print(f"Error restoring branding assets: {e}")
    finally:
        db.close()


def _run_migrations():
    """Safely add any columns that may be missing from existing tables in
    production PostgreSQL databases (SQLAlchemy create_all only creates missing
    *tables*, not missing *columns* on already-existing tables)."""
    is_postgres = not config.DATABASE_URL.startswith("sqlite")
    with engine.connect() as conn:
        migrations = [
            # organization_profiles: branding columns
            ("organization_profiles", "logo_path",       "VARCHAR(255)"),
            ("organization_profiles", "signature_path",  "VARCHAR(255)"),
            ("organization_profiles", "seal_path",       "VARCHAR(255)"),
            ("organization_profiles", "invoice_terms",   "TEXT"),
            ("organization_profiles", "bank_name",       "VARCHAR(100)"),
            ("organization_profiles", "bank_account_number", "VARCHAR(100)"),
            ("organization_profiles", "bank_ifsc",       "VARCHAR(50)"),
            ("organization_profiles", "bank_branch",     "VARCHAR(100)"),
            ("organization_profiles", "upi_id",          "VARCHAR(100)"),
            # invoices: added when Invoice absorbed the "Legacy V1
            # Compatibility" estimation-linkage fields (app/models/invoice.py)
            ("invoices", "estimation_id", "VARCHAR(255)"),
            ("invoices", "invoice_html",  "TEXT"),
        ]
        for table, col, col_type in migrations:
            try:
                if is_postgres:
                    conn.execute(sa_text(
                        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type}"
                    ))
                else:
                    # SQLite: check column existence manually
                    rows = conn.execute(sa_text(f"PRAGMA table_info({table})")).fetchall()
                    existing_cols = [r[1] for r in rows]
                    if col not in existing_cols:
                        conn.execute(sa_text(
                            f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"
                        ))
            except Exception as e:
                print(f"[migration] WARNING: could not add column {table}.{col}: {e}")
        conn.commit()


def init_db():
    # Import every model module so its class is registered on Base.metadata
    # before create_all runs — importing app.models does this in one place.
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _run_migrations()   # ensure all columns exist after schema evolves
    sync_rate_card()
    restore_branding_assets()
