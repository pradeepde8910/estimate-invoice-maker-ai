"""
Configuration module — loads API keys, model settings, and developer rate cards.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── API Keys ────────────────────────────────────────────────────────────────

MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "")

# Multiple keys for rotation (comma-separated in .env)
GROQ_API_KEYS: list[str] = [
    k.strip() for k in os.getenv("GROQ_API_KEYS", "").split(",") if k.strip()
]
GEMINI_API_KEYS: list[str] = [
    k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()
]

# ─── Authentication Settings ──────────────────────────────────────────────────
# ADMIN_USERNAME/ADMIN_PASSWORD gate a one-time bootstrap login used only
# before any User row exists (see api.py login_endpoint). No default
# password ships in source; leaving ADMIN_PASSWORD unset simply disables
# that bootstrap path, forcing account creation via scripts/create_user.py.
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

JWT_SECRET = os.getenv("JWT_SECRET", "")
if not JWT_SECRET:
    raise RuntimeError(
        "JWT_SECRET is not set. Generate one (e.g. `python -c \"import secrets; "
        "print(secrets.token_urlsafe(48))\"`) and set it in your .env file - "
        "the app refuses to start with no signing secret rather than fall "
        "back to a value that used to be hardcoded in source."
    )

QA_TEST_API_KEY = os.getenv("QA_TEST_API_KEY", "")
# Identity that requests authenticated via X-API-Key resolve to, so
# role-gated endpoints (require_role) behave the same for QA tooling
# (Postman/JMeter/k6) as they do for a real Bearer-token login, instead of
# the API key silently skipping authorization checks entirely. Defaults to
# the admin bootstrap username so QA can exercise Admin-only endpoints out
# of the box; point it at a dedicated low-privilege account's username to
# test non-Admin paths instead.
QA_TEST_USERNAME = os.getenv("QA_TEST_USERNAME", ADMIN_USERNAME)

# ─── Database Settings ────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///pixous.db").strip()


# ─── Model Configuration ─────────────────────────────────────────────────────

MISTRAL_OCR_MODEL = "mistral-ocr-latest"
GROQ_LLM_MODEL = "llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini-3.6-flash"

# ─── Processing Settings ─────────────────────────────────────────────────────

MAX_CHUNK_CHARS = 12_000          # Max characters per LLM call (Groq context safety, 12k fits well within TPM limits)
RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2

# ─── Developer Rate Card (INR/hour) ──────────────────────────────────────────

DEVELOPER_RATES = {
    "junior_developer":       {"rate_per_hour": 2000, "label": "Junior Developer"},
    "mid_developer":          {"rate_per_hour": 3500, "label": "Mid-Level Developer"},
    "senior_developer":       {"rate_per_hour": 6000, "label": "Senior Developer"},
    "lead_developer":         {"rate_per_hour": 7500, "label": "Tech Lead / Architect"},
    "ui_ux_designer":         {"rate_per_hour": 4500, "label": "UI/UX Designer"},
    "qa_engineer":            {"rate_per_hour": 3200, "label": "QA Engineer"},
    "devops_engineer":        {"rate_per_hour": 5200, "label": "DevOps Engineer"},
    "project_manager":        {"rate_per_hour": 4800, "label": "Project Manager"},
    "business_analyst":       {"rate_per_hour": 4000, "label": "Business Analyst"},
    "data_engineer":          {"rate_per_hour": 5600, "label": "Data Engineer"},
    "ml_engineer":            {"rate_per_hour": 6800, "label": "ML Engineer"},
    "security_specialist":    {"rate_per_hour": 6400, "label": "Security Specialist"},
}

SYSTEM_ROLE_KEYS = set(DEVELOPER_RATES.keys())

# ─── Output Settings ─────────────────────────────────────────────────────────

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
