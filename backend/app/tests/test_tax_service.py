"""
Unit tests for GST tax calculation and Indian state / GSTIN resolution.
Verifies:
- Intra-state supply (Tamil Nadu -> Tamil Nadu) splits into CGST + SGST
- Inter-state supply (Tamil Nadu -> Karnataka / Delhi / etc.) applies IGST
- GSTIN 2-digit state code resolution (e.g., 33 -> TN, 29 -> KA, 07 -> DL)
- Full address state keyword resolution
"""

from decimal import Decimal
import pytest
from app.services.tax_service import (
    calculate_gst,
    calculate_taxes_by_bucket,
    resolve_state,
    calculate_tds,
)


def test_resolve_state_from_gstin():
    # 33 = Tamil Nadu
    assert resolve_state(gstin="33AAAAA0000A1Z5") == "Tamil Nadu"
    # 29 = Karnataka
    assert resolve_state(gstin="29ABCDE1234F1Z5") == "Karnataka"
    # 07 = Delhi
    assert resolve_state(gstin="07AABCB7821M1Z2") == "Delhi"
    # 27 = Maharashtra
    assert resolve_state(gstin="27AABCB7821M1Z2") == "Maharashtra"


def test_resolve_state_from_address():
    assert resolve_state(address="123 Anna Salai, Chennai, Tamil Nadu - 600002") == "Tamil Nadu"
    assert resolve_state(address="Indiranagar, Bangalore, Karnataka 560038") == "Karnataka"
    assert resolve_state(address="2nd Floor, Sector 62, Noida, Uttar Pradesh") == "Uttar Pradesh"
    assert resolve_state(address="Connaught Place, New Delhi - 110001") == "Delhi"


def test_intra_state_gst_splits_into_cgst_and_sgst():
    # Tamil Nadu to Tamil Nadu, taxable amount = 100,000, GST rate = 18%
    res = calculate_gst(
        seller_state="Tamil Nadu",
        buyer_state="123 Anna Salai, Chennai, Tamil Nadu",
        taxable_amount=Decimal("100000.00"),
        gst_rate=Decimal("18.00")
    )
    assert res.cgst == Decimal("9000.00")
    assert res.sgst == Decimal("9000.00")
    assert res.igst == Decimal("0.00")
    assert res.total_gst == Decimal("18000.00")


def test_inter_state_gst_applies_igst():
    # Tamil Nadu to Karnataka, taxable amount = 100,000, GST rate = 18%
    res = calculate_gst(
        seller_state="Tamil Nadu",
        buyer_state="MG Road, Bangalore, Karnataka",
        taxable_amount=Decimal("100000.00"),
        gst_rate=Decimal("18.00")
    )
    assert res.cgst == Decimal("0.00")
    assert res.sgst == Decimal("0.00")
    assert res.igst == Decimal("18000.00")
    assert res.total_gst == Decimal("18000.00")


def test_calculate_taxes_by_bucket_intra_state():
    items = [
        {"amount": Decimal("50000.00"), "gst_rate": Decimal("18.00")},
        {"amount": Decimal("50000.00"), "gst_rate": Decimal("18.00")},
    ]
    buckets = calculate_taxes_by_bucket(
        seller_state="Tamil Nadu",
        buyer_state="Chennai",
        items=items
    )
    assert len(buckets) == 1
    assert buckets[0].taxable_amount == Decimal("100000.00")
    assert buckets[0].cgst == Decimal("9000.00")
    assert buckets[0].sgst == Decimal("9000.00")
    assert buckets[0].igst == Decimal("0.00")
    assert buckets[0].total_gst == Decimal("18000.00")


def test_calculate_taxes_by_bucket_inter_state():
    items = [
        {"amount": Decimal("100000.00"), "gst_rate": Decimal("18.00")}
    ]
    buckets = calculate_taxes_by_bucket(
        seller_state="Tamil Nadu",
        buyer_state="Noida, Uttar Pradesh",
        items=items
    )
    assert len(buckets) == 1
    assert buckets[0].cgst == Decimal("0.00")
    assert buckets[0].sgst == Decimal("0.00")
    assert buckets[0].igst == Decimal("18000.00")
    assert buckets[0].total_gst == Decimal("18000.00")
