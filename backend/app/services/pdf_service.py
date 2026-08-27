"""
V2 invoice PDF renderer.

Builds a professional, self-contained HTML tax invoice from the invoice's
own persisted DB snapshot (client, project, bank and line-item fields already
frozen on the Invoice/InvoiceItem rows at creation time — see
app/services/invoice_service.py) and renders it to PDF via
app.utils.pdf_builder.html_to_pdf.

The markup/CSS here is a deliberate 1:1 port of the on-screen invoice view
(frontend/src/pages/InvoiceViewV2.tsx) — same seller block, header block,
amber "Billed To" card, dark items-table header, financials grid, and
signature footer — translated from Tailwind utility classes to plain CSS
since the PDF renderer has no Tailwind pipeline. Keep the two in sync: a
layout change on one side without the other reintroduces the on-screen vs.
downloaded-PDF mismatch this was written to fix.

Seller identity (company name, address, GSTIN, logo, signatory) has no
snapshot field on the V2 Invoice model yet, so it's read live from the
shared organization profile (app.utils.organization) — the same source the
on-screen view reads via GET /api/organization.
"""

from __future__ import annotations

import base64
import io
from html import escape
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.utils.organization import load_profile, branding_url


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


def _inr(n: float) -> str:
    """Matches the web view's formatMoney(): ₹ + Indian-grouped 2-decimal amount."""
    return f"₹{n:,.2f}"


def _group_items(items: list) -> list[dict]:
    """Group line items by milestone/component, then by requirement — mirrors
    the on-screen grouping in frontend/src/pages/InvoiceViewV2.tsx so the PDF
    and the web view present the same structure."""
    groups: dict[str, dict] = {}
    for item in items:
        group_id = item.milestone_id or (f"comp_{item.component_id}" if item.component_id else "other")
        group_name = item.milestone_name or ("Commercial Components" if item.component_id else "Other Items")
        group = groups.setdefault(group_id, {"name": group_name, "requirements": {}, "total": 0.0, "item_count": 0})

        req_name = item.requirement_name or "General"
        req = group["requirements"].setdefault(req_name, {"name": req_name, "items": [], "total": 0.0})
        req["items"].append(item)
        req["total"] += float(item.amount)
        group["total"] += float(item.amount)
        group["item_count"] += 1

    return list(groups.values())


# Mirrors the badge color maps in InvoiceViewV2.tsx's headerBlock exactly —
# two independent badges (document status, payment status), not the single
# conflated "Draft/Sent/Paid/..." label the old renderer used.
_STATUS_BADGE = {
    "ISSUED": ("#DBEAFE", "#1E40AF"),
    "CANCELLED": ("#FFE4E1", "#BE123C"),
    "DRAFT": ("#E2E8F0", "#334155"),
}
_PAYMENT_BADGE = {
    "PAID": ("#D1FAE5", "#065F46"),
    "PARTIALLY_PAID": ("#FEF3C7", "#92400E"),
    "UNPAID": ("#E2E8F0", "#334155"),
    "INITIATED": ("#E2E8F0", "#334155"),
}

CSS = """
/* Page numbering is provided by the renderer's own footer_template
   (see app/utils/pdf_builder.py's _html_to_pdf_playwright) — an @page
   @bottom-center rule here would render a second, overlapping "Page X of Y". */
@page {
    size: A4;
    margin: 15mm;
}
* { box-sizing: border-box; }
body {
    font-family: 'Google Sans', Helvetica, Arial, sans-serif;
    font-size: 10.5pt;
    color: #1e293b;
    line-height: 1.45;
    margin: 0;
}
.text-right { text-align: right; }
.text-center { text-align: center; }
/* NOTE: layout below is deliberately table-based, not flexbox/grid — the
   Chromium print pipeline in pdf_builder.html_to_pdf doesn't reliably
   stretch a `display:flex` block to its parent's width during pagination
   (a flex container with width:auto sizes to fit-content instead), which
   silently clips content past the page's right margin. Tables (including
   `display:table`/`table-cell` for simple label/value rows) don't have
   that problem, so every multi-column block here uses one. */
.layout-table { width: 100%; border-collapse: collapse; }
.layout-table > tbody > tr > td { vertical-align: top; padding: 0; }

/* ── Seller block ── */
.seller-block { margin-bottom: 14pt; padding-bottom: 14pt; border-bottom: 1px solid #F1F5F9; }
.brand-logo { height: 30pt; width: auto; object-fit: contain; vertical-align: top; margin-right: 10pt; }
.brand-name { font-size: 13pt; font-weight: 900; color: #0F172A; letter-spacing: -0.2px; }
.brand-tagline { font-size: 8pt; font-weight: 700; color: #2563EB; text-transform: uppercase; letter-spacing: 0.4px; margin-top: 1pt; }
.seller-address { font-size: 8.5pt; color: #64748B; margin-top: 3pt; max-width: 300pt; }
.seller-gstin { font-size: 8.5pt; color: #64748B; text-align: right; white-space: nowrap; padding-left: 18pt; }
.seller-gstin strong { color: #334155; font-weight: 600; }

/* ── Header block (project/client name + invoice meta) ── */
.header-block { margin-bottom: 18pt; padding-bottom: 12pt; border-bottom: 2px solid #0F172A; }
.header-title { font-size: 15pt; font-weight: 700; color: #0F172A; letter-spacing: -0.2px; line-height: 1.25; }
.header-subline { font-size: 8.5pt; color: #64748B; margin-top: 3pt; }
.header-subline span + span { margin-left: 10pt; }
.header-subline strong { color: #334155; font-weight: 600; }
.standalone-badge { display: inline-block; padding: 1pt 6pt; border-radius: 8pt; background: #F1F5F9; color: #475569; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px; font-size: 6.5pt; margin-left: 10pt; }
.header-right { text-align: right; white-space: nowrap; padding-left: 18pt; }
.invoice-caption { margin-bottom: 4pt; }
.invoice-caption h1 { display: inline-block; vertical-align: middle; font-size: 15pt; font-weight: 900; color: #0F172A; letter-spacing: -0.2px; margin: 0 5pt 0 0; }
.badge { display: inline-block; vertical-align: middle; padding: 1.5pt 6pt; border-radius: 8pt; font-size: 6.5pt; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px; margin-left: 4pt; }
.invoice-meta { font-size: 9pt; }
.invoice-meta div { margin-top: 1.5pt; }
.invoice-meta .label { color: #64748B; }
.invoice-meta .value { color: #1E293B; font-weight: 600; }
.invoice-meta .no-label { color: #0F172A; font-weight: 700; }

/* ── Billed To (amber card) ── */
.bill-to-card { background: #FFFBEB; border: 1px solid #FEF3C7; border-radius: 6pt; padding: 10pt 12pt; max-width: 260pt; margin-bottom: 18pt; }
.bill-to-title { font-size: 8pt; font-weight: 700; color: #92400E; text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 6pt 0; border-bottom: 1px solid #FDE68A; padding-bottom: 5pt; }
.bill-to-name { font-size: 10pt; font-weight: 700; color: #0F172A; margin: 0; }
.bill-to-address { font-size: 9pt; color: #475569; margin-top: 3pt; white-space: pre-line; }
.bill-to-lines { font-size: 9pt; color: #475569; margin-top: 5pt; }
.bill-to-lines div { margin-top: 1.5pt; }
.bill-to-lines strong { color: #334155; font-weight: 600; margin-right: 3pt; }

/* ── Items table ── */
.items-table { width: 100%; border-collapse: collapse; margin-bottom: 18pt; }
.items-table thead tr { background: #0F172A; }
.items-table th { color: #ffffff; font-size: 7.5pt; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px; padding: 6pt 7pt; text-align: left; }
.items-table tbody tr { page-break-inside: avoid; }
.items-table td { padding: 5pt 7pt; font-size: 9pt; color: #1E293B; border-bottom: 1px solid #F1F5F9; }
.items-table .group-row td { background: #F8FAFC; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px; font-size: 8pt; color: #1E293B; border-top: 1px solid #E2E8F0; border-bottom: 1px solid #E2E8F0; }
.items-table .req-row td { font-size: 7.8pt; font-weight: 700; color: #64748B; padding-left: 18pt; }
.items-table .sno-col { color: #64748B; font-family: monospace; width: 4%; }
.items-table .hsn-col { font-size: 7.8pt; color: #64748B; font-family: monospace; width: 12%; }
.items-table .hours-col { text-align: right; color: #475569; font-family: monospace; width: 12%; }
.items-table .amount-col { text-align: right; font-weight: 500; color: #0F172A; width: 22%; }
.items-table .subtotal-row td { font-size: 7.5pt; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.4px; text-align: right; }
.items-table .subtotal-row .amount-col { color: #0F172A; background: #F8FAFC; }

/* ── Trailing: payment info + financials ── */
.trailing-grid td.col-left { width: 58%; padding-right: 14pt; }
.trailing-grid td.col-right { width: 42%; }
.payment-box { background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6pt; padding: 10pt 12pt; }
.payment-box h4 { font-size: 8pt; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 6pt 0; border-bottom: 1px solid #E2E8F0; padding-bottom: 5pt; }
.payment-box .pb-row { margin-top: 5pt; }
.payment-box .pb-label { font-size: 7.5pt; color: #64748B; }
.payment-box .pb-value { font-size: 9pt; font-weight: 600; color: #0F172A; font-family: monospace; }
.qr-cell { text-align: right; }
.qr-cell img { width: 62pt; height: 62pt; }

/* Label/value rows use display:table + table-cell (not flex — see note
   above) so the row reliably fills its container width. */
.lv-row { display: table; width: 100%; table-layout: fixed; margin-top: 3pt; }
.lv-row > span { display: table-cell; }
.lv-row > span.val { text-align: right; }

.totals-list { font-size: 9pt; color: #475569; border-bottom: 1px solid #E2E8F0; padding-bottom: 5pt; margin-bottom: 5pt; }
.totals-list .lv-row .val { font-weight: 600; color: #0F172A; }
.totals-list .t-total { padding-top: 4pt; margin-top: 4pt; border-top: 1px solid #F1F5F9; font-weight: 600; color: #0F172A; }
.totals-list .t-tds { color: #E11D48; }
.total-payable-box { background: #0F172A; color: #ffffff; border-radius: 6pt; padding: 7pt; text-align: center; }
.total-payable-box .tp-label { display: block; font-size: 7pt; font-weight: 600; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 1pt; }
.total-payable-box .tp-value { display: block; font-size: 13pt; font-weight: 900; letter-spacing: -0.2px; }
.paid-line { font-size: 9pt; margin-top: 5pt; padding: 0 2pt; }
.paid-line .paid-val { font-weight: 600; color: #059669; }
.balance-line { font-size: 9pt; padding: 0 2pt; }
.balance-line .bal-val { font-weight: 700; color: #0F172A; }

/* ── Amount in words ── */
.amount-words { margin-bottom: 16pt; font-size: 9pt; }
.amount-words .label { font-size: 7.5pt; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.5px; margin-right: 5pt; }
.amount-words .value { color: #334155; font-style: italic; }

/* ── Payment history ── */
.payment-history { margin-bottom: 16pt; }
.payment-history h4 { font-size: 8pt; font-weight: 700; color: #1E293B; text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 6pt 0; }
.payment-history table { width: 100%; border-collapse: collapse; font-size: 8.5pt; }
.payment-history th { font-size: 7pt; font-weight: 600; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.4px; text-align: left; padding: 4pt 0; border-bottom: 1px solid #E2E8F0; }
.payment-history td { padding: 4pt 0; border-bottom: 1px solid #F1F5F9; color: #334155; }
.payment-history .ph-ref { font-family: monospace; font-size: 7.5pt; color: #475569; }
.payment-history .ph-amt { text-align: right; font-weight: 600; color: #0F172A; }

/* ── Footer: notes/terms + signature ── */
.footer-grid { padding-top: 12pt; border-top: 1px solid #E2E8F0; }
.footer-grid td.footer-notes-cell { width: 66%; padding-right: 16pt; }
.footer-grid td.footer-sign-cell { width: 34%; }
.footer-notes { font-size: 7.8pt; color: #64748B; line-height: 1.5; }
.footer-notes h4 { font-size: 7.8pt; font-weight: 700; color: #1E293B; text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 4pt 0; }
.footer-notes p { margin: 0; white-space: pre-line; }
.footer-sign { text-align: center; }
.footer-sign .thanks { font-size: 9pt; font-weight: 600; color: #1E293B; margin-bottom: 2pt; }
.footer-sign .for-company { font-size: 8pt; color: #64748B; margin-bottom: 26pt; }
.footer-sign .sign-space img { max-height: 34pt; margin-bottom: 2pt; }
.footer-sign .sign-line { border-top: 1px solid #CBD5E1; width: 75%; margin: 0 auto; padding-top: 4pt; }
.footer-sign .sign-line p { font-size: 7.5pt; font-weight: 700; color: #0F172A; text-transform: uppercase; letter-spacing: 0.4px; margin: 0; }

.no-break { page-break-inside: avoid; }
"""


def generate_invoice_pdf(session: Session, invoice_id: str) -> bytes:
    invoice = session.query(Invoice).filter_by(id=invoice_id).first()
    if not invoice:
        raise ValueError("Invoice not found")

    profile = load_profile()
    logo_url = branding_url(profile, "logo")
    signature_url = branding_url(profile, "signature")
    seal_url = branding_url(profile, "seal")
    org_name = profile.get("name", "")

    is_standalone = invoice.invoice_type == "STANDALONE" or not invoice.project_id

    # ── Seller block ──
    logo_html = (
        f'<img src="{logo_url}" alt="{escape(org_name or "Logo")}" class="brand-logo" onerror="this.style.display=\'none\';" />'
        if logo_url else ""
    )
    tagline_html = f'<div class="brand-tagline">{escape(profile["tagline"])}</div>' if profile.get("tagline") else ""
    address_line2 = " | ".join(x for x in [profile.get("phone", ""), profile.get("email", "")] if x)
    seller_html = f"""
    <table class="layout-table seller-block"><tr>
        <td>
            {logo_html}<span style="display:inline-block;vertical-align:top;">
                <div class="brand-name">{escape(org_name.upper())}</div>
                {tagline_html}
                <div class="seller-address">{escape(profile.get('address', ''))}{f'<br>{escape(address_line2)}' if address_line2 else ''}</div>
            </span>
        </td>
        <td style="width:1%;">{f'<div class="seller-gstin">GSTIN: <strong>{escape(profile["gstin"])}</strong></div>' if profile.get('gstin') else ''}</td>
    </tr></table>"""

    # ── Header block (title + invoice meta), mirrors headerBlock in InvoiceViewV2.tsx ──
    subline_bits = []
    if invoice.project_number:
        subline_bits.append(f'<span>Project ID: <strong>{escape(invoice.project_number)}</strong></span>')
    if invoice.project_start_date:
        subline_bits.append(f'<span>Start: <strong>{invoice.project_start_date.strftime("%d/%m/%Y")}</strong></span>')
    if invoice.project_end_date:
        subline_bits.append(f'<span>End: <strong>{invoice.project_end_date.strftime("%d/%m/%Y")}</strong></span>')
    standalone_html = '<span class="standalone-badge">Standalone</span>' if is_standalone else ''

    status_bg, status_fg = _STATUS_BADGE.get(invoice.status, _STATUS_BADGE["DRAFT"])
    payment_badge_html = ""
    if invoice.status != "DRAFT":
        pay_bg, pay_fg = _PAYMENT_BADGE.get(invoice.payment_status, _PAYMENT_BADGE["UNPAID"])
        pay_label = "Partially Paid" if invoice.payment_status == "PARTIALLY_PAID" else invoice.payment_status.title()
        payment_badge_html = f'<span class="badge" style="background:{pay_bg};color:{pay_fg};">{escape(pay_label)}</span>'

    meta_lines = [f'<div><span class="label">No.</span> <span class="no-label">{escape(invoice.invoice_number or "DRAFT")}</span></div>']
    if invoice.invoice_date:
        meta_lines.append(f'<div><span class="label">Date:</span> <span class="value">{invoice.invoice_date.strftime("%d/%m/%Y")}</span></div>')
    if invoice.due_date:
        meta_lines.append(f'<div><span class="label">Due:</span> <span class="value">{invoice.due_date.strftime("%d/%m/%Y")}</span></div>')
    if invoice.payment_terms:
        meta_lines.append(f'<div><span class="label">Terms:</span> <span class="value">{escape(invoice.payment_terms)}</span></div>')
    if invoice.po_number:
        meta_lines.append(f'<div><span class="label">PO No.:</span> <span class="value">{escape(invoice.po_number)}</span></div>')

    header_html = f"""
    <table class="layout-table header-block"><tr>
        <td>
            <div class="header-title">{escape(invoice.project_name or invoice.client_name or '')}</div>
            <div class="header-subline">{''.join(subline_bits)}{standalone_html}</div>
        </td>
        <td style="width:1%;">
            <div class="header-right">
                <div class="invoice-caption">
                    <h1>INVOICE</h1>
                    <span class="badge" style="background:{status_bg};color:{status_fg};">{escape(invoice.status)}</span>
                    {payment_badge_html}
                </div>
                <div class="invoice-meta">{''.join(meta_lines)}</div>
            </div>
        </td>
    </tr></table>"""

    # ── Billed-to (amber card) — from the invoice's own client snapshot, never the live client record ──
    bill_to_lines = []
    if invoice.client_email:
        bill_to_lines.append(f'<div><strong>Email:</strong>{escape(invoice.client_email)}</div>')
    if invoice.client_phone:
        bill_to_lines.append(f'<div><strong>Phone:</strong>{escape(invoice.client_phone)}</div>')
    if invoice.client_gstin:
        bill_to_lines.append(f'<div><strong>GSTIN:</strong>{escape(invoice.client_gstin)}</div>')

    bill_to_html = f"""
    <div class="bill-to-card no-break">
        <div class="bill-to-title">Billed To</div>
        <div class="bill-to-name">{escape(invoice.client_name or 'N/A')}</div>
        {f'<div class="bill-to-address">{escape(invoice.client_address)}</div>' if invoice.client_address else ''}
        <div class="bill-to-lines">{''.join(bill_to_lines)}</div>
    </div>"""

    # ── Line items — grouped like the on-screen view, HSN/SAC shown per item ──
    rows_html = []
    sno = 0
    for group in _group_items(invoice.items):
        rows_html.append(f'<tr class="group-row"><td colspan="5">{escape(group["name"])}</td></tr>')
        for req in group["requirements"].values():
            if req["name"] != "General":
                rows_html.append(f'<tr class="req-row"><td colspan="5">{escape(req["name"])}</td></tr>')
            for item in req["items"]:
                sno += 1
                desc = escape(item.description)
                hsn = escape(item.hsn_sac) if item.hsn_sac else "—"
                hours = f"{float(item.hours):.1f}" if item.hours else "—"
                rows_html.append(
                    f'<tr><td class="sno-col">{sno}</td>'
                    f'<td>{desc}</td>'
                    f'<td class="hsn-col">{hsn}</td>'
                    f'<td class="hours-col">{hours}</td>'
                    f'<td class="amount-col">{_inr(float(item.amount))}</td></tr>'
                )
        if group["item_count"] > 1:
            rows_html.append(
                f'<tr class="subtotal-row"><td colspan="4">Group Subtotal</td>'
                f'<td class="amount-col">{_inr(group["total"])}</td></tr>'
            )

    # ── Bank details + UPI QR — only shown if the invoice actually has them ──
    qr_data_uri = _upi_qr_data_uri(
        profile.get("upi_id", ""), profile.get("name", ""), invoice.total_payable, invoice.invoice_number
    )
    qr_html = f'<img src="{qr_data_uri}" alt="UPI QR" />' if qr_data_uri else ""
    has_bank_info = bool(invoice.bank_name or invoice.bank_account_number or invoice.bank_ifsc)

    payment_box_html = ""
    if has_bank_info:
        bank_rows = []
        if invoice.bank_name:
            bank_rows.append(f'<div class="pb-row"><div class="pb-label">Bank Name</div><div class="pb-value">{escape(invoice.bank_name)}</div></div>')
        if invoice.bank_account_number:
            bank_rows.append(f'<div class="pb-row"><div class="pb-label">Account Number</div><div class="pb-value">{escape(invoice.bank_account_number)}</div></div>')
        if invoice.bank_ifsc:
            bank_rows.append(f'<div class="pb-row"><div class="pb-label">Routing / IFSC</div><div class="pb-value">{escape(invoice.bank_ifsc)}</div></div>')
        payment_box_html = f"""
        <div class="payment-box">
            <table style="width:100%;"><tr>
                <td><h4>Payment Information</h4>{''.join(bank_rows)}</td>
                {f'<td class="qr-cell" width="1">{qr_html}</td>' if qr_html else ''}
            </tr></table>
        </div>"""

    # ── Totals ──
    totals_rows = [f'<div class="lv-row"><span>Subtotal</span><span class="val">{_inr(float(invoice.subtotal))}</span></div>']
    if invoice.discount_amount:
        totals_rows.append(f'<div class="lv-row"><span>Discount</span><span class="val">- {_inr(float(invoice.discount_amount))}</span></div>')
    for tax in invoice.taxes:
        totals_rows.append(
            f'<div class="lv-row"><span>{escape(tax.tax_type)} ({float(tax.percentage):.0f}%)</span>'
            f'<span class="val">{_inr(float(tax.amount))}</span></div>'
        )
    totals_html = f'<div class="totals-list">{"".join(totals_rows)}'
    totals_html += f'<div class="lv-row t-total"><span>Total</span><span class="val">{_inr(float(invoice.gross_amount))}</span></div>'
    if invoice.tds:
        totals_html += (
            f'<div class="lv-row t-tds"><span>TDS ({float(invoice.tds.tds_percentage):.0f}%)</span>'
            f'<span class="val" style="color:#E11D48;">- {_inr(float(invoice.tds.tds_amount))}</span></div>'
        )
    totals_html += "</div>"

    trailing_extra = ""
    if invoice.amount_paid > 0:
        trailing_extra += f'<div class="lv-row paid-line"><span>Paid</span><span class="val paid-val">{_inr(float(invoice.amount_paid))}</span></div>'
        if invoice.payment_status != "PAID":
            trailing_extra += f'<div class="lv-row balance-line"><span>Balance Due</span><span class="val bal-val">{_inr(float(invoice.balance_due))}</span></div>'

    trailing_html = f"""
    <table class="layout-table trailing-grid no-break"><tr>
        <td class="col-left">{payment_box_html}</td>
        <td class="col-right">
            {totals_html}
            <div class="total-payable-box">
                <span class="tp-label">Total Payable</span>
                <span class="tp-value">{_inr(float(invoice.total_payable))}</span>
            </div>
            {trailing_extra}
        </td>
    </tr></table>"""

    # ── Amount in words ──
    amount_words_html = f"""
    <div class="amount-words">
        <span class="label">Amount in Words:</span>
        <span class="value">{escape(amount_in_words(invoice.total_payable))}</span>
    </div>"""

    # ── Payment history ──
    successful_payments = [p for p in invoice.payments if p.status == "SUCCESS"]
    payment_history_html = ""
    if successful_payments:
        payment_rows = "".join(
            f'<tr><td class="ph-ref">{escape(p.payment_reference or "—")}</td>'
            f'<td>{(p.payment_date or p.received_at).strftime("%d/%m/%Y")}</td>'
            f'<td>{escape((p.payment_method or "—").replace("_", " ").title())}</td>'
            f'<td class="ph-ref">{escape(p.transaction_reference or "—")}</td>'
            f'<td class="ph-amt">{_inr(float(p.amount))}</td></tr>'
            for p in successful_payments
        )
        payment_history_html = f"""
        <div class="payment-history no-break">
            <h4>Payment History</h4>
            <table>
                <thead><tr><th>Voucher</th><th>Date</th><th>Method</th><th>Reference</th><th class="text-right">Amount</th></tr></thead>
                <tbody>{payment_rows}</tbody>
            </table>
        </div>"""

    # ── Footer: notes/terms + signature, mirrors footerContent in InvoiceViewV2.tsx ──
    invoice_terms = invoice.invoice_terms or profile.get("invoice_terms", "")
    if invoice_terms.strip():
        terms_body_html = f'<p>{escape(invoice_terms)}</p>'
    else:
        terms_body_html = (
            "<p>Payment is due within the stipulated timeframe. Late payments may incur interest "
            "charges. Please include the invoice number as the payment reference.</p>"
        )

    signature_img_html = f'<img src="{signature_url}" alt="Signature" />' if signature_url else ""
    seal_img_html = f'<img src="{seal_url}" alt="Seal" />' if seal_url else ""

    footer_html = f"""
    <table class="layout-table footer-grid no-break"><tr>
        <td class="footer-notes-cell">
            <div class="footer-notes">
                <h4>Notes &amp; Terms</h4>
                {terms_body_html}
            </div>
        </td>
        <td class="footer-sign-cell">
            <div class="footer-sign">
                <div class="thanks">Thank you for your business!</div>
                {f'<div class="for-company">For {escape(org_name)}</div>' if org_name else ''}
                <div class="sign-space">{signature_img_html}{seal_img_html}</div>
                <div class="sign-line"><p>Authorized Signatory</p></div>
            </div>
        </td>
    </tr></table>"""

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
{seller_html}
{header_html}
{bill_to_html}
<table class="items-table">
    <thead>
        <tr>
            <th style="width:4%;">#</th>
            <th style="width:42%;">Description</th>
            <th style="width:14%;">HSN/SAC</th>
            <th class="text-right" style="width:15%;">Hours</th>
            <th class="text-right" style="width:25%;">Taxable Amount</th>
        </tr>
    </thead>
    <tbody>{''.join(rows_html)}</tbody>
</table>
{trailing_html}
{amount_words_html}
{payment_history_html}
{footer_html}
</body>
</html>"""

    from app.utils import pdf_builder
    return pdf_builder.html_to_pdf(html)
