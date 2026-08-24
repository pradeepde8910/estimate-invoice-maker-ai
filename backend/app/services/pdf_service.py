"""
V2 invoice PDF renderer.

Builds a professional, self-contained HTML tax invoice from the invoice's
own persisted DB snapshot (client, project, bank and line-item fields already
frozen on the Invoice/InvoiceItem rows at creation time — see
app/services/invoice_service.py) and renders it to PDF via
app.utils.pdf_builder.html_to_pdf.

Seller identity (company name, address, GSTIN, logo, signatory) has no
snapshot field on the V2 Invoice model yet, so it's read live from the
shared organization profile (app.utils.organization) — the same source the
V1 invoice builder uses. Reuses that module's CSS for visual consistency
with V1-generated documents and because it's already tuned for the
PDF-rendering engines in pdf_builder (table-based layout, no flexbox/grid).
"""

from __future__ import annotations

import base64
import io
from html import escape
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.utils.organization import load_profile, branding_url

from v1.invoice_builder import CSS, STATUS_COLORS, _meta_table, _inr


def _upi_qr_data_uri(upi_id: str, payee_name: str, amount, invoice_number: str) -> str | None:
    """Base64 PNG data URI for a UPI payment QR code, or None if no UPI ID is configured."""
    if not upi_id:
        return None
    import qrcode

    upi_uri = (
        f"upi://pay?pa={quote(upi_id)}&pn={quote(payee_name)}"
        f"&am={float(amount):.2f}&cu=INR&tn={quote(invoice_number or 'Invoice Payment')}"
    )
    img = qrcode.make(upi_uri, box_size=4, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"

_ONES = [
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
    "Seventeen", "Eighteen", "Nineteen",
]
_TENS = [
    "", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety",
]


def _under_1000_words(n: int) -> str:
    if n == 0:
        return ""
    if n < 20:
        return _ONES[n]
    if n < 100:
        return (_TENS[n // 10] + (f" {_ONES[n % 10]}" if n % 10 else "")).strip()
    return (_ONES[n // 100] + " Hundred" + (f" {_under_1000_words(n % 100)}" if n % 100 else "")).strip()


def amount_in_words(amount) -> str:
    """Indian numbering (crore/lakh/thousand) amount-in-words for GST invoices."""
    rupees = int(amount)
    paise = round((float(amount) - rupees) * 100)

    if rupees == 0:
        rupee_words = "Zero"
    else:
        parts = []
        crore, rupees = divmod(rupees, 10_000_000)
        lakh, rupees = divmod(rupees, 100_000)
        thousand, rupees = divmod(rupees, 1000)
        hundred = rupees

        if crore:
            parts.append(f"{_under_1000_words(crore)} Crore")
        if lakh:
            parts.append(f"{_under_1000_words(lakh)} Lakh")
        if thousand:
            parts.append(f"{_under_1000_words(thousand)} Thousand")
        if hundred:
            parts.append(_under_1000_words(hundred))
        rupee_words = " ".join(parts)

    words = f"Rupees {rupee_words} Only"
    if paise:
        words = f"Rupees {rupee_words} and {_under_1000_words(paise)} Paise Only"
    return words


def _group_items(items: list) -> list[dict]:
    """Group line items by milestone/component, then by requirement — mirrors
    the on-screen grouping in frontend/src/pages/InvoiceViewV2.tsx so the PDF
    and the web view present the same structure."""
    groups: dict[str, dict] = {}
    for item in items:
        group_id = item.milestone_id or (f"comp_{item.component_id}" if item.component_id else "other")
        group_name = item.milestone_name or ("Commercial Components" if item.component_id else "Other Items")
        group = groups.setdefault(group_id, {"name": group_name, "requirements": {}, "total": 0.0})

        req_name = item.requirement_name or "General"
        req = group["requirements"].setdefault(req_name, {"name": req_name, "items": [], "total": 0.0})
        req["items"].append(item)
        req["total"] += float(item.amount)
        group["total"] += float(item.amount)

    return list(groups.values())


def generate_invoice_pdf(session: Session, invoice_id: str) -> bytes:
    invoice = session.query(Invoice).filter_by(id=invoice_id).first()
    if not invoice:
        raise ValueError("Invoice not found")

    profile = load_profile()
    logo_url = branding_url(profile, "logo")
    signature_url = branding_url(profile, "signature")
    seal_url = branding_url(profile, "seal")

    logo_html = (
        f'<img src="{logo_url}" alt="{escape(profile.get("name", "Logo"))}" class="brand-logo" onerror="this.style.display=\'none\';" />'
        if logo_url else ""
    )
    tagline_html = f'<div class="brand-tagline">{escape(profile["tagline"])}</div>' if profile.get("tagline") else ""
    signature_img_html = f'<img src="{signature_url}" alt="Signature" />' if signature_url else ""
    seal_img_html = f'<img src="{seal_url}" alt="Seal" />' if seal_url else ""

    status_label = {"DRAFT": "Draft", "ISSUED": "Sent", "CANCELLED": "Cancelled"}.get(invoice.status, invoice.status)
    if invoice.payment_status == "PAID":
        status_label = "Paid"
    elif invoice.payment_status == "PARTIALLY_PAID":
        status_label = "Partially Paid"
    badge_bg, badge_fg = STATUS_COLORS.get(status_label, STATUS_COLORS["Draft"])

    # ── Billed-to block (from the invoice's own client snapshot — never the live client record) ──
    client_meta_pairs = []
    if invoice.project_name:
        client_meta_pairs.append(("Project:", invoice.project_name))
    if invoice.client_address:
        client_meta_pairs.append(("Address:", invoice.client_address))
    if invoice.client_gstin:
        client_meta_pairs.append(("GSTIN:", invoice.client_gstin))
    if invoice.client_email:
        client_meta_pairs.append(("Email:", invoice.client_email))
    if invoice.client_phone:
        client_meta_pairs.append(("Phone:", invoice.client_phone))
    client_meta_html = _meta_table(client_meta_pairs)

    invoice_meta_pairs = []
    if invoice.invoice_date:
        invoice_meta_pairs.append(("Invoice Date:", invoice.invoice_date.strftime("%b %d, %Y")))
    if invoice.due_date:
        invoice_meta_pairs.append(("Due Date:", invoice.due_date.strftime("%b %d, %Y")))
    if invoice.payment_terms:
        invoice_meta_pairs.append(("Payment Terms:", invoice.payment_terms))
    if invoice.po_number:
        invoice_meta_pairs.append(("PO Number:", invoice.po_number))
    invoice_meta_html = _meta_table(invoice_meta_pairs)

    # ── Line items — grouped like the on-screen view, HSN/SAC shown per item ──
    rows_html = []
    sno = 0
    for group in _group_items(invoice.items):
        rows_html.append(
            f'<tr><td colspan="5" style="background:#F8FAFC;font-weight:700;'
            f'text-transform:uppercase;letter-spacing:0.5px;font-size:11px;color:#0F172A;">'
            f'{escape(group["name"])}</td></tr>'
        )
        for req in group["requirements"].values():
            if req["name"] != "General":
                rows_html.append(
                    f'<tr><td colspan="5" style="font-size:11px;font-weight:700;color:#64748B;'
                    f'padding-left:24px;">{escape(req["name"])}</td></tr>'
                )
            for item in req["items"]:
                sno += 1
                desc = escape(item.description)
                hsn = escape(item.hsn_sac) if item.hsn_sac else "—"
                hours = f"{float(item.hours):.1f}" if item.hours else "—"
                rows_html.append(
                    f'<tr><td style="color:#64748B;">{sno}</td>'
                    f'<td>{desc}</td>'
                    f'<td style="font-size:11px;color:#64748B;">{hsn}</td>'
                    f'<td class="text-center">{hours}</td>'
                    f'<td class="text-right">{_inr(float(item.amount))}</td></tr>'
                )
        rows_html.append(
            f'<tr><td colspan="4" class="text-right" style="font-weight:700;color:#64748B;'
            f'text-transform:uppercase;font-size:10px;">Phase Total</td>'
            f'<td class="text-right" style="font-weight:700;color:#0F172A;">{_inr(group["total"])}</td></tr>'
        )

    # ── Bank details + UPI QR — only shown if the invoice actually has them ──
    qr_data_uri = _upi_qr_data_uri(
        profile.get("upi_id", ""), profile.get("name", ""), invoice.total_payable, invoice.invoice_number
    )
    qr_html = f'<img src="{qr_data_uri}" alt="UPI QR" style="width:88px;height:88px;margin-left:16px;" />' if qr_data_uri else ""

    if invoice.bank_name or invoice.bank_account_number or invoice.bank_ifsc or qr_data_uri:
        bank_box_html = f"""
        <div class="payment-box">
            <table class="layout-table"><tr>
                <td>
                    <h4>Bank Payment Details</h4>
                    {_meta_table([
                        ("Bank:", invoice.bank_name or ""),
                        ("A/C No:", invoice.bank_account_number or ""),
                        ("IFSC:", invoice.bank_ifsc or ""),
                    ])}
                </td>
                <td width="1" style="white-space:nowrap;">{qr_html}</td>
            </tr></table>
        </div>"""
    else:
        bank_box_html = "<div></div>"

    # ── Totals ──
    totals_rows = [f'<tr><td>Subtotal</td><td class="text-right">{_inr(float(invoice.subtotal))}</td></tr>']
    if invoice.discount_amount:
        totals_rows.append(
            f'<tr><td>Discount</td><td class="text-right">-{_inr(float(invoice.discount_amount))}</td></tr>'
        )
    for tax in invoice.taxes:
        totals_rows.append(
            f'<tr><td>{escape(tax.tax_type)} ({float(tax.percentage):.0f}%)</td>'
            f'<td class="text-right">{_inr(float(tax.amount))}</td></tr>'
        )
    totals_rows.append(
        f'<tr style="border-top:1px solid #E2E8F0;"><td style="padding-top:8px;">Gross</td>'
        f'<td class="text-right" style="padding-top:8px;">{_inr(float(invoice.gross_amount))}</td></tr>'
    )
    if invoice.tds:
        totals_rows.append(
            f'<tr style="color:#DC2626;"><td>TDS ({float(invoice.tds.tds_percentage):.0f}%)</td>'
            f'<td class="text-right">-{_inr(float(invoice.tds.tds_amount))}</td></tr>'
        )
    totals_rows.append(
        f'<tr class="grand-total"><td>Total Payable (INR)</td>'
        f'<td class="text-right">{_inr(float(invoice.total_payable))}</td></tr>'
    )
    if invoice.amount_paid > 0:
        totals_rows.append(
            f'<tr style="color:#059669;"><td>Paid</td>'
            f'<td class="text-right">-{_inr(float(invoice.amount_paid))}</td></tr>'
        )
        if invoice.payment_status != "PAID":
            totals_rows.append(
                f'<tr class="grand-total"><td>Balance Due</td>'
                f'<td class="text-right">{_inr(float(invoice.balance_due))}</td></tr>'
            )

    # ── Payment history ──
    successful_payments = [p for p in invoice.payments if p.status == "SUCCESS"]
    payment_history_html = ""
    if successful_payments:
        payment_rows = "".join(
            f'<tr><td>{escape(p.payment_reference or "—")}</td>'
            f'<td>{(p.payment_date or p.received_at).strftime("%b %d, %Y")}</td>'
            f'<td>{escape((p.payment_method or "—").replace("_", " ").title())}</td>'
            f'<td>{escape(p.transaction_reference or "—")}</td>'
            f'<td class="text-right">{_inr(float(p.amount))}</td></tr>'
            for p in successful_payments
        )
        payment_history_html = f"""
        <section style="margin-top: 20px;">
            <div class="section-label">Payment History</div>
            <table class="items-table">
                <thead>
                    <tr>
                        <th>Voucher</th><th>Date</th><th>Method</th><th>Reference</th>
                        <th class="text-right">Amount</th>
                    </tr>
                </thead>
                <tbody>{payment_rows}</tbody>
            </table>
        </section>"""

    # ── Terms ──
    terms_html = ""
    invoice_terms = invoice.invoice_terms or profile.get("invoice_terms", "")
    if invoice_terms.strip():
        terms_items = "".join(f"<li>{escape(line.strip())}</li>" for line in invoice_terms.split("\n") if line.strip())
        terms_html = f"""
        <div style="margin-top: 24px;">
            <div class="section-label">Terms &amp; Conditions</div>
            <ol class="terms-list">{terms_items}</ol>
        </div>"""

    legal_bits = []
    if profile.get("gstin"):
        legal_bits.append(f"<strong>GSTIN:</strong> {escape(profile['gstin'])}")
    if profile.get("registration_number"):
        legal_bits.append(f"<strong>Reg. No:</strong> {escape(profile['registration_number'])}")
    legal_line = " | ".join(legal_bits)
    legal_footer_html = ""
    if legal_line:
        legal_footer_html = f'<div class="company-legal-footer">{escape(profile.get("name", ""))} | {legal_line}</div>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Tax Invoice {escape(invoice.invoice_number or "Draft")}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Google+Sans+Flex:opsz,wght@6..144,1..1000&family=Google+Sans:ital,opsz,wght@0,17..18,400..700;1,17..18,400..700&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="invoice-card">
    <header class="header-table">
        <table class="layout-table"><tr>
            <td width="60%">
                <div class="logo-container">
                    {logo_html}
                    <div class="brand-name">{escape(profile.get('name', '').upper())}</div>
                </div>
                {tagline_html}
                <div class="company-address">
                    {escape(profile.get('address', ''))}<br>
                    {escape(profile.get('phone', ''))} | {escape(profile.get('email', ''))}
                </div>
            </td>
            <td class="invoice-title-block" width="40%">
                <div class="invoice-title">Tax Invoice</div>
                <div class="badge" style="background:{badge_bg};color:{badge_fg};">{escape(status_label)}</div>
                <div style="margin-top: 12px; font-size: 12px; font-weight: 600; color: #0F172A;">{escape(invoice.invoice_number or 'DRAFT')}</div>
            </td>
        </tr></table>
    </header>

    <section class="no-break" style="margin: 28px 0;">
        <table class="layout-table"><tr>
            <td width="55%" style="padding-right: 16px;">
                <div class="section-label">Billed To</div>
                <div class="client-name">{escape(invoice.client_name or 'N/A')}</div>
                {client_meta_html}
            </td>
            <td width="45%">
                <div class="section-label">Invoice Details</div>
                {invoice_meta_html}
            </td>
        </tr></table>
    </section>

    <section>
        <table class="items-table">
            <thead>
                <tr>
                    <th width="4%">#</th>
                    <th width="42%">Milestone Details</th>
                    <th width="14%">HSN/SAC</th>
                    <th class="text-center" width="15%">Hours</th>
                    <th class="text-right" width="25%">Amount Due</th>
                </tr>
            </thead>
            <tbody>{''.join(rows_html)}
            </tbody>
        </table>
    </section>

    <section class="no-break" style="margin-top: 20px;">
        <table class="layout-table"><tr>
            <td width="55%" style="padding-right: 16px;">{bank_box_html}</td>
            <td width="45%">
                <table class="totals-table">{''.join(totals_rows)}</table>
            </td>
        </tr></table>
    </section>

    <section class="no-break" style="margin-top: 16px;">
        <div class="section-label">Amount in Words</div>
        <div style="font-size: 12px; color: #334155;">{escape(amount_in_words(invoice.total_payable))}</div>
    </section>

    {payment_history_html}

    <footer class="footer-section no-break">
        <table class="layout-table"><tr>
            <td width="60%"></td>
            <td width="40%">
                <div class="signature-box">
                    <div class="signature-space">{signature_img_html}{seal_img_html}</div>
                    <div class="signature-title">For {escape(profile.get('name', '').upper())}<br><small>({escape(profile.get('signatory_title', 'Authorized Signatory'))})</small></div>
                </div>
            </td>
        </tr></table>
        {terms_html}
        {legal_footer_html}
    </footer>
</div>
</body>
</html>"""

    from app.utils import pdf_builder
    return pdf_builder.html_to_pdf(html)
