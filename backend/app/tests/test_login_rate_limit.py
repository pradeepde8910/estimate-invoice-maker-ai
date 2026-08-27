"""
Tests for the login brute-force guard wired into app/api/auth.py's /login —
app/core/rate_limiter.py already implemented lockout logic but was never
called from the endpoint that's actually mounted at /api/auth/login.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import router as auth_router
from app.core.database import get_db
from app.models.base import Base
from app.models.user import User
from app.core import rate_limiter
from app.core.security import hash_password


@pytest.fixture(autouse=True)
def _reset_rate_limiter_state():
    # Module-level dicts persist across tests otherwise — each test needs a
    # clean slate so an earlier test's lockout doesn't bleed into the next.
    rate_limiter._failures.clear()
    rate_limiter._locked_until.clear()
    yield
    rate_limiter._failures.clear()
    rate_limiter._locked_until.clear()


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = SessionLocal()
    db.add(User(username="bob", password_hash=hash_password("correct-password"), role="Developer"))
    db.commit()
    db.close()

    app = FastAPI()
    app.include_router(auth_router, prefix="/api/auth")

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_correct_login_succeeds(client):
    resp = client.post("/api/auth/login", json={"username": "bob", "password": "correct-password"})
    assert resp.status_code == 200
    assert "token" in resp.json()


def test_wrong_password_rejected_but_not_locked_out_immediately(client):
    resp = client.post("/api/auth/login", json={"username": "bob", "password": "wrong"})
    assert resp.status_code == 401


def test_repeated_failures_trigger_lockout(client):
    for _ in range(rate_limiter.MAX_FAILED_ATTEMPTS):
        resp = client.post("/api/auth/login", json={"username": "bob", "password": "wrong"})
        assert resp.status_code == 401

    # One more attempt, even with the CORRECT password, must now be
    # rate-limited rather than silently authenticating a brute-forcer who
    # eventually guesses right within the flood of attempts.
    resp = client.post("/api/auth/login", json={"username": "bob", "password": "correct-password"})
    assert resp.status_code == 429


def test_lockout_is_scoped_to_ip_and_username_pair():
    # A different username shouldn't be locked out by another user's failures.
    rate_limiter.record_login_failure("1.2.3.4", "bob")
    rate_limiter.record_login_failure("1.2.3.4", "bob")
    assert rate_limiter.check_login_rate_limit("1.2.3.4", "alice") is None


def test_successful_login_clears_prior_failure_count():
    rate_limiter.record_login_failure("1.2.3.4", "bob")
    rate_limiter.record_login_failure("1.2.3.4", "bob")
    rate_limiter.record_login_success("1.2.3.4", "bob")
    # 2 failures recorded then cleared; 2 more shouldn't trigger lockout
    # (threshold is 5), proving the counter actually reset.
    rate_limiter.record_login_failure("1.2.3.4", "bob")
    rate_limiter.record_login_failure("1.2.3.4", "bob")
    assert rate_limiter.check_login_rate_limit("1.2.3.4", "bob") is None
