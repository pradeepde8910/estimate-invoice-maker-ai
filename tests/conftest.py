"""
Shared pytest fixtures for security tests.

IMPORTANT: DATABASE_URL is overridden to an isolated temp sqlite file *before*
any project module is imported, so these tests never touch the real
pixous.db / production data.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_tmp_db_fd, _tmp_db_path = tempfile.mkstemp(suffix=".db")
os.close(_tmp_db_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db_path}"

import config  # noqa: E402
import db  # noqa: E402
import api  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_database():
    """Recreate all tables before every test so tests never see each other's rows."""
    db.Base.metadata.drop_all(bind=db.engine)
    db.Base.metadata.create_all(bind=db.engine)
    api.JOBS.clear()
    yield
    db.Base.metadata.drop_all(bind=db.engine)


@pytest.fixture
def client():
    return TestClient(api.app)


@pytest.fixture
def db_session():
    session = db.SessionLocal()
    try:
        yield session
    finally:
        session.close()


def make_user(session, username: str, plaintext_password: str, role: str = "Admin"):
    """Creates a user the way the app does post-fix: password_hash holds a
    bcrypt hash, never the raw password."""
    from utils.security import hash_password

    user = db.User(username=username, password_hash=hash_password(plaintext_password), role=role)
    session.add(user)
    session.commit()
    return user


def make_legacy_plaintext_user(session, username: str, plaintext_password: str, role: str = "Admin"):
    """Simulates a row created before the hashing fix existed - password_hash
    holds the raw plaintext value. Used to test the transparent upgrade path."""
    user = db.User(username=username, password_hash=plaintext_password, role=role)
    session.add(user)
    session.commit()
    return user


def pytest_sessionfinish(session, exitstatus):
    try:
        os.remove(_tmp_db_path)
    except OSError:
        pass
