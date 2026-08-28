"""
Regression tests for GET /api/projects/{project_id}/billing-preview
(app/api/projects.py::get_billing_preview).

Context: this endpoint used to run two extra DB queries per task (one
checking ISSUED invoice items, one checking DRAFT invoice items) inside the
task loop — an N+1 pattern. It was rewritten to batch-fetch all billed/draft
InvoiceItem (milestone_id, task_key) pairs once up front into an in-memory
set, and to prebuild a classification-by-id lookup instead of querying per
match. These tests pin the observable behavior (which tasks are included or
excluded) so that optimization can't silently change what gets billed.
"""

import pytest
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models.base import Base
from app.models.master import Client
from app.models.project import Project, ProjectMilestone
from app.models.estimation import Estimation
from app.models.invoice import Invoice, InvoiceItem
from app.models.user import User
from app.api.projects import router as projects_router
from app.api.dependencies import get_current_user
from app.database import get_db as projects_get_db
import app.api.projects as projects_module


ADMIN_USER = User(id="admin-1", username="admin", role="Admin")

RAW_PIPELINE_JSON = {
    "cost_estimation": {
        "unit_estimates": [
            {
                "unit_id": "unit-1",
                "requirement_estimates": [
                    {
                        "title": "Login Module",
                        "implementation_tasks": [
                            {"task": "Build login API", "cost": 500, "hours": 10},
                            {"task": "Build login UI", "cost": 300, "hours": 6},
                        ],
                    }
                ],
            }
        ]
    }
}


@pytest.fixture
def client_app(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # projects.py queries Project/ProjectMilestone/InvoiceItem via app.database's
    # get_db, but the Estimation (with raw_pipeline_json) via a separate
    # V1SessionLocal (app.core.database.SessionLocal) — in production both
    # point at the same physical DB, so for this test both are bound to the
    # same in-memory engine/sessionmaker.
    monkeypatch.setattr(projects_module, "V1SessionLocal", TestSessionLocal)

    def override_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(projects_router, prefix="/api/projects")
    app.dependency_overrides[projects_get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: ADMIN_USER

    return TestClient(app), TestSessionLocal


def _seed(session_factory, invoice_items=None):
    db = session_factory()
    db.add(Client(
        id="client-1", company_name="Acme", contact_person="Jane",
        email="j@a.com", phone="+911234567890", gstin="07AABCB7821M1Z2", status="ACTIVE",
    ))
    db.add(Estimation(
        id="est-1", estimation_number="EST-1", client_id="client-1",
        project_name="Test Project", status="Converted",
        raw_pipeline_json=RAW_PIPELINE_JSON,
    ))
    db.add(Project(
        id="proj-1", client_id="client-1", project_number="P-1", project_name="Test Project",
        contract_value=Decimal("1000.00"), estimation_id="est-1",
    ))
    db.add(ProjectMilestone(
        id="ms-1", project_id="proj-1", name="Milestone 1",
        amount=Decimal("800.00"), status="PENDING", source_unit_id="unit-1",
    ))
    if invoice_items:
        db.add(Invoice(
            id="inv-1", invoice_type="PROJECT", project_id="proj-1", client_id="client-1",
            total_payable=Decimal("500.00"), status=invoice_items["invoice_status"],
        ))
        db.flush()
        db.add(InvoiceItem(
            id="item-1", invoice_id="inv-1", milestone_id="ms-1",
            task_key=invoice_items["task_key"], description="Build login API",
            amount=Decimal("500.00"),
        ))
    db.commit()
    db.close()


class TestBillingPreview:
    def test_unbilled_tasks_are_all_returned(self, client_app):
        client, session_factory = client_app
        _seed(session_factory)

        resp = client.get("/api/projects/proj-1/billing-preview")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["milestones"]) == 1
        tasks = body["milestones"][0]["tasks"]
        assert {t["description"] for t in tasks} == {"Build login API", "Build login UI"}

    def test_task_already_on_issued_invoice_is_excluded(self, client_app):
        client, session_factory = client_app
        _seed(session_factory, invoice_items={"invoice_status": "ISSUED", "task_key": "unit-1:req-0:task-0"})

        resp = client.get("/api/projects/proj-1/billing-preview")
        assert resp.status_code == 200
        tasks = resp.json()["milestones"][0]["tasks"]
        descriptions = {t["description"] for t in tasks}
        assert "Build login API" not in descriptions
        assert "Build login UI" in descriptions

    def test_task_already_on_draft_invoice_is_excluded(self, client_app):
        client, session_factory = client_app
        _seed(session_factory, invoice_items={"invoice_status": "DRAFT", "task_key": "unit-1:req-0:task-0"})

        resp = client.get("/api/projects/proj-1/billing-preview")
        assert resp.status_code == 200
        descriptions = {t["description"] for t in resp.json()["milestones"][0]["tasks"]}
        assert "Build login API" not in descriptions

    def test_task_on_cancelled_invoice_is_not_excluded(self, client_app):
        """CANCELLED invoices don't hold a task's billing slot — a cancelled
        draft shouldn't permanently block the underlying task from being billed."""
        client, session_factory = client_app
        _seed(session_factory, invoice_items={"invoice_status": "CANCELLED", "task_key": "unit-1:req-0:task-0"})

        resp = client.get("/api/projects/proj-1/billing-preview")
        assert resp.status_code == 200
        descriptions = {t["description"] for t in resp.json()["milestones"][0]["tasks"]}
        assert "Build login API" in descriptions

    def test_milestone_with_all_tasks_billed_is_omitted_entirely(self, client_app):
        client, session_factory = client_app
        db = session_factory()
        db.add(Client(
            id="client-1", company_name="Acme", contact_person="Jane",
            email="j@a.com", phone="+911234567890", gstin="07AABCB7821M1Z2", status="ACTIVE",
        ))
        single_task_json = {
            "cost_estimation": {
                "unit_estimates": [{
                    "unit_id": "unit-1",
                    "requirement_estimates": [{
                        "title": "Login Module",
                        "implementation_tasks": [{"task": "Build login API", "cost": 500, "hours": 10}],
                    }],
                }]
            }
        }
        db.add(Estimation(
            id="est-1", estimation_number="EST-1", client_id="client-1",
            project_name="Test Project", status="Converted", raw_pipeline_json=single_task_json,
        ))
        db.add(Project(
            id="proj-1", client_id="client-1", project_number="P-1", project_name="Test Project",
            contract_value=Decimal("1000.00"), estimation_id="est-1",
        ))
        db.add(ProjectMilestone(
            id="ms-1", project_id="proj-1", name="Milestone 1",
            amount=Decimal("500.00"), status="PENDING", source_unit_id="unit-1",
        ))
        db.add(Invoice(id="inv-1", invoice_type="PROJECT", project_id="proj-1", client_id="client-1",
                        total_payable=Decimal("500.00"), status="ISSUED"))
        db.flush()
        db.add(InvoiceItem(id="item-1", invoice_id="inv-1", milestone_id="ms-1",
                            task_key="unit-1:req-0:task-0", description="Build login API", amount=Decimal("500.00")))
        db.commit()
        db.close()

        resp = client.get("/api/projects/proj-1/billing-preview")
        assert resp.status_code == 200
        assert resp.json()["milestones"] == []

    def test_unknown_project_is_404(self, client_app):
        client, _ = client_app
        resp = client.get("/api/projects/does-not-exist/billing-preview")
        assert resp.status_code == 404

    def test_project_without_milestones_returns_empty(self, client_app):
        client, session_factory = client_app
        db = session_factory()
        db.add(Client(
            id="client-1", company_name="Acme", contact_person="Jane",
            email="j@a.com", phone="+911234567890", gstin="07AABCB7821M1Z2", status="ACTIVE",
        ))
        db.add(Estimation(
            id="est-1", estimation_number="EST-1", client_id="client-1",
            project_name="Test Project", status="Converted", raw_pipeline_json=RAW_PIPELINE_JSON,
        ))
        db.add(Project(
            id="proj-1", client_id="client-1", project_number="P-1", project_name="Test Project",
            contract_value=Decimal("1000.00"), estimation_id="est-1",
        ))
        db.commit()
        db.close()

        resp = client.get("/api/projects/proj-1/billing-preview")
        assert resp.status_code == 200
        assert resp.json()["milestones"] == []
