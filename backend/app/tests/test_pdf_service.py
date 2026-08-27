"""
Unit tests for app/services/pdf_service.py:
  - amount_in_words() Indian-numbering conversion
  - _group_items() milestone/component/requirement grouping (mirrors the
    on-screen grouping in frontend/src/pages/InvoiceViewV2.tsx)
  - HTML/XSS escaping: every DB-sourced string must be escape()'d before
    landing in the HTML that gets rendered to PDF. generate_invoice_pdf()
    doesn't return the intermediate HTML, so these tests monkeypatch
    app.utils.pdf_builder.html_to_pdf to intercept it instead of rendering
    a real PDF.
"""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.pdf_service import amount_in_words, _group_items, generate_invoice_pdf


# ── amount_in_words ─────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "amount,expected",
    [
        (0, "Rupees Zero Only"),
        (1, "Rupees One Only"),
        (100, "Rupees One Hundred Only"),
        (1000, "Rupees One Thousand Only"),
        (100000, "Rupees One Lakh Only"),
        (10000000, "Rupees One Crore Only"),
        (5900.00, "Rupees Five Thousand Nine Hundred Only"),
    ],
)
def test_amount_in_words_whole_numbers(amount, expected):
    assert amount_in_words(amount) == expected


def test_amount_in_words_with_paise():
    assert amount_in_words(4543073.16) == "Rupees Forty Five Lakh Forty Three Thousand Seventy Three and Sixteen Paise Only"


def test_amount_in_words_accepts_decimal():
    assert amount_in_words(Decimal("100.00")) == "Rupees One Hundred Only"


# ── _group_items ─────────────────────────────────────────────────────────────

def _item(description, amount, milestone_id=None, milestone_name=None,
          component_id=None, requirement_name=None, hsn_sac=None, hours=None):
    return SimpleNamespace(
        description=description, amount=amount, milestone_id=milestone_id,
        milestone_name=milestone_name, component_id=component_id,
        requirement_name=requirement_name, hsn_sac=hsn_sac, hours=hours,
    )


def test_group_items_groups_by_milestone():
    items = [
        _item("Task A", 100, milestone_id="m1", milestone_name="Phase 1"),
        _item("Task B", 200, milestone_id="m1", milestone_name="Phase 1"),
        _item("Task C", 300, milestone_id="m2", milestone_name="Phase 2"),
    ]
    groups = _group_items(items)
    assert len(groups) == 2
    phase1 = next(g for g in groups if g["name"] == "Phase 1")
    assert phase1["item_count"] == 2
    assert phase1["total"] == 300


def test_group_items_component_vs_custom():
    items = [
        _item("Infra", 500, component_id="c1"),
        _item("Ad-hoc consulting", 50),
    ]
    groups = _group_items(items)
    names = {g["name"] for g in groups}
    assert "Commercial Components" in names
    assert "Other Items" in names


def test_group_items_requirement_subgrouping():
    items = [
        _item("Sub-task 1", 10, milestone_id="m1", milestone_name="Phase 1", requirement_name="Auth"),
        _item("Sub-task 2", 20, milestone_id="m1", milestone_name="Phase 1", requirement_name="Auth"),
        _item("Sub-task 3", 30, milestone_id="m1", milestone_name="Phase 1", requirement_name="Billing"),
    ]
    groups = _group_items(items)
    assert len(groups) == 1
    reqs = groups[0]["requirements"]
    assert set(reqs.keys()) == {"Auth", "Billing"}
    assert reqs["Auth"]["total"] == 30
    assert reqs["Billing"]["total"] == 30


def test_group_items_empty_list():
    assert _group_items([]) == []


# ── XSS / HTML-escaping ──────────────────────────────────────────────────────

class _FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter_by(self, **kwargs):
        return self

    def first(self):
        return self._result


class _FakeSession:
    def __init__(self, invoice):
        self._invoice = invoice

    def query(self, model):
        return _FakeQuery(self._invoice)


def _malicious_invoice():
    """An Invoice-shaped object with an XSS payload in every user/DB-sourced
    string field the PDF template interpolates."""
    payload = '<script>alert(1)</script>"><img src=x onerror=alert(2)>'
    tax = SimpleNamespace(tax_type=payload, percentage=Decimal("18"), amount=Decimal("18.00"))
    return SimpleNamespace(
        id="inv-1",
        invoice_number=payload,
        invoice_type="STANDALONE",
        project_id=None,
        project_name=payload,
        project_number=payload,
        project_start_date=None,
        project_end_date=None,
        status="DRAFT",
        payment_status="UNPAID",
        client_name=payload,
        client_address=payload,
        client_gstin=payload,
        client_email=payload,
        client_phone=payload,
        invoice_date=None,
        due_date=None,
        payment_terms=payload,
        po_number=payload,
        items=[_item(payload, Decimal("100.00"), requirement_name=payload)],
        bank_name=payload,
        bank_account_number=payload,
        bank_ifsc=payload,
        subtotal=Decimal("100.00"),
        discount_amount=Decimal("0"),
        taxes=[tax],
        gross_amount=Decimal("118.00"),
        tds=None,
        total_payable=Decimal("118.00"),
        amount_paid=Decimal("0"),
        balance_due=Decimal("118.00"),
        payments=[],
        invoice_terms=payload,
    )


@patch("app.utils.organization.load_profile")
@patch("app.utils.organization.branding_url", return_value=None)
def test_generate_invoice_pdf_escapes_all_user_content(mock_branding, mock_profile):
    mock_profile.return_value = {
        "name": "Test Org", "address": "", "phone": "", "email": "",
        "gstin": "", "upi_id": "", "invoice_terms": "",
    }
    invoice = _malicious_invoice()
    session = _FakeSession(invoice)

    captured = {}

    def fake_html_to_pdf(html):
        captured["html"] = html
        return b"%PDF-fake%"

    with patch("app.utils.pdf_builder.html_to_pdf", side_effect=fake_html_to_pdf):
        result = generate_invoice_pdf(session, "inv-1")

    assert result == b"%PDF-fake%"
    html = captured["html"]
    # The raw, unescaped payload must never appear in the generated HTML —
    # if it does, the browser would execute it as a live <script>/<img onerror>
    # instead of rendering it as literal invoice text.
    assert "<script>alert(1)</script>" not in html
    assert "<img src=x onerror=alert(2)>" not in html
    # And the escaped form should be present (proving the content made it
    # through rather than being silently dropped).
    assert "&lt;script&gt;" in html


def test_generate_invoice_pdf_raises_for_unknown_invoice():
    session = _FakeSession(None)
    with pytest.raises(ValueError):
        generate_invoice_pdf(session, "does-not-exist")
