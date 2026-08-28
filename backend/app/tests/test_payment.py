"""
Unit and integration tests for the payment module (app/api/payment.py +
app/services/payment_service.py).

Context: payment.router implements a full payment lifecycle (manual entry,
initiate/processing/success/failure, correction) with row locking and
overpayment guards, but was never mounted in main.py's include_router list —
every payment endpoint 404'd in production despite the frontend
(RecordPaymentModal.tsx) calling it. This file both proves the router is now
reachable and exercises the underlying business logic, which previously had
zero test coverage.
"""

import json
import pytest
from decimal import Decimal
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models.base import Base
from app.models.master import Client
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.audit import AuditLog
from app.models.user import User
from app.api.payment import router as payment_router
from app.api.dependencies import get_current_user
from app.database import get_db as payment_get_db


ADMIN_USER = User(id="admin-1", username="admin", role="Admin")
DEVELOPER_USER = User(id="dev-1", username="dev", role="Developer")


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def make_client(session_factory):
    """Builds a TestClient wired to an isolated in-memory DB, with the
    authenticated user swappable per-test via the returned setter."""
    state = {"user": ADMIN_USER}

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def override_user():
        return state["user"]

    app = FastAPI()
    app.include_router(payment_router)
    app.dependency_overrides[payment_get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    def _make(user=ADMIN_USER):
        state["user"] = user
        return TestClient(app)

    return _make


@pytest.fixture
def issued_invoice(session_factory):
    """Seeds a Client + an ISSUED, unpaid invoice with total_payable=1000."""
    db = session_factory()
    client = Client(
        id="client-1",
        company_name="Acme Corp",
        contact_person="Jane Doe",
        email="jane@acme.example",
        phone="+911234567890",
        gstin="07AABCB7821M1Z2",
        status="ACTIVE",
    )
    invoice = Invoice(
        id="inv-1",
        invoice_type="STANDALONE",
        client_id="client-1",
        subtotal=Decimal("1000.00"),
        total_payable=Decimal("1000.00"),
        status="ISSUED",
        payment_status="UNPAID",
    )
    db.add_all([client, invoice])
    db.commit()
    db.close()
    return "inv-1"


def _get(session_factory, model, **filters):
    db = session_factory()
    try:
        q = db.query(model)
        for k, v in filters.items():
            q = q.filter(getattr(model, k) == v)
        return q.all()
    finally:
        db.close()


class TestRouterIsRegistered:
    def test_payment_routes_are_mounted_on_the_real_app(self):
        """Regression test for the router never being included in main.py —
        every payment path must resolve to a concrete route at /api/payments."""
        import main

        schema = main.app.openapi()
        assert "/api/payments/{project_id}/invoices/{invoice_id}/payments" in schema["paths"]
        assert "/api/payments/{project_id}/invoices/{invoice_id}/payments/manual" in schema["paths"]
        assert "/api/payments/{project_id}/invoices/{invoice_id}/payments/{payment_id}/success" in schema["paths"]


class TestManualPayment:
    def test_full_payment_marks_invoice_paid_and_attributes_audit_to_caller(
        self, make_client, issued_invoice, session_factory
    ):
        client = make_client(ADMIN_USER)
        resp = client.post(
            "/proj-1/invoices/inv-1/payments/manual",
            json={"amount": "1000.00", "payment_method": "BANK_TRANSFER"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "SUCCESS"
        assert body["payment_reference"].startswith("PAY/")

        invoices = _get(session_factory, Invoice, id="inv-1")
        assert invoices[0].payment_status == "PAID"

        logs = _get(session_factory, AuditLog, action="PAYMENT_RECORDED_MANUAL")
        assert len(logs) == 1
        # Regression: handler used to omit user_id, defaulting the service to "system"
        # regardless of who actually recorded the payment.
        assert logs[0].user_id == "admin-1"

    def test_partial_payment_marks_invoice_partially_paid(self, make_client, issued_invoice, session_factory):
        client = make_client(ADMIN_USER)
        resp = client.post(
            "/proj-1/invoices/inv-1/payments/manual",
            json={"amount": "400.00", "payment_method": "UPI"},
        )
        assert resp.status_code == 200
        invoices = _get(session_factory, Invoice, id="inv-1")
        assert invoices[0].payment_status == "PARTIALLY_PAID"

    def test_overpayment_is_rejected(self, make_client, issued_invoice):
        client = make_client(ADMIN_USER)
        resp = client.post(
            "/proj-1/invoices/inv-1/payments/manual",
            json={"amount": "1500.00", "payment_method": "CASH"},
        )
        assert resp.status_code == 400
        assert "exceeds the outstanding balance" in resp.json()["detail"]

    def test_payment_against_draft_invoice_is_rejected(self, make_client, session_factory):
        db = session_factory()
        db.add_all([
            Client(id="c1", company_name="Acme", contact_person="Jane", email="j@a.com",
                   phone="+911234567890", gstin="07AABCB7821M1Z2", status="ACTIVE"),
            Invoice(id="inv-draft", invoice_type="STANDALONE", client_id="c1",
                    total_payable=Decimal("500.00"), status="DRAFT", payment_status="UNPAID"),
        ])
        db.commit()
        db.close()

        client = make_client(ADMIN_USER)
        resp = client.post(
            "/proj-1/invoices/inv-draft/payments/manual",
            json={"amount": "100.00", "payment_method": "CASH"},
        )
        assert resp.status_code == 400
        assert "ISSUED" in resp.json()["detail"]

    def test_payment_against_unknown_invoice_is_404(self, make_client):
        client = make_client(ADMIN_USER)
        resp = client.post(
            "/proj-1/invoices/does-not-exist/payments/manual",
            json={"amount": "100.00", "payment_method": "CASH"},
        )
        assert resp.status_code == 404

    def test_role_without_finance_or_admin_is_forbidden(self, make_client, issued_invoice):
        client = make_client(DEVELOPER_USER)
        resp = client.post(
            "/proj-1/invoices/inv-1/payments/manual",
            json={"amount": "100.00", "payment_method": "CASH"},
        )
        assert resp.status_code == 403


class TestGatewayLifecycle:
    def test_initiate_then_success_updates_invoice_and_attributes_audit(
        self, make_client, issued_invoice, session_factory
    ):
        client = make_client(ADMIN_USER)

        initiate_resp = client.post(
            "/proj-1/invoices/inv-1/payments",
            json={"amount": "1000.00", "payment_method": "CARD"},
        )
        assert initiate_resp.status_code == 200
        assert initiate_resp.json()["status"] == "INITIATED"
        payment_id = initiate_resp.json()["id"]

        processing_resp = client.post(
            f"/proj-1/invoices/inv-1/payments/{payment_id}/processing"
        )
        assert processing_resp.status_code == 200
        assert processing_resp.json()["status"] == "PROCESSING"

        success_resp = client.post(
            f"/proj-1/invoices/inv-1/payments/{payment_id}/success",
            json={"received_at": datetime.utcnow().isoformat()},
        )
        assert success_resp.status_code == 200
        assert success_resp.json()["status"] == "SUCCESS"

        invoices = _get(session_factory, Invoice, id="inv-1")
        assert invoices[0].payment_status == "PAID"

        logs = _get(session_factory, AuditLog, action="PAYMENT_SUCCESS")
        assert logs[0].user_id == "admin-1"

    def test_success_cannot_follow_failed(self, make_client, issued_invoice):
        client = make_client(ADMIN_USER)
        payment_id = client.post(
            "/proj-1/invoices/inv-1/payments",
            json={"amount": "500.00", "payment_method": "CARD"},
        ).json()["id"]

        fail_resp = client.post(f"/proj-1/invoices/inv-1/payments/{payment_id}/failure", json={})
        assert fail_resp.status_code == 200
        assert fail_resp.json()["status"] == "FAILED"

        success_resp = client.post(
            f"/proj-1/invoices/inv-1/payments/{payment_id}/success",
            json={"received_at": datetime.utcnow().isoformat()},
        )
        assert success_resp.status_code == 400


class TestCorrection:
    def test_correcting_a_success_payment_recomputes_invoice_status(
        self, make_client, issued_invoice, session_factory
    ):
        client = make_client(ADMIN_USER)
        payment_id = client.post(
            "/proj-1/invoices/inv-1/payments/manual",
            json={"amount": "1000.00", "payment_method": "CASH"},
        ).json()["id"]

        invoices = _get(session_factory, Invoice, id="inv-1")
        assert invoices[0].payment_status == "PAID"

        correct_resp = client.put(
            f"/proj-1/invoices/inv-1/payments/{payment_id}/correct",
            json={"corrected_amount": "600.00", "reason": "Data entry error"},
        )
        assert correct_resp.status_code == 200

        invoices = _get(session_factory, Invoice, id="inv-1")
        assert invoices[0].payment_status == "PARTIALLY_PAID"

        logs = _get(session_factory, AuditLog, action="PAYMENT_CORRECTION")
        assert logs[0].user_id == "admin-1"

    def test_correction_exceeding_balance_is_rejected(self, make_client, issued_invoice):
        client = make_client(ADMIN_USER)
        payment_id = client.post(
            "/proj-1/invoices/inv-1/payments/manual",
            json={"amount": "400.00", "payment_method": "CASH"},
        ).json()["id"]

        resp = client.put(
            f"/proj-1/invoices/inv-1/payments/{payment_id}/correct",
            json={"corrected_amount": "5000.00", "reason": "typo fix attempt"},
        )
        assert resp.status_code == 400
