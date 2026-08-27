"""
End-to-end security tests for auth/role enforcement on the invoice API,
run against an isolated in-memory SQLite DB (never the real dev database).

Covers: no-token access, garbage-token access, wrong-role access, and a
smoke check that a 404 for a missing resource doesn't leak internals.
"""

import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config
from app.api.invoices import router as invoice_router
from app.database import get_db
from app.core.database import get_db as get_core_db
from app.models.base import Base
from app.models.user import User

TEST_SECRET = "endpoint-test-secret"


@pytest.fixture(scope="module")
def engine():
    # StaticPool (not the default SingletonThreadPool) is required here:
    # Starlette's TestClient runs each request through a worker thread, and
    # SingletonThreadPool keys its one :memory: connection per-thread — the
    # request would silently see a second, empty in-memory DB instead of
    # the one seeded_users just populated, surfacing as "no such table".
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture(scope="module")
def SessionLocal(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module")
def seeded_users(SessionLocal):
    db = SessionLocal()
    finance_user = User(username="finance_alice", password_hash="x", role="Finance")
    dev_user = User(username="dev_bob", password_hash="x", role="Developer")
    db.add_all([finance_user, dev_user])
    db.commit()
    yield {"finance": finance_user.username, "dev": dev_user.username}
    db.close()


@pytest.fixture(scope="module")
def client(SessionLocal):
    app = FastAPI()
    app.include_router(invoice_router)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Two DB modules coexist post-restoration: the invoice router itself
    # uses app.database.get_db, but the auth dependency chain
    # (require_roles -> get_current_user, in app/api/dependencies.py) uses
    # app.core.database.get_db — a different function object even though
    # both now point at the same physical file outside tests. Both must be
    # overridden or the auth lookup silently falls through to the real DB.
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_core_db] = override_get_db
    return TestClient(app)


@pytest.fixture(autouse=True)
def _fixed_secret(monkeypatch):
    monkeypatch.setattr(config, "JWT_SECRET", TEST_SECRET)
    yield


def _token_for(username: str, secret: str = TEST_SECRET, exp_delta: int = 3600) -> str:
    payload = {"user": username, "exp": int(time.time()) + exp_delta}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signature = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def test_get_invoice_without_token_is_rejected(client):
    resp = client.get("/some-invoice-id")
    assert resp.status_code == 401


def test_get_invoice_with_garbage_token_is_rejected(client):
    resp = client.get("/some-invoice-id", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_get_invoice_with_token_forged_under_wrong_secret_is_rejected(client):
    forged = _token_for("finance_alice", secret="attacker-does-not-know-this")
    resp = client.get("/some-invoice-id", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401


def test_get_invoice_with_expired_token_is_rejected(client):
    expired = _token_for("finance_alice", exp_delta=-10)
    resp = client.get("/some-invoice-id", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401


def test_developer_role_forbidden_from_finance_only_route(client, seeded_users):
    # GET /invoices/{id} requires Admin/Finance — Developer must be 403, not 200/500.
    token = _token_for(seeded_users["dev"])
    resp = client.get("/some-invoice-id", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_finance_role_allowed_gets_404_not_500_for_missing_invoice(client, seeded_users):
    # Correct role, nonexistent resource: should be a clean 404, not a stack
    # trace / 500 that could leak internals.
    token = _token_for(seeded_users["finance"])
    resp = client.get("/does-not-exist", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404
    assert "Invoice not found" in resp.text


def test_unknown_username_in_valid_token_is_rejected(client):
    # Token is cryptographically valid but names a user that doesn't exist
    # (e.g. a deleted/deactivated account) and isn't the bootstrap admin.
    token = _token_for("someone_who_was_deleted")
    resp = client.get("/some-invoice-id", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
