"""
Root pytest conftest — ensures env vars from .env (JWT_SECRET, DATABASE_URL,
etc.) are loaded before any test module imports app.config or v1.config.

Without this, running `pytest` directly (rather than through main.py, whose
import of v1.api happens to call load_dotenv() as a side effect) hits
app.config's fail-closed RuntimeError on missing JWT_SECRET during test
collection, even though the app runs fine — the secret exists in .env, it
just was never loaded into this process's environment.
"""

import os
import sys

from dotenv import load_dotenv

_BACKEND_DIR = os.path.dirname(__file__)
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)

# .env lives at the repo root in this project, not inside backend/.
load_dotenv(os.path.join(_REPO_ROOT, ".env"))
load_dotenv(os.path.join(_BACKEND_DIR, ".env"))  # no-op if absent

# Tests still need to construct their own in-memory DB/session — this only
# guarantees JWT_SECRET (and any other required env var) is present so
# importing app.config / v1.config doesn't itself fail.
if not os.environ.get("JWT_SECRET"):
    # Last resort for a bare CI/test environment with no .env at all: tests
    # exercising auth need *a* deterministic secret, not the app's real one.
    os.environ["JWT_SECRET"] = "test-only-secret-do-not-use-in-production"

sys.path.insert(0, os.path.join(_BACKEND_DIR, "v1"))
