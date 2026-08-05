import sys
import os
import json
import re
import datetime
from pathlib import Path

# Add project root to path so we can import local modules
sys.path.append(str(Path(__file__).parent.parent.resolve()))

import config
import organization
from db import init_db, SessionLocal, User, Client, Estimation, Document, Invoice, generate_next_serial, RateCard

def migrate():
    print("Starting database migration...")
    
    # 1. Initialize tables and sync rate card defaults
    init_db()
    project_root = Path(__file__).parent.parent.resolve()
    db = SessionLocal()
    
    try:
        # 2. Migrate Organization Profile from JSON file
        legacy_profile_path = project_root / "organization_profile.json"
        if legacy_profile_path.exists():
            print("Found legacy organization profile. Migrating...")
            try:
                profile_data = json.loads(legacy_profile_path.read_text(encoding="utf-8"))
                organization.save_profile(profile_data)
                print("Organization profile migrated successfully.")
            except Exception as e:
                print(f"Failed to migrate organization profile: {e}")
                
        # 3. Migrate Rate Card Overrides from JSON file
        legacy_rates_path = project_root / "rate_card_overrides.json"
        if legacy_rates_path.exists():
            print("Found legacy rate card overrides. Migrating...")
            try:
                rates_data = json.loads(legacy_rates_path.read_text(encoding="utf-8"))
                for key, val in rates_data.items():
                    rate_val = val.get("rate_per_hour")
                    if rate_val:
                        # Deactivate any active
                        current = db.query(RateCard).filter(RateCard.role_key == key, RateCard.is_active == True).first()
                        if current:
                            current.is_active = False
                            current.effective_to = datetime.datetime.utcnow()
                        
                        # Add new active override
                        db_rate = RateCard(
                            role_key=key,
                            role_label=config.DEVELOPER_RATES.get(key, {}).get("label", key),
                            rate_per_hour=rate_val,
                            effective_from=datetime.datetime.utcnow(),
                            is_active=True
                        )
                        db.add(db_rate)
                db.commit()
                print("Rate card overrides migrated successfully.")
            except Exception as e:
                print(f"Failed to migrate rate card overrides: {e}")

        # 4. Migrate Output Files (Estimations, Invoices, Documents)
        out_dir = Path(config.OUTPUT_DIR)
        data_files = list(out_dir.glob("*_data.json"))
        print(f"Found {len(data_files)} legacy data files to migrate.")
        
        for f in data_files:
            # Extract base name slug
            m = re.match(r"^(.*)_data\.json$", f.name)
            if not m:
                continue
            base_name = m.group(1)
            print(f"Processing estimation: {base_name}...")
            
            try:
                # Load JSON
                data = json.loads(f.read_text(encoding="utf-8"))
                client_name = data.get("client_name") or (data.get("analysis") or {}).get("client_name") or "Unspecified Client"
                project_name = data.get("project_name") or "Manual Project"
                
                # Check if estimation already exists
                existing_est = db.query(Estimation).filter(Estimation.id == base_name).first()
                if existing_est:
                    print(f"Estimation {base_name} already exists in DB. Skipping.")
                    continue
                
                # 4a. Get or create Client
                client = db.query(Client).filter(Client.company_name == client_name).first()
                if not client:
                    client = Client(company_name=client_name, created_at=datetime.datetime.utcnow())
                    db.add(client)
                    db.commit()
                    db.refresh(client)
                
                # 4b. Create Estimation
                est_num = generate_next_serial("EST", db)
                est_sec = data.get("cost_estimation") or {}
                estimation = Estimation(
                    id=base_name,
                    estimation_number=est_num,
                    client_id=client.id,
                    project_name=project_name,
                    status="Completed",
                    timeline_weeks=float(est_sec.get("timeline_weeks", 0.0) or 0.0),
                    grand_total=float(est_sec.get("grand_total", 0.0) or 0.0),
                    raw_pipeline_json=data,
                    created_at=datetime.datetime.fromtimestamp(f.stat().st_mtime),
                    updated_at=datetime.datetime.fromtimestamp(f.stat().st_mtime)
                )
                db.add(estimation)
                
                # 4c. Create Documents (quotation, brd, srs)
                for doc_type in ("quotation", "brd", "srs"):
                    doc_path = out_dir / f"{base_name}_{doc_type}.md"
                    if doc_path.exists():
                        doc_content = doc_path.read_text(encoding="utf-8")
                        doc_num = generate_next_serial(doc_type.upper()[:3], db)
                        document = Document(
                            document_number=doc_num,
                            estimation_id=base_name,
                            type=doc_type,
                            content=doc_content,
                            version=1,
                            created_at=datetime.datetime.fromtimestamp(doc_path.stat().st_mtime),
                            updated_at=datetime.datetime.fromtimestamp(doc_path.stat().st_mtime)
                        )
                        db.add(document)
                
                # 4d. Create Invoice
                invoice_path = out_dir / f"{base_name}_invoice.html"
                if invoice_path.exists():
                    html_content = invoice_path.read_text(encoding="utf-8")
                    meta = data.get("invoice_meta") or {}
                    invoice_number = meta.get("invoice_number") or generate_next_serial("INV", db)
                    
                    # Resolve duplicate invoice numbers by appending a suffix
                    orig_number = invoice_number
                    counter = 1
                    while db.query(Invoice).filter(Invoice.invoice_number == invoice_number).first() is not None:
                        invoice_number = f"{orig_number}-{counter}"
                        counter += 1
                    
                    subtotal = float(meta.get("subtotal", 0.0))
                    gst_amount = float(meta.get("tax_amount", 0.0))
                    total = float(meta.get("total_due", 0.0))
                    
                    due_date_str = meta.get("due_date", "")
                    try:
                        due_date = datetime.datetime.strptime(due_date_str, "%Y-%m-%d")
                    except Exception:
                        due_date = datetime.datetime.utcnow() + datetime.timedelta(days=15)
                        
                    paid_on_str = meta.get("paid_on")
                    paid_on = None
                    if paid_on_str:
                        try:
                            paid_on = datetime.datetime.strptime(paid_on_str, "%Y-%m-%d")
                        except Exception:
                            pass
                            
                    invoice = Invoice(
                        invoice_number=invoice_number,
                        estimation_id=base_name,
                        subtotal=subtotal,
                        gst_amount=gst_amount,
                        discount=0.0,
                        total=total,
                        status=meta.get("status", "Draft"),
                        due_date=due_date,
                        paid_on=paid_on,
                        payment_mode=meta.get("payment_mode"),
                        invoice_html=html_content,
                        created_at=datetime.datetime.fromtimestamp(invoice_path.stat().st_mtime)
                    )
                    db.add(invoice)
                    
                db.commit()
                print(f"Estimation {base_name} migrated successfully.")
            except Exception as e:
                db.rollback()
                print(f"Failed to migrate estimation {base_name}: {e}")
                
        print("Migration complete!")
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
