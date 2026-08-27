"""
Organization profile & branding service — the business-logic layer the
app/api/organization.py router calls into.

This delegates to app.utils.organization, which already implements the real
(and load-bearing — pdf_service.py and the invoice renderer read from it on
every PDF generated this session) JSON-file + filesystem-backed profile and
branding storage. It is NOT the DB-backed OrganizationProfile/BrandingAsset
model layer some restored files assumed existed; those models exist (see
app/models/organization.py) for future migration but nothing reads/writes
them yet — introducing a second, competing profile store here would silently
diverge from what PDFs actually render.
"""

from app.utils import organization as _org
from app.utils.organization import InvalidBrandingAssetError, BRANDING_DIR  # re-exported for routers/main.py

__all__ = [
    "InvalidBrandingAssetError",
    "BRANDING_DIR",
    "get_organization_profile",
    "update_organization_profile",
    "upload_branding_asset",
    "remove_branding_asset",
]


def get_organization_profile() -> dict:
    return _org.load_profile()


def update_organization_profile(fields: dict) -> dict:
    return _org.save_profile(fields)


def upload_branding_asset(slot: str, filename: str, content: bytes) -> dict:
    return _org.save_branding_file(slot, filename, content)


def remove_branding_asset(slot: str) -> dict:
    return _org.remove_branding_file(slot)
