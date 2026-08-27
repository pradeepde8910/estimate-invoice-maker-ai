"""
Security-focused unit tests for the HMAC "JWT-like" token scheme, now
consolidated in app/core/security.py (decode_access_token/create_access_token)
rather than split between v1 and app/api/dependencies.py.

These test the auth primitive in isolation — no DB, no running server —
so they can't accidentally pass because of an unrelated fixture or a real
JWT_SECRET leaking in from the environment (each test builds its own token
using an explicit, test-local secret via monkeypatching app.config.JWT_SECRET).
"""

import base64
import hashlib
import hmac
import json
import time

import pytest

from app import config
from app.core.security import decode_access_token


TEST_SECRET = "unit-test-secret-not-the-real-one"


def _make_token(payload: dict, secret: str = TEST_SECRET) -> str:
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signature = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


@pytest.fixture(autouse=True)
def _fixed_secret(monkeypatch):
    monkeypatch.setattr(config, "JWT_SECRET", TEST_SECRET)
    yield


def test_valid_token_decodes():
    token = _make_token({"user": "alice", "exp": int(time.time()) + 3600})
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["user"] == "alice"


def test_tampered_signature_rejected():
    token = _make_token({"user": "alice", "exp": int(time.time()) + 3600})
    payload_b64, _sig = token.split(".")
    forged = f"{payload_b64}.{'0' * 64}"
    assert decode_access_token(forged) is None


def test_token_signed_with_wrong_secret_rejected():
    # Simulates an attacker who doesn't know JWT_SECRET forging their own token.
    token = _make_token({"user": "alice", "exp": int(time.time()) + 3600}, secret="attacker-guessed-secret")
    assert decode_access_token(token) is None


def test_expired_token_rejected():
    token = _make_token({"user": "alice", "exp": int(time.time()) - 10})
    assert decode_access_token(token) is None


def test_token_missing_exp_treated_as_expired():
    # payload.get("exp", 0) -> any current timestamp is > 0, so a payload
    # with no "exp" field at all must be rejected, not silently trusted.
    token = _make_token({"user": "alice"})
    assert decode_access_token(token) is None


@pytest.mark.parametrize("malformed", [
    "not-a-token",
    "only.one.dot.too.many",
    "",
    "missingdot",
])
def test_malformed_tokens_rejected(malformed):
    assert decode_access_token(malformed) is None


def test_payload_tampering_changes_signature_mismatch():
    # An attacker who edits the payload (e.g. to change "user" to "admin")
    # without knowing the secret can't produce a matching signature.
    token = _make_token({"user": "alice", "exp": int(time.time()) + 3600})
    payload_b64, signature = token.split(".")
    tampered_payload = base64.urlsafe_b64encode(
        json.dumps({"user": "admin", "exp": int(time.time()) + 3600}).encode()
    ).decode().rstrip("=")
    forged_token = f"{tampered_payload}.{signature}"
    assert decode_access_token(forged_token) is None


def test_none_algorithm_style_bypass_rejected():
    # Classic JWT "alg=none" bypass doesn't apply to this HMAC-only scheme,
    # but an empty/absent signature segment must still be rejected outright.
    payload_b64 = base64.urlsafe_b64encode(json.dumps({"user": "alice", "exp": int(time.time()) + 3600}).encode()).decode().rstrip("=")
    assert decode_access_token(f"{payload_b64}.") is None
    assert decode_access_token(payload_b64) is None  # no dot at all


def test_jwt_secret_fails_closed_when_unset(monkeypatch):
    """app/config.py must refuse to import with a silent weak default —
    this is the fix for the hardcoded 'supersecretkey' fallback found during
    the security review. Simulates a bare environment by clearing the env
    var and re-importing the module fresh.

    app/config.py calls load_dotenv() at import time, which — since it
    doesn't override already-set variables, only fills in missing ones —
    would silently refill JWT_SECRET from the real .env file the instant
    delenv() removes it, making the "unset" simulation a no-op. Stubbing
    load_dotenv() to do nothing is what actually makes this a bare
    environment for the reimport."""
    import importlib
    import os
    import sys

    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **kw: None)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    sys.modules.pop("app.config", None)
    try:
        with pytest.raises(RuntimeError):
            importlib.import_module("app.config")
    finally:
        # Restore for any subsequent test in the same process.
        sys.modules.pop("app.config", None)
        os.environ.setdefault("JWT_SECRET", TEST_SECRET)
        importlib.import_module("app.config")
