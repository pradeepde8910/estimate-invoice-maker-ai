"""
Shared letterhead + signature block builders — used to prepend a consistent
corporate header (logo, company name, address, contact line) and append a
signature block to every generated document (quotation, BRD, SRS, invoice,
cover letter), in plain Markdown so it stays fully editable on-screen and
still renders cleanly when converted to PDF.
"""

from __future__ import annotations

from app.utils.organization import branding_url


def build_letterhead_markdown(profile: dict) -> str:
    logo_url = branding_url(profile, "logo")
    lines = []
    if logo_url:
        lines.append(f"![{profile.get('name', 'Logo')}]({logo_url})")
        lines.append("")
    lines.append(f"# {profile.get('name', 'Your Company')}")
    contact_bits = [b for b in [profile.get("address"), profile.get("phone"), profile.get("email")] if b]
    if contact_bits:
        lines.append(" · ".join(contact_bits))
    meta_bits = []
    if profile.get("website"):
        meta_bits.append(profile["website"])
    if profile.get("gstin"):
        meta_bits.append(f"GSTIN: {profile['gstin']}")
    if profile.get("registration_number"):
        meta_bits.append(f"Reg. No: {profile['registration_number']}")
    if meta_bits:
        lines.append(" · ".join(meta_bits))
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def build_signature_block_markdown(profile: dict) -> str:
    signature_url = branding_url(profile, "signature")
    seal_url = branding_url(profile, "seal")
    if not signature_url and not seal_url and not profile.get("signatory_name"):
        return ""

    lines = ["", "---", ""]
    if signature_url:
        lines.append(f"![Signature]({signature_url})")
        lines.append("")
    if seal_url:
        lines.append(f"![Seal]({seal_url})")
        lines.append("")
    if profile.get("signatory_name"):
        lines.append(f"**{profile['signatory_name']}**  ")
        lines.append(f"{profile.get('signatory_title', 'Authorized Signatory')}  ")
        lines.append(f"for {profile.get('name', '')}")
    return "\n".join(lines)


def apply_letterhead(body_markdown: str, profile: dict, *, include_signature: bool = True) -> str:
    parts = [build_letterhead_markdown(profile), body_markdown]
    if include_signature:
        parts.append(build_signature_block_markdown(profile))
    return "\n".join(p for p in parts if p)
