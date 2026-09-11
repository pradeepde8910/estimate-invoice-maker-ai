"""
Shared letterhead + signature block builders — used to prepend a consistent
corporate header (logo, company name, address, contact line) and append a
signature block to every generated document (quotation, BRD, SRS, invoice,
cover letter), in plain Markdown so it stays fully editable on-screen and
still renders cleanly when converted to PDF.
"""

from __future__ import annotations

import re

from app.utils.organization import branding_url


def _hard_break_join(items: list[str]) -> str:
    """
    Joins already-formatted lines with a markdown hard break (two trailing
    spaces + newline) so each stays on its own visual line regardless of
    renderer — plain consecutive lines with no blank line between them are
    CommonMark for "one wrapped paragraph", which is exactly the bug this
    letterhead used to have.
    """
    return "  \n".join(items)


def build_letterhead_markdown(profile: dict) -> str:
    logo_url = branding_url(profile, "logo")
    lines = []
    if logo_url:
        lines.append(f"![{profile.get('name', 'Logo')}]({logo_url})")
        lines.append("")

    lines.append("**ORGANIZATION DETAILS**")
    lines.append("")
    lines.append(f"# {profile.get('name', 'Your Company')}")

    # The address field is a free-form textarea (see OrganizationSettings),
    # so it may already contain manually entered line breaks — preserve
    # those as hard breaks rather than only ever relying on the renderer's
    # own soft-wrap for a single long line.
    address = (profile.get("address") or "").strip()
    if address:
        address_lines = [ln.strip() for ln in address.splitlines() if ln.strip()]
        if address_lines:
            lines.append(_hard_break_join(address_lines))

    contact_lines = []
    if profile.get("phone"):
        contact_lines.append(f"Phone: {profile['phone']}")
    if profile.get("email"):
        contact_lines.append(f"Email: {profile['email']}")
    if profile.get("website"):
        website = profile["website"]
        display = re.sub(r"^https?://", "", website)
        contact_lines.append(f"Website: [{display}]({website})")
    if contact_lines:
        lines.append("")
        lines.append("**Contact Information**  ")
        lines.append(_hard_break_join(contact_lines))

    statutory_lines = []
    if profile.get("gstin"):
        statutory_lines.append(f"GSTIN: {profile['gstin']}")
    if profile.get("registration_number"):
        statutory_lines.append(f"Reg. No: {profile['registration_number']}")
    if statutory_lines:
        lines.append("")
        lines.append("**Statutory Information**  ")
        lines.append(_hard_break_join(statutory_lines))

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
