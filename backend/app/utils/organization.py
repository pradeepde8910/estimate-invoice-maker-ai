"""
Organization profile — branding info (logo, signature, seal, company & tax
details) used to build the letterhead header and signature block on every
generated document (quotation, BRD, SRS, invoice, cover letter).

Persisted in the database.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent
BRANDING_DIR = ROOT / "branding"
BRANDING_DIR.mkdir(exist_ok=True)

# Extension the client asked for -> Pillow format name(s) it must actually decode as.
# Rejects anything else (svg, html, js, ...) regardless of what extension/
# Content-Type the client sent - both are attacker controlled.
ALLOWED_BRANDING_FORMATS = {
    ".png": {"PNG"},
    ".jpg": {"JPEG"},
    ".jpeg": {"JPEG"},
    ".webp": {"WEBP"},
    ".avif": {"AVIF", "HEIF"},
    ".gif": {"GIF"},
}
MAX_BRANDING_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


class InvalidBrandingAssetError(ValueError):
    pass


def _assert_valid_branding_image(ext: str, content: bytes) -> None:
    if ext not in ALLOWED_BRANDING_FORMATS:
        raise InvalidBrandingAssetError(
            f"'{ext}' is not an allowed branding asset type. "
            f"Allowed: {', '.join(sorted(ALLOWED_BRANDING_FORMATS))}."
        )
    if len(content) > MAX_BRANDING_UPLOAD_BYTES:
        raise InvalidBrandingAssetError(
            f"File exceeds the {MAX_BRANDING_UPLOAD_BYTES // (1024 * 1024)}MB limit for branding assets."
        )
    try:
        image = Image.open(io.BytesIO(content))
        image.verify()
        actual_format = (image.format or "").upper()
    except Exception as e:
        raise InvalidBrandingAssetError(f"File is not a valid image (or is corrupted): {e}")

    if actual_format not in ALLOWED_BRANDING_FORMATS[ext]:
        raise InvalidBrandingAssetError(
            f"File extension '{ext}' does not match its actual content ({actual_format or 'unknown'})."
        )

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
    "upi_id": "",
    "logo_path": None,
    "signature_path": None,
    "seal_path": None,
    "invoice_terms": "Payment is due strictly within the timeframe stated above.\nInterest @ 18% p.a. will be levied on overdue balances.\nAll legal matters and disputes are subject to the jurisdiction where the issuer is registered.\nThis is a system-generated document and requires no physical seal if signed digitally.",
}

FIELD_KEYS = [
    "name", "tagline", "address", "email", "phone", "website",
    "gstin", "registration_number", "certifications", "signatory_name", "signatory_title",
    "bank_name", "bank_account_number", "bank_ifsc", "bank_branch", "upi_id", "invoice_terms",
]
SLOT_KEYS = ["logo_path", "signature_path", "seal_path"]


def load_profile() -> dict:
    import traceback
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
        print("[organization] ERROR in load_profile:")
        traceback.print_exc()
        return dict(DEFAULT_PROFILE)
    finally:
        db.close()


def save_profile(fields: dict) -> dict:
    import traceback
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
        print("[organization] ERROR in save_profile:")
        traceback.print_exc()
        db.rollback()
        return dict(DEFAULT_PROFILE)
    finally:
        db.close()


def save_branding_file(slot: str, filename: str, content: bytes) -> dict:
    """slot: 'logo' | 'signature' | 'seal'"""
    import base64
    import traceback
    ext = Path(filename).suffix.lower() or ".png"
    # Validate BEFORE touching disk: an invalid/malicious upload must never
    # delete the existing valid asset for this slot.
    _assert_valid_branding_image(ext, content)

    dest = BRANDING_DIR / f"{slot}{ext}"
    # Remove any previous file for this slot with a different extension.
    for existing in BRANDING_DIR.glob(f"{slot}.*"):
        existing.unlink(missing_ok=True)
    dest.write_bytes(content)

    from db import SessionLocal, OrganizationProfile
    db = SessionLocal()
    try:
        # Primary: update the OrganizationProfile path reference
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
    except Exception:
        print(f"[organization] ERROR saving profile path for slot '{slot}':")
        traceback.print_exc()
        db.rollback()
        db.close()
        raise  # Re-raise so the API endpoint can return the real error
    finally:
        db.close()

    # Secondary (best-effort): back up raw bytes to BrandingAsset table so
    # assets survive ephemeral-filesystem redeploys. If the table doesn't
    # exist yet (first deploy before migration runs) this silently skips.
    try:
        from db import SessionLocal as _SL, BrandingAsset
        _db = _SL()
        try:
            asset = _db.query(BrandingAsset).filter(BrandingAsset.slot == slot).first()
            if not asset:
                asset = BrandingAsset(slot=slot)
                _db.add(asset)
            asset.file_name = f"{slot}{ext}"
            asset.data = base64.b64encode(content).decode("utf-8")
            _db.commit()
        except Exception:
            _db.rollback()
            print(f"[organization] WARNING: Could not backup branding asset '{slot}' to DB (table may not exist yet). Asset is saved to disk.")
        finally:
            _db.close()
    except Exception:
        pass  # Non-critical — disk file is already written above

    return result


def branding_url(profile: dict, slot: str) -> str | None:
    path = profile.get(f"{slot}_path")
    if path and (BRANDING_DIR / path).exists():
        return f"/branding/{path}"
    return None


def branding_abs_path(profile: dict, slot: str) -> Path | None:
    path = profile.get(f"{slot}_path")
    if not path:
        return None
    p = BRANDING_DIR / path
    return p if p.exists() else None


def remove_branding_file(slot: str) -> dict:
    """slot: 'logo' | 'signature' | 'seal'. Deletes the on-disk asset (if
    any) and clears the DB reference so the app stops trying to render it."""
    for existing in BRANDING_DIR.glob(f"{slot}.*"):
        existing.unlink(missing_ok=True)

    from db import SessionLocal, OrganizationProfile, BrandingAsset
    db = SessionLocal()
    try:
        asset = db.query(BrandingAsset).filter(BrandingAsset.slot == slot).first()
        if asset:
            db.delete(asset)

        profile_row = db.query(OrganizationProfile).first()
        if profile_row:
            setattr(profile_row, f"{slot}_path", None)
            db.commit()
            db.refresh(profile_row)
            result = {}
            for key in DEFAULT_PROFILE.keys():
                result[key] = getattr(profile_row, key, DEFAULT_PROFILE[key])
            return result
        return dict(DEFAULT_PROFILE)
    finally:
        db.close()
