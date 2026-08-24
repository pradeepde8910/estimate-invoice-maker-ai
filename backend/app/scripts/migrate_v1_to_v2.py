import argparse
import logging
from decimal import Decimal
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db import Base as V1Base
from db import Client as V1Client, Estimation as V1Estimation, Invoice as V1Invoice

from app.models.base import Base as V2Base
from app.models.master import Client as V2Client, User as V2User
from app.models.project import Project as V2Project, ProjectBillingConfig as V2BillingConfig
from app.models.invoice import Invoice as V2Invoice
from app.models.payment import Payment as V2Payment

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_migration(source_url: str, target_url: str):
    logger.info(f"Connecting to V1 Source: {source_url}")
    source_engine = create_engine(source_url)
    SourceSession = sessionmaker(bind=source_engine)
    source_session = SourceSession()

    logger.info(f"Connecting to V2 Target: {target_url}")
    target_engine = create_engine(target_url)
    V2Base.metadata.create_all(bind=target_engine)
    TargetSession = sessionmaker(bind=target_engine)
    target_session = TargetSession()

    try:
        # 1. Migrate Clients
        logger.info("Migrating Clients...")
        v1_clients = source_session.query(V1Client).all()
        for v1_c in v1_clients:
            v2_c = target_session.query(V2Client).filter_by(id=v1_c.id).first()
            if not v2_c:
                v2_c = V2Client(
                    id=v1_c.id,
                    company_name=v1_c.company_name,
                    contact_person=v1_c.contact_person,
                    email=v1_c.email,
                    phone=v1_c.phone,
                    gstin=v1_c.gstin,
                    billing_address=v1_c.billing_address,
                    created_at=v1_c.created_at or datetime.utcnow()
                )
                target_session.add(v2_c)
        target_session.commit()
        logger.info(f"Migrated {len(v1_clients)} clients.")

        # 2. Migrate Projects (Estimations)
        logger.info("Migrating Projects...")
        v1_estimations = source_session.query(V1Estimation).all()
        for v1_e in v1_estimations:
            v2_p = target_session.query(V2Project).filter_by(id=v1_e.id).first()
            if not v2_p:
                status_map = {
                    "Draft": "Draft",
                    "Processing": "Active",
                    "Completed": "Completed",
                    "Approved": "Active",
                    "Sent": "Active",
                    "Archived": "Archived"
                }
                v2_p = V2Project(
                    id=v1_e.id,
                    client_id=v1_e.client_id,
                    project_number=v1_e.estimation_number,
                    project_name=v1_e.project_name,
                    status=status_map.get(v1_e.status, "Active"),
                    contract_value=Decimal(str(v1_e.grand_total)),
                    created_at=v1_e.created_at or datetime.utcnow()
                )
                target_session.add(v2_p)

                # Add default billing config so V2 invoices can be generated if needed later
                from app.models.master import BillingType
                billing_type = target_session.query(BillingType).filter_by(code="PERCENTAGE").first()
                if not billing_type:
                    billing_type = BillingType(code="PERCENTAGE", description="Percentage Billing")
                    target_session.add(billing_type)
                    target_session.flush()

                v2_bc = V2BillingConfig(
                    project_id=v1_e.id,
                    billing_type_id=billing_type.id,
                    gst_percentage=Decimal('18.00'),
                    hsn_sac_code="9983"
                )
                target_session.add(v2_bc)
        target_session.commit()
        logger.info(f"Migrated {len(v1_estimations)} projects.")

        # 3. Migrate Invoices & synthesize Payments
        logger.info("Migrating Invoices and Payments...")
        v1_invoices = source_session.query(V1Invoice).all()
        for v1_inv in v1_invoices:
            v2_inv = target_session.query(V2Invoice).filter_by(id=v1_inv.id).first()
            if not v2_inv:
                # Resolve Client ID from Estimation
                v1_e = source_session.query(V1Estimation).filter_by(id=v1_inv.estimation_id).first()
                if not v1_e:
                    logger.warning(f"Skipping invoice {v1_inv.id}: Estimation not found")
                    continue

                status_map = {
                    "Draft": "DRAFT",
                    "Sent": "ISSUED",
                    "Paid": "ISSUED",
                    "Partially Paid": "ISSUED",
                    "Overdue": "ISSUED",
                    "Cancelled": "CANCELLED"
                }
                mapped_status = status_map.get(v1_inv.status, "ISSUED")

                # Map payment status
                if v1_inv.amount_paid >= v1_inv.total and v1_inv.total > 0:
                    payment_status = "PAID"
                elif v1_inv.amount_paid > 0:
                    payment_status = "PARTIALLY_PAID"
                else:
                    payment_status = "UNPAID"

                gross_amount = Decimal(str(v1_inv.subtotal + v1_inv.gst_amount))
                v2_inv = V2Invoice(
                    id=v1_inv.id,
                    invoice_number=v1_inv.invoice_number,
                    project_id=v1_inv.estimation_id,
                    client_id=v1_e.client_id,
                    billing_type="PERCENTAGE",
                    billing_percentage=Decimal('100.00'), # Placeholder for migrated
                    subtotal=Decimal(str(v1_inv.subtotal)),
                    gross_amount=gross_amount,
                    total_payable=Decimal(str(v1_inv.total)),
                    status=mapped_status,
                    payment_status=payment_status,
                    created_at=v1_inv.created_at or datetime.utcnow()
                )
                target_session.add(v2_inv)

                # Synthesize payment if amount_paid > 0
                if v1_inv.amount_paid > 0:
                    # Check if payment already synthesized
                    existing_payment = target_session.query(V2Payment).filter_by(invoice_id=v1_inv.id).first()
                    if not existing_payment:
                        received_at = v1_inv.paid_on or datetime.utcnow()
                        pay = V2Payment(
                            invoice_id=v1_inv.id,
                            amount=Decimal(str(v1_inv.amount_paid)),
                            status="SUCCESS",
                            payment_method=v1_inv.payment_mode or "MIGRATED",
                            received_at=received_at,
                            remarks="Migrated from V1 amount_paid"
                        )
                        target_session.add(pay)

        target_session.commit()
        logger.info(f"Migrated {len(v1_invoices)} invoices and synthesized payments.")

        logger.info("Migration completed successfully.")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        target_session.rollback()
        raise
    finally:
        source_session.close()
        target_session.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate V1 DB to V2 DB")
    parser.add_argument("--source", required=True, help="SQLAlchemy URL for V1 Source DB (e.g., sqlite:///pixous_prod.db)")
    parser.add_argument("--target", required=True, help="SQLAlchemy URL for V2 Target DB (e.g., sqlite:///v2_staging.db)")
    args = parser.parse_args()

    run_migration(args.source, args.target)
