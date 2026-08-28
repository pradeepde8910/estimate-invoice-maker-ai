import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from backend directory, repo root directory, and current working directory
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BACKEND_DIR.parent

load_dotenv(_REPO_ROOT / ".env")
load_dotenv(_BACKEND_DIR / ".env")
load_dotenv()


# ─── API Keys ────────────────────────────────────────────────────────────────
MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "")

GEMINI_API_KEYS: list[str] = [
    k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()
]

# ─── Authentication Settings ──────────────────────────────────────────────────
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
QA_TEST_USERNAME = os.getenv("QA_TEST_USERNAME", ADMIN_USERNAME)

# ─── Database Settings ────────────────────────────────────────────────────────
# Must match app/database.py's V2_DATABASE_URL default — app/core/database.py
# (used by the restored routers: documents, estimations, clients, jobs,
# organization, system, rate_cards) and app/database.py (used by invoice_service/
# project.py/pdf_service, this session's tested V2 invoicing work) need to be
# the SAME physical database, or half the app silently reads/writes an empty
# legacy file while the other half sees real data.
DATABASE_URL = os.getenv("DATABASE_URL", os.getenv("V2_DATABASE_URL", "sqlite:///../pixous_staging.db")).strip()

# ─── Model Configuration ─────────────────────────────────────────────────────
MISTRAL_OCR_MODEL = "mistral-ocr-latest"
GEMINI_LLM_MODEL = "gemini-3.1-flash-lite"
GEMINI_SEARCH_MODEL = os.getenv("GEMINI_SEARCH_MODEL", "gemini-3.5-flash-lite")

# ─── Processing Settings ─────────────────────────────────────────────────────
MAX_CHUNK_CHARS = 12_000          # Max characters per LLM call
RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2
MAX_ESTIMATION_VALIDATION_RETRIES = 2

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

# ─── Data & Output Settings ──────────────────────────────────────────────────
# Resolve paths relative to the project root (parent of the backend directory, or wherever it is run from)
DATA_DIR = os.getenv("DATA_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data")))
OUTPUT_DIR = os.path.join(DATA_DIR, "output")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
