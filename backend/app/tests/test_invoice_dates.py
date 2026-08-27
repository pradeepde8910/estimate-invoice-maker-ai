"""
Unit tests for invoice_service._compute_invoice_dates — fixes the bug where
invoice_date/due_date were never populated, leaving downloaded PDFs with a
blank "Invoice Details" section (see app/services/invoice_service.py).
"""

from datetime import datetime

from app.services.invoice_service import _compute_invoice_dates, DEFAULT_DUE_DAYS


def test_invoice_date_is_always_now():
    before = datetime.utcnow()
    invoice_date, _ = _compute_invoice_dates(None)
    after = datetime.utcnow()
    assert before <= invoice_date <= after


def test_net_30_parsed_correctly():
    invoice_date, due_date = _compute_invoice_dates("Net 30")
    assert (due_date - invoice_date).days == 30


def test_net_without_space_and_case_insensitive():
    invoice_date, due_date = _compute_invoice_dates("NET15")
    assert (due_date - invoice_date).days == 15


def test_net_with_dash():
    invoice_date, due_date = _compute_invoice_dates("Net-45")
    assert (due_date - invoice_date).days == 45


def test_none_falls_back_to_default():
    invoice_date, due_date = _compute_invoice_dates(None)
    assert (due_date - invoice_date).days == DEFAULT_DUE_DAYS


def test_empty_string_falls_back_to_default():
    invoice_date, due_date = _compute_invoice_dates("")
    assert (due_date - invoice_date).days == DEFAULT_DUE_DAYS


def test_unrecognized_terms_fall_back_to_default():
    invoice_date, due_date = _compute_invoice_dates("Due on receipt")
    assert (due_date - invoice_date).days == DEFAULT_DUE_DAYS


def test_due_date_is_strictly_after_invoice_date():
    invoice_date, due_date = _compute_invoice_dates("Net 30")
    assert due_date > invoice_date
