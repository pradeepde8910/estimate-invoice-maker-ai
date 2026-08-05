"""
Organization profile — branding info (logo, signature, seal, company & tax
details) used to build the letterhead header and signature block on every
generated document (quotation, BRD, SRS, invoice, cover letter).

Persisted in the database.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent
BRANDING_DIR = ROOT / "branding"
BRANDING_DIR.mkdir(exist_ok=True)

DEFAULT_PROFILE = {
    "name": "Pixous Technologies Pvt Ltd",
    "tagline": "",
    "address": "382, Lakshmanar Nagar, 2nd Street (Extn.), Gandhipuram, Coimbatore - 641012, Tamil Nadu, India",
    "email": "info@pixoustech.com",
    "phone": "+91 70940 47000",
    "website": "https://pixoustech.com",
    "gstin": "",
    "registration_number": "",
    "certifications": "",
    "signatory_name": "",
    "signatory_title": "Authorized Signatory",
    "bank_name": "",
    "bank_account_number": "",
    "bank_ifsc": "",
    "bank_branch": "",
    "logo_path": None,
    "signature_path": None,
    "seal_path": None,
}

FIELD_KEYS = [
    "name", "tagline", "address", "email", "phone", "website",
    "gstin", "registration_number", "certifications", "signatory_name", "signatory_title",
    "bank_name", "bank_account_number", "bank_ifsc", "bank_branch",
]
SLOT_KEYS = ["logo_path", "signature_path", "seal_path"]


def load_profile() -> dict:
    from db import SessionLocal, OrganizationProfile
    db = SessionLocal()
    try:
        profile_row = db.query(OrganizationProfile).first()
        if not profile_row:
            # Create default profile row in DB
            profile_row = OrganizationProfile(**DEFAULT_PROFILE)
            db.add(profile_row)
            db.commit()
            db.refresh(profile_row)
        
        # Convert to dictionary
        result = {}
        for key in DEFAULT_PROFILE.keys():
            result[key] = getattr(profile_row, key, DEFAULT_PROFILE[key])
        return result
    except Exception:
        return dict(DEFAULT_PROFILE)
    finally:
        db.close()


def save_profile(fields: dict) -> dict:
    from db import SessionLocal, OrganizationProfile
    db = SessionLocal()
    try:
        profile_row = db.query(OrganizationProfile).first()
        if not profile_row:
            profile_row = OrganizationProfile(**DEFAULT_PROFILE)
            db.add(profile_row)
        for key in FIELD_KEYS:
            if key in fields:
                setattr(profile_row, key, fields[key])
        db.commit()
        db.refresh(profile_row)
        
        result = {}
        for key in DEFAULT_PROFILE.keys():
            result[key] = getattr(profile_row, key, DEFAULT_PROFILE[key])
        return result
    except Exception:
        return dict(DEFAULT_PROFILE)
    finally:
        db.close()


def save_branding_file(slot: str, filename: str, content: bytes) -> dict:
    """slot: 'logo' | 'signature' | 'seal'"""
    ext = Path(filename).suffix.lower() or ".png"
    dest = BRANDING_DIR / f"{slot}{ext}"
    # Remove any previous file for this slot with a different extension.
    for existing in BRANDING_DIR.glob(f"{slot}.*"):
        existing.unlink(missing_ok=True)
    dest.write_bytes(content)

    from db import SessionLocal, OrganizationProfile
    db = SessionLocal()
    try:
        profile_row = db.query(OrganizationProfile).first()
        if not profile_row:
            profile_row = OrganizationProfile(**DEFAULT_PROFILE)
            db.add(profile_row)
        setattr(profile_row, f"{slot}_path", dest.name)
        db.commit()
        db.refresh(profile_row)
        
        result = {}
        for key in DEFAULT_PROFILE.keys():
            result[key] = getattr(profile_row, key, DEFAULT_PROFILE[key])
        return result
    except Exception:
        return dict(DEFAULT_PROFILE)
    finally:
        db.close()


def branding_url(profile: dict, slot: str) -> str | None:
    path = profile.get(f"{slot}_path")
    return f"/branding/{path}" if path else None


def branding_abs_path(profile: dict, slot: str) -> Path | None:
    path = profile.get(f"{slot}_path")
    if not path:
        return None
    p = BRANDING_DIR / path
    return p if p.exists() else None
