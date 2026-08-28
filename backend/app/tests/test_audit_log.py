"""
Unit and integration tests for AuditLog persistence and bootstrap admin / system actions.
Verifies that AuditLog records can be created with arbitrary actor IDs
(e.g., 'bootstrap-admin', 'system', UUID, None) without foreign key violations.
"""

import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models.base import Base
from app.models.audit import AuditLog
from app.models.master import Client
from app.models.estimation import Estimation
from app.models.user import User
from app.api.estimations import router as estimations_router
from app.core.database import get_db, _run_migrations
from app.api.dependencies import get_current_user
from app import config


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    yield session
    session.close()


def test_audit_log_supports_bootstrap_admin_and_system_ids(db_session):
    """Verifies that AuditLog rows can be persisted with non-user actor IDs."""
    entries = [
        AuditLog(user_id="bootstrap-admin", action="UPDATE_ESTIMATION_CLIENT", details=json.dumps({"field": "val"})),
        AuditLog(user_id="system", action="PAYMENT_RECORDED_MANUAL", details=json.dumps({"amount": 100})),
        AuditLog(user_id=None, action="INVOICE_CREATED", details=json.dumps({"num": "INV-1"})),
        AuditLog(user_id="custom-uuid-1234", action="SOME_ACTION", details="{}"),
    ]
    db_session.add_all(entries)
    db_session.commit()

    saved = db_session.query(AuditLog).all()
    assert len(saved) == 4
    user_ids = {log.user_id for log in saved}
    assert user_ids == {"bootstrap-admin", "system", None, "custom-uuid-1234"}


def test_update_estimation_client_as_bootstrap_admin(monkeypatch):
    """Verifies that updating estimation client with bootstrap admin auth creates audit log without error."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = Session()
    client = Client(
        id="client-1",
        company_name="Test Company",
        contact_person="Priya Sharma",
        email="priya@example.com",
        phone="+919871245678",
        gstin="07AABCB7821M1Z2",
        status="DRAFT"
    )
    estimation = Estimation(
        id="est-1",
        estimation_number="EST-2026-000001",
        client_id="client-1",
        project_name="Test Project",
        status="DRAFT"
    )
    db.add_all([client, estimation])
    db.commit()
    db.close()

    app = FastAPI()
    app.include_router(estimations_router)

    # Override DB to use the test SQLite instance
    def override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    # Simulate bootstrap admin user
    bootstrap_admin = User(id="bootstrap-admin", username="admin", role="Admin")
    app.dependency_overrides[get_current_user] = lambda: bootstrap_admin

    # Patch SessionLocal in estimations module
    import app.api.estimations as est_module
    monkeypatch.setattr(est_module, "SessionLocal", Session)

    test_client = TestClient(app)
    response = test_client.patch(
        "/api/estimations/est-1/client",
        json={
            "company_name": "VertexCore Systems Pvt. Ltd.",
            "contact_person": "Priya Sharma",
            "email": "priya.sharma@bluepeakdigital.in",
            "phone": "+91 98712 45678",
            "billing_address": "2nd Floor, Sector 62, Noida",
            "gstin": "07AABCB7821M1Z2",
            "status": "CONFIRMED"
        }
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Verify audit log was recorded with user_id = 'bootstrap-admin'
    verify_db = Session()
    logs = verify_db.query(AuditLog).filter(AuditLog.action == "UPDATE_ESTIMATION_CLIENT").all()
    assert len(logs) == 1
    assert logs[0].user_id == "bootstrap-admin"
    verify_db.close()
