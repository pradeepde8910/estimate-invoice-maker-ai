"""
Seeds the `billing_classifications` catalog from
backend/app/data/billing_classifications.csv.

Idempotent: re-running clears and reloads active rows rather than duplicating
them, so this is safe to run again after the CSV is edited/expanded.

Usage (from backend/app/):
    python -m scripts.seed_billing_classifications
"""
import csv
import logging
from pathlib import Path

from app.database import SessionLocal, engine
from app.models.base import Base
from app.models.master import BillingClassification

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "billing_classifications.csv"


def run_seed():
    Base.metadata.create_all(bind=engine)  # ensure the table exists (new model, not yet migrated)

    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Seed data not found: {CSV_PATH}")

    session = SessionLocal()
    try:
        rows = []
        with open(CSV_PATH, encoding="utf-8") as f:
            for raw in csv.DictReader(f):
                rows.append(
                    BillingClassification(
                        category=raw["category"].strip(),
                        description=raw["description"].strip(),
                        item_type="HARDWARE" if raw["hsn_sac_type"].strip().upper() == "HSN" else "SERVICE",
                        hsn_sac_code=raw["hsn_sac"].strip(),
                        hsn_sac_type=raw["hsn_sac_type"].strip().upper(),
                        gst_rate=raw["suggested_gst"].strip(),
                        keywords=raw["keywords"].strip(),
                        active=True,
                    )
                )

        # Reseed: this table only ever holds catalog/reference data (no invoices
        # or foreign keys point into it yet), so clearing and reloading is safe
        # and keeps this script idempotent across CSV edits.
        deleted = session.query(BillingClassification).delete()
        session.add_all(rows)
        session.commit()
        logger.info(f"Seeded {len(rows)} billing classifications (replaced {deleted} existing rows).")
    finally:
        session.close()


if __name__ == "__main__":
    run_seed()
