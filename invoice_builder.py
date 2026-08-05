"""
Invoice Builder — turns a completed estimation (or manually entered line
items) into a professional, self-contained HTML tax invoice.

Deterministic (no LLM calls) — every number here already exists in the
estimation data; this is a disciplined re-presentation of it as a styled
document, plus tax/due-date terms and the organization's branding.

The output is a full standalone HTML document (own <style> block) so it can
be rendered as-is in an iframe on screen, edited as raw HTML, and converted
straight to PDF without an intermediate Markdown step.

Layout note: every multi-column section is built with <table> rather than
flexbox/grid. A real browser (the on-screen iframe) would render either
fine, but the PDF path (xhtml2pdf/reportlab) only understands block, inline
and table layout — no flexbox, no CSS grid, and no CSS custom properties
(var(--x)). Using tables everywhere keeps the screen and PDF renders
identical instead of maintaining two separate stylesheets.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from html import escape

from organization import branding_url

STATUS_COLORS = {
    "Draft": ("#FEF3C7", "#92400E"),
    "Sent": ("#DBEAFE", "#1E40AF"),
    "Paid": ("#DCFCE7", "#166534"),
    "Overdue": ("#FEE2E2", "#991B1B"),
    "Cancelled": ("#E2E8F0", "#475569"),
}

# primary=#0F172A accent=#2563EB text=#334155 muted=#64748B border=#E2E8F0 bg-light=#F8FAFC
CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; font-family: "Google Sans Flex", "Google Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
body { background-color: #F1F5F9; color: #334155; padding: 40px 12px; font-size: 13px; line-height: 1.5; }
.invoice-card { max-width: 800px; margin: 0 auto; background: #FFFFFF; padding: 48px; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
.layout-table { width: 100%; border-collapse: collapse; }
.layout-table td { padding: 0; border: none; vertical-align: top; }
.header-table { border-bottom: 2px solid #0F172A; padding-bottom: 24px; }
.logo-container { display: block; margin-bottom: 12px; }
.brand-logo { max-height: 48px; width: auto; object-fit: contain; display: inline-block; vertical-align: middle; margin-right: 10px; }
.brand-name { font-size: 22px; font-weight: 800; letter-spacing: -0.5px; color: #0F172A; line-height: 1.1; display: inline-block; vertical-align: middle; }
.brand-tagline { font-size: 11px; color: #2563EB; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px; }
.company-address { color: #64748B; font-size: 12px; max-width: 340px; line-height: 1.4; }
.invoice-title-block { text-align: right; }
.invoice-title { font-size: 28px; font-weight: 800; color: #0F172A; text-transform: uppercase; letter-spacing: 1px; }
.badge { display: inline-block; font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 4px; text-transform: uppercase; margin-top: 4px; }
.section-label { font-size: 10px; font-weight: 700; text-transform: uppercase; color: #64748B; letter-spacing: 0.5px; margin-bottom: 6px; }
.client-name { font-size: 15px; font-weight: 700; color: #0F172A; }
.meta-table { width: auto; margin-top: 6px; border-collapse: collapse; }
.meta-table td { border: none; padding: 2px 10px 2px 0; font-size: 12px; vertical-align: top; }
.meta-table td.dt { color: #64748B; font-weight: 500; white-space: nowrap; }
.meta-table td.dd { color: #334155; font-weight: 600; }
.items-table { width: 100%; border-collapse: collapse; text-align: left; margin: 28px 0; }
.items-table th { background-color: #F8FAFC; color: #64748B; font-size: 10px; font-weight: 700; text-transform: uppercase; padding: 10px 12px; border-bottom: 1px solid #E2E8F0; }
.items-table td { padding: 14px 12px; border-bottom: 1px solid #E2E8F0; font-size: 13px; }
.text-right { text-align: right; }
.text-center { text-align: center; }
.payment-box { background: #F8FAFC; padding: 16px; border-radius: 6px; border: 1px solid #E2E8F0; }
.payment-box h4 { font-size: 11px; text-transform: uppercase; color: #64748B; margin-bottom: 8px; }
.totals-table { width: 100%; border-collapse: collapse; }
.totals-table td { border: none; padding: 6px 0; font-size: 12px; color: #64748B; }
.totals-table tr.grand-total td { border-top: 2px solid #0F172A; padding-top: 10px; font-size: 16px; font-weight: 700; color: #0F172A; }
.footer-section { margin-top: 40px; padding-top: 20px; border-top: 1px solid #E2E8F0; }
.signature-box { text-align: center; width: 220px; }
.signature-space { height: 50px; }
.signature-space img { max-height: 48px; }
.signature-title { font-size: 11px; font-weight: 600; color: #64748B; border-top: 1px solid #E2E8F0; padding-top: 4px; }
.terms-list { font-size: 10px; color: #64748B; line-height: 1.6; padding-left: 14px; }
.company-legal-footer { margin-top: 24px; text-align: center; font-size: 10px; color: #64748B; background: #F8FAFC; padding: 8px; border-radius: 4px; }
@media print { body { background: #fff; padding: 0; } .invoice-card { box-shadow: none; padding: 0; } }
"""


def _inr(n: float) -> str:
    return f"₹{n:,.2f}"


def _meta_table(pairs: list[tuple[str, str]]) -> str:
    rows = "".join(f'<tr><td class="dt">{escape(k)}</td><td class="dd">{escape(v)}</td></tr>' for k, v in pairs if v)
    return f'<table class="meta-table">{rows}</table>' if rows else ""


def build_invoice(
    data: dict,
    business_profile: dict,
    invoice_number: str,
    tax_percentage: float = 18.0,
    due_days: int = 15,
    invoice_date: str | None = None,
    status: str = "Draft",
) -> tuple[str, dict]:
    """Build a styled HTML invoice from estimation data. Returns (html, invoice_meta)."""
    analysis = data.get("analysis") or {}
    estimation = data.get("cost_estimation") or {}
    client_name = data.get("client_name") or analysis.get("client_name") or "Unspecified Client"
    project_name = data.get("project_name") or analysis.get("project_name") or "Untitled Project"

    now = datetime.now() if not invoice_date else datetime.fromisoformat(invoice_date)
    due = now + timedelta(days=due_days)

    role_estimates = estimation.get("role_estimates", [])
    contingency_amount = estimation.get("contingency_amount", 0)
    contingency_pct = estimation.get("contingency_percentage", 0)
    infra_monthly = estimation.get("infrastructure_cost_monthly", 0)
    license_monthly = estimation.get("third_party_licenses_monthly", 0)
    subtotal = estimation.get("grand_total", 0)
    tax_amount = subtotal * (tax_percentage / 100)
    total_due = subtotal + tax_amount

    # ── Line items ──
    rows_html = []
    idx = 1
    for r in sorted(role_estimates, key=lambda x: x.get("total_cost", 0), reverse=True):
        rows_html.append(f"""
            <tr>
                <td>{idx}</td>
                <td><strong>{escape(r.get('role_label', ''))}</strong></td>
                <td class="text-center">{r.get('hours', 0):.0f}</td>
                <td class="text-right">{_inr(r.get('rate_per_hour', 0))}</td>
                <td class="text-center">{tax_percentage:.0f}%</td>
                <td class="text-right">{_inr(r.get('total_cost', 0))}</td>
            </tr>""")
        idx += 1

    def extra_row(label: str, amount: float) -> str:
        nonlocal idx
        row_html = f"""
            <tr>
                <td>{idx}</td>
                <td><strong>{escape(label)}</strong></td>
                <td class="text-center">—</td>
                <td class="text-right">—</td>
                <td class="text-center">{tax_percentage:.0f}%</td>
                <td class="text-right">{_inr(amount)}</td>
            </tr>"""
        idx += 1
        return row_html

    if infra_monthly:
        rows_html.append(extra_row("Infrastructure & Hosting (6 months)", infra_monthly * 6))
    if license_monthly:
        rows_html.append(extra_row("Third-Party Licenses & Services (6 months)", license_monthly * 6))
    if contingency_amount:
        rows_html.append(extra_row(f"Contingency ({contingency_pct:.0f}%)", contingency_amount))

    # ── Branding ──
    logo_url = branding_url(business_profile, "logo")
    signature_url = branding_url(business_profile, "signature")
    logo_html = (
        f'<img src="{logo_url}" alt="{escape(business_profile.get("name", "Logo"))}" class="brand-logo" onerror="this.style.display=\'none\';" />'
        if logo_url
        else ""
    )
    tagline_html = (
        f'<div class="brand-tagline">{escape(business_profile["tagline"])}</div>' if business_profile.get("tagline") else ""
    )
    signature_img_html = f'<img src="{signature_url}" alt="Signature" />' if signature_url else ""

    badge_bg, badge_fg = STATUS_COLORS.get(status, STATUS_COLORS["Draft"])

    # ── Bank details (only shown if configured) ──
    if business_profile.get("bank_name"):
        bank_box_html = f"""
        <div class="payment-box">
            <h4>Bank Payment Details</h4>
            {_meta_table([
                ("Bank:", business_profile.get("bank_name", "")),
                ("A/C No:", business_profile.get("bank_account_number", "")),
                ("IFSC:", business_profile.get("bank_ifsc", "")),
                ("Branch:", business_profile.get("bank_branch", "")),
            ])}
        </div>"""
    else:
        bank_box_html = "<div></div>"

    # ── Client meta (only fields we actually have) ──
    client_meta_html = _meta_table([("Project:", project_name)])

    invoice_meta_html = _meta_table([
        ("Invoice Date:", now.strftime("%b %d, %Y")),
        ("Due Date:", due.strftime("%b %d, %Y")),
        ("Payment Terms:", f"NET {due_days}"),
    ])

    legal_bits = []
    if business_profile.get("gstin"):
        legal_bits.append(f"<strong>GSTIN:</strong> {escape(business_profile['gstin'])}")
    if business_profile.get("registration_number"):
        legal_bits.append(f"<strong>Reg. No:</strong> {escape(business_profile['registration_number'])}")
    legal_line = " | ".join(legal_bits)
    certifications_line = (
        f"<br>{escape(business_profile['certifications'])}" if business_profile.get("certifications") else ""
    )
    legal_footer_html = ""
    if legal_line or certifications_line:
        legal_footer_html = f'<div class="company-legal-footer">{escape(business_profile.get("name",""))}{" | " + legal_line if legal_line else ""}{certifications_line}</div>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Tax Invoice - {escape(business_profile.get('name', ''))}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Google+Sans+Flex:opsz,wght@6..144,1..1000&family=Google+Sans:ital,opsz,wght@0,17..18,400..700;1,17..18,400..700&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="invoice-card">
    <header class="header-table">
        <table class="layout-table"><tr>
            <td style="width: 60%;">
                <div class="logo-container">
                    {logo_html}
                    <span class="brand-name">{escape(business_profile.get('name', '').upper())}</span>
                </div>
                {tagline_html}
                <div class="company-address">
                    {escape(business_profile.get('address', ''))}<br>
                    {escape(business_profile.get('phone', ''))} | {escape(business_profile.get('email', ''))}<br>
                    {escape(business_profile.get('website', ''))}
                </div>
            </td>
            <td class="invoice-title-block" style="width: 40%;">
                <div class="invoice-title">Tax Invoice</div>
                <div class="badge" style="background:{badge_bg};color:{badge_fg};">{escape(status)}</div>
                <div style="margin-top: 12px; font-size: 12px; font-weight: 600; color: #0F172A;"># {escape(invoice_number)}</div>
            </td>
        </tr></table>
    </header>

    <section style="margin: 28px 0;">
        <table class="layout-table"><tr>
            <td style="width: 50%; padding-right: 16px;">
                <div class="section-label">Billed To</div>
                <div class="client-name">{escape(client_name)}</div>
                {client_meta_html}
            </td>
            <td style="width: 50%; padding-left: 16px;">
                <div class="section-label">Invoice Details</div>
                {invoice_meta_html}
            </td>
        </tr></table>
    </section>

    <section>
        <table class="items-table">
            <thead>
                <tr>
                    <th style="width: 5%;">#</th>
                    <th style="width: 45%;">Item &amp; Description</th>
                    <th class="text-center" style="width: 10%;">Qty</th>
                    <th class="text-right" style="width: 15%;">Unit Rate</th>
                    <th class="text-center" style="width: 10%;">GST</th>
                    <th class="text-right" style="width: 15%;">Amount</th>
                </tr>
            </thead>
            <tbody>{''.join(rows_html)}
            </tbody>
        </table>
    </section>

    <section style="margin-top: 20px;">
        <table class="layout-table"><tr>
            <td style="width: 55%; padding-right: 16px;">{bank_box_html}</td>
            <td style="width: 45%;">
                <table class="totals-table">
                    <tr><td>Subtotal</td><td class="text-right">{_inr(subtotal)}</td></tr>
                    <tr><td>GST ({tax_percentage:.0f}%)</td><td class="text-right">{_inr(tax_amount)}</td></tr>
                    <tr class="grand-total"><td>Grand Total (INR)</td><td class="text-right">{_inr(total_due)}</td></tr>
                </table>
            </td>
        </tr></table>
    </section>

    <footer class="footer-section">
        <table class="layout-table"><tr><td style="text-align: right;">
            <table style="display: inline-table;"><tr><td class="signature-box">
                <div class="signature-space">{signature_img_html}</div>
                <div class="signature-title">For {escape(business_profile.get('name', '').upper())}<br><small>({escape(business_profile.get('signatory_title', 'Authorized Signatory'))})</small></div>
            </td></tr></table>
        </td></tr></table>
        <div style="margin-top: 24px;">
            <div class="section-label">Terms &amp; Conditions</div>
            <ol class="terms-list">
                <li>Payment is due strictly within the timeframe stated above.</li>
                <li>Interest @ 18% p.a. will be levied on overdue balances.</li>
                <li>All legal matters and disputes are subject to the jurisdiction where {escape(business_profile.get('name', 'the issuer'))} is registered.</li>
                <li>This is a system-generated document and requires no physical seal if signed digitally.</li>
            </ol>
        </div>
        {legal_footer_html}
    </footer>
</div>
</body>
</html>"""

    invoice_meta = {
        "invoice_number": invoice_number,
        "invoice_date": now.isoformat(),
        "due_date": due.isoformat(),
        "tax_percentage": tax_percentage,
        "subtotal": subtotal,
        "tax_amount": tax_amount,
        "total_due": total_due,
        "client_name": client_name,
        "project_name": project_name,
        "status": status,
    }

    return html, invoice_meta
