import argparse
import logging
from decimal import Decimal
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from db import Client as V1Client, Estimation as V1Estimation, Invoice as V1Invoice
from v2.models.master import Client as V2Client
from v2.models.project import Project as V2Project
from v2.models.invoice import Invoice as V2Invoice
from v2.models.payment import Payment as V2Payment

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def reconcile(source_url: str, target_url: str):
    logger.info("=== Starting V1 to V2 Migration Reconciliation ===")
    
    source_engine = create_engine(source_url)
    SourceSession = sessionmaker(bind=source_engine)
    source_session = SourceSession()

    target_engine = create_engine(target_url)
    TargetSession = sessionmaker(bind=target_engine)
    target_session = TargetSession()

    mismatches = 0

    try:
        # 1. Clients
        v1_clients = source_session.query(V1Client).count()
        v2_clients = target_session.query(V2Client).count()
        logger.info(f"V1 Clients: {v1_clients}")
        logger.info(f"V2 Clients: {v2_clients}")
        if v1_clients != v2_clients:
            logger.error("MISMATCH in Clients!")
            mismatches += 1

        # 2. Projects (Estimations)
        v1_projects = source_session.query(V1Estimation).count()
        v2_projects = target_session.query(V2Project).count()
        logger.info(f"\nV1 Projects: {v1_projects}")
        logger.info(f"V2 Projects: {v2_projects}")
        if v1_projects != v2_projects:
            logger.error("MISMATCH in Projects!")
            mismatches += 1

        # 3. Invoices
        v1_invoices = source_session.query(V1Invoice).count()
        v2_invoices = target_session.query(V2Invoice).count()
        logger.info(f"\nV1 Invoices: {v1_invoices}")
        logger.info(f"V2 Invoices: {v2_invoices}")
        if v1_invoices != v2_invoices:
            logger.error("MISMATCH in Invoices!")
            mismatches += 1

        # 4. Invoice Values
        v1_inv_total = source_session.query(func.sum(V1Invoice.total)).scalar() or 0.0
        v2_inv_total = target_session.query(func.sum(V2Invoice.total_payable)).scalar() or Decimal('0.00')
        logger.info(f"\nV1 Invoice Value: {v1_inv_total:.2f}")
        logger.info(f"V2 Invoice Value: {v2_inv_total:.2f}")
        if abs(float(v1_inv_total) - float(v2_inv_total)) > 0.01:
            logger.error("MISMATCH in Invoice Values!")
            mismatches += 1

        # 5. Recorded Payments
        v1_payments = source_session.query(func.sum(V1Invoice.amount_paid)).scalar() or 0.0
        v2_payments = target_session.query(func.sum(V2Payment.amount)).filter(V2Payment.status == "SUCCESS").scalar() or Decimal('0.00')
        logger.info(f"\nV1 Recorded Payments: {v1_payments:.2f}")
        logger.info(f"V2 Recorded Payments: {v2_payments:.2f}")
        if abs(float(v1_payments) - float(v2_payments)) > 0.01:
            logger.error("MISMATCH in Recorded Payments!")
            mismatches += 1

        # 6. Outstanding
        v1_outstanding = float(v1_inv_total) - float(v1_payments)
        v2_outstanding = float(v2_inv_total) - float(v2_payments)
        logger.info(f"\nV1 Outstanding: {v1_outstanding:.2f}")
        logger.info(f"V2 Outstanding: {v2_outstanding:.2f}")
        if abs(v1_outstanding - v2_outstanding) > 0.01:
            logger.error("MISMATCH in Outstanding!")
            mismatches += 1

        logger.info("\n=== Reconciliation Result ===")
        if mismatches == 0:
            logger.info("PASS: All financial totals match perfectly.")
        else:
            logger.error(f"FAIL: Found {mismatches} mismatches! Do not promote V2.")
            exit(1)

    finally:
        source_session.close()
        target_session.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reconcile V1 and V2 Databases")
    parser.add_argument("--source", required=True, help="SQLAlchemy URL for V1 Source DB")
    parser.add_argument("--target", required=True, help="SQLAlchemy URL for V2 Target DB")
    args = parser.parse_args()

    reconcile(args.source, args.target)
