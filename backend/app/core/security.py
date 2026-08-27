"""Password hashing, JWT-like token, and QA API key primitives — the single
security implementation both the auth router (app/api/auth.py) and the
auth dependency (app/api/dependencies.py) use, so there is exactly one
place that issues and verifies sessions.

Existing rows may still hold a legacy plaintext password (this app had no
hashing at all until now). verify_password() accepts either form so logins
keep working, and the caller re-hashes on successful legacy verification so
every account is transparently upgraded to bcrypt the next time it logs in.
"""
import base64
import hashlib
import hmac
import json
import time

import bcrypt

from app import config

_BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")

TOKEN_TTL_SECONDS = 24 * 60 * 60  # 24 hours


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def is_bcrypt_hash(value: str) -> bool:
    return bool(value) and value.startswith(_BCRYPT_PREFIXES)


def verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False
    if is_bcrypt_hash(stored):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
        except ValueError:
            return False
    # Legacy plaintext row: constant-time compare so this path doesn't leak
    # timing information any worse than the bcrypt path does.
    return hmac.compare_digest(password.encode("utf-8"), stored.encode("utf-8"))


# ── Session tokens ────────────────────────────────────────────────────────
# HMAC-SHA256 "JWT-like" token: base64url(payload_json) + "." + hex HMAC
# signature over that payload, keyed by config.JWT_SECRET. Not a real JWT
# library on purpose — this app has always used this exact scheme (see the
# git history of v1/api.py's create_token/decode_token), and changing the
# token *format* here would invalidate every existing session's Bearer
# token on deploy. Keep the wire format stable even as the code moves.

def create_access_token(username: str, role: str) -> str:
    exp = int(time.time()) + TOKEN_TTL_SECONDS
    payload = {"user": username, "role": role, "exp": exp}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signature = hmac.new(config.JWT_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def decode_access_token(token: str) -> dict | None:
    """Verifies the HMAC signature and expiry and returns the decoded payload."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, signature = parts
        expected_signature = hmac.new(config.JWT_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            return None

        padding = "=" * (4 - len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64 + padding).decode()
        payload = json.loads(payload_json)
        if int(time.time()) > payload.get("exp", 0):
            return None
        return payload
    except Exception:
        return None


# ── QA API key ───────────────────────────────────────────────────────────
def verify_qa_api_key(api_key: str) -> bool:
    """True only when QA mode is explicitly enabled (config.QA_TEST_API_KEY
    set) and the supplied key matches it exactly. Never a bypass when QA
    mode is off — an empty configured key must never match an empty/blank
    header value, hence the truthiness check on both sides."""
    if not config.QA_TEST_API_KEY or not api_key:
        return False
    return hmac.compare_digest(api_key, config.QA_TEST_API_KEY)
