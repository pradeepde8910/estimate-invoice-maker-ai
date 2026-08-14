

"""
FastAPI backend for the Pixous Technologies Estimation & Invoicing app.

Wraps the existing LangGraph pipeline (agents/graph.py) with a small HTTP API:
  - Upload a document / URL / raw text and kick off an async analysis job
  - Poll job status with live per-stage progress (via graph.astream)
  - Fetch generated Quotation / BRD / SRS markdown
  - List & download previously generated documents from output/
  - View & edit the developer rate card used for cost estimation

Run with:
    uvicorn api:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tempfile
import uuid
import hmac
import hashlib
import time
import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field, field_validator

import config
from agents.graph import build_pipeline
from invoice_builder import build_invoice
from letterhead import apply_letterhead
from pdf_builder import markdown_to_pdf, html_to_pdf
import organization
from db import init_db, SessionLocal, User, Client, Estimation, Document, Invoice, RateCard, generate_next_serial
from utils.security import hash_password, is_bcrypt_hash, verify_password
from utils.rate_limiter import check_login_rate_limit, record_login_failure, record_login_success
from utils.html_sanitize import strip_script_vectors

logger = logging.getLogger("pixous.api")

# Run DB migrations + restore branding assets eagerly so they complete
# BEFORE StaticFiles mounts the branding/ directory and before the app
# serves any requests (startup event fires after the server is already up).
from db import restore_branding_assets as _restore_branding_assets, _run_migrations as _run_db_migrations
try:
    _run_db_migrations()
except Exception as _e:
    print(f"[startup] Pre-app migration warning: {_e}")
try:
    _restore_branding_assets()
except Exception:
    pass  # Table may not exist yet on very first deploy

app = FastAPI(title="Pixous Technologies API")

@app.on_event("startup")
def startup_event():
    init_db()
    # Re-run after DB tables are guaranteed to exist
    try:
        _restore_branding_assets()
    except Exception:
        pass

# --- Token helpers for authentication ---
def create_token(username: str) -> str:
    # Token valid for 24 hours
    exp = int(time.time()) + 86400
    payload = {"user": username, "exp": exp}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signature = hmac.new(config.JWT_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"

def decode_token(token: str) -> Optional[dict]:
    """Verifies the HMAC signature and expiry and returns the decoded
    payload, or None if the token is malformed, tampered, or expired.
    Does NOT check that the embedded username corresponds to a real,
    active account - callers that need that must use is_valid_username()
    against a DB session (see auth_middleware / get_current_username)."""
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


def verify_token(token: str) -> bool:
    return decode_token(token) is not None


def is_valid_username(username: str, db) -> bool:
    """A signed, unexpired JWT is only half of authentication - the
    username it names must also correspond to a real account, or to the
    bootstrap admin identity the login endpoint itself trusts before any
    User row exists. Without this check, anyone who knows JWT_SECRET could
    mint a token for a username that was never created and still pass
    every protected route (see login_endpoint's bootstrap comment for why
    the ADMIN_USERNAME carve-out exists)."""
    if not username:
        return False
    if username == config.ADMIN_USERNAME:
        return True
    return db.query(User).filter(User.username == username).first() is not None

class LoginRequest(BaseModel):
    username: str
    password: str

class EstimationPatch(BaseModel):
    project_name: Optional[str] = None
    timeline_weeks: Optional[float] = None
    grand_total: Optional[float] = None
    version: int

    @field_validator('timeline_weeks', 'grand_total')
    @classmethod
    def validate_positive(cls, v):
        if v is not None and v < 0:
            raise ValueError("Value must be non-negative")
        return v

class InvoicePatch(BaseModel):
    subtotal: Optional[float] = None
    gst_amount: Optional[float] = None
    discount: Optional[float] = None
    total: Optional[float] = None
    status: Optional[str] = None
    amount_paid: Optional[float] = None
    paid_on: Optional[str] = None

    @field_validator('subtotal', 'gst_amount', 'discount', 'total', 'amount_paid')
    @classmethod
    def validate_positive(cls, v):
        if v is not None and v < 0:
            raise ValueError("Value must be non-negative")
        return v

@app.post("/api/auth/login")
async def login_endpoint(payload: LoginRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    locked_seconds = check_login_rate_limit(client_ip, payload.username)
    if locked_seconds is not None:
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed login attempts. Try again in {int(locked_seconds) // 60 + 1} minute(s).",
        )

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == payload.username).first()

        # Bootstrap-only fallback: lets an operator log in as the configured
        # admin before any User row exists. Disabled entirely if
        # ADMIN_PASSWORD isn't set - no hardcoded default credential exists.
        if not user and db.query(User).count() == 0:
            if (
                config.ADMIN_PASSWORD
                and payload.username == config.ADMIN_USERNAME
                and hmac.compare_digest(payload.password.encode("utf-8"), config.ADMIN_PASSWORD.encode("utf-8"))
            ):
                record_login_success(client_ip, payload.username)
                token = create_token(payload.username)
                return {"token": token}

        if user and verify_password(payload.password, user.password_hash):
            if not is_bcrypt_hash(user.password_hash):
                # Transparent upgrade: this row was still holding the
                # pre-hashing plaintext value. Re-hash now that we've
                # verified the correct password was supplied.
                user.password_hash = hash_password(payload.password)
                db.commit()
            record_login_success(client_ip, payload.username)
            token = create_token(payload.username)
            return {"token": token}

        record_login_failure(client_ip, payload.username)
        raise HTTPException(status_code=401, detail="Invalid username or password")
    finally:
        db.close()

@app.get("/api/auth/validate")
async def validate_token():
    return {"status": "valid"}

@app.get("/api/auth/branding")
async def public_branding():
    """Returns the logo/branding paths without authentication so the
    Login page can display the company logo before the user signs in.
    Falls back to the default Pixous logo when no custom logo is uploaded."""
    profile = organization.load_profile()
    logo_path = profile.get("logo_path")
    # If no custom logo is set, use the bundled default so the login page
    # never falls back to the plain-text placeholder.
    if not logo_path:
        default_logo = organization.BRANDING_DIR / "logo_default.png"
        if default_logo.exists():
            logo_path = "logo_default.png"
    return {
        "logo_path": logo_path,
        "name": profile.get("name", "Pixous Technologies"),
    }

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    # Public endpoints that don't require a Bearer token
    PUBLIC_PATHS = {"/api/auth/login", "/api/auth/validate", "/api/auth/branding"}
    if path.startswith("/api") and path not in PUBLIC_PATHS and request.method != "OPTIONS":
        # Allow QA testing scripts (Postman/JMeter/k6) to authenticate via a
        # static API key instead of a Bearer token. This resolves to a real
        # identity (config.QA_TEST_USERNAME) rather than skipping
        # authorization entirely, so role-gated endpoints (require_role)
        # still enforce the same rules for QA traffic as for a logged-in
        # user. QA_TEST_API_KEY is empty by default - set it only in
        # QA/staging environments; leave it unset in production so this
        # header has no effect there.
        api_key = request.headers.get("X-API-Key")
        if api_key is not None:
            if config.QA_TEST_API_KEY and hmac.compare_digest(api_key, config.QA_TEST_API_KEY):
                request.state.qa_authenticated_username = config.QA_TEST_USERNAME
                return await call_next(request)
            return JSONResponse(status_code=401, content={"detail": "Invalid API Key or QA mode disabled."})

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized. Please log in."})
        token = auth_header.split(" ")[1]
        payload = decode_token(token)
        if not payload:
            return JSONResponse(status_code=401, content={"detail": "Session expired or invalid token."})

        db = SessionLocal()
        try:
            if not is_valid_username(payload.get("user"), db):
                return JSONResponse(status_code=401, content={"detail": "Account no longer exists or is inactive."})
        finally:
            db.close()

    response = await call_next(request)
    return response

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Pixous Technologies API",
        version="1.0.0",
        description="API with JWT and QA API Key authentication",
        routes=app.routes,
    )
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        }
    }
    
    PUBLIC_PATHS = {"/api/auth/login", "/api/auth/validate", "/api/auth/branding"}
    for path in openapi_schema.get("paths", {}):
        if path.startswith("/api") and path not in PUBLIC_PATHS:
            for method in openapi_schema["paths"][path]:
                openapi_schema["paths"][path][method]["security"] = [
                    {"BearerAuth": []},
                    {"ApiKeyAuth": []},
                ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi


# allow_credentials=False deliberately: auth is a Bearer token in the
# Authorization header (never a cookie - see client.ts, no `credentials:
# 'include'` anywhere), so there's nothing for a cross-site request to ride
# along automatically. That makes allow_origins=["*"] safe here; combining
# a wildcard origin with allow_credentials=True is what's dangerous
# (browsers refuse to reflect "*" with credentials anyway, but Starlette
# was reflecting the request's Origin verbatim instead, which defeats the
# same protection).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/branding", StaticFiles(directory=str(organization.BRANDING_DIR)), name="branding")

UPLOAD_DIR = Path(config.OUTPUT_DIR).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# (rate_card_overrides.json logic removed - database is now the single source of truth)

# ── Stage sequencing shown in the UI ──────────────────────────────────────────
# Maps the 8 stepper items in the UI to the pipeline's internal `current_stage`
# values. OCR is conditionally skipped for non-PDF inputs.
STEPS = [
    {"key": "ingestion", "label": "Ingestion", "done_stage": "ingested"},
    {"key": "ocr", "label": "OCR Processing", "done_stage": "ocr_complete"},
    {"key": "analysis", "label": "Analysis", "done_stage": "analysis_complete"},
    {"key": "estimation", "label": "Estimation", "done_stage": "estimation_complete"},
    {"key": "web_search", "label": "Web Research", "done_stage": "search_complete"},
    {"key": "brd", "label": "BRD Generation", "done_stage": "brd_complete"},
    {"key": "srs", "label": "SRS Generation", "done_stage": "srs_complete"},
    {"key": "quotation", "label": "Quotation", "done_stage": "quotation_complete"},
]
STEP_INDEX = {s["done_stage"]: i for i, s in enumerate(STEPS)}

JOBS: dict[str, dict] = {}


def _sanitize_filename(name: str) -> str:
    safe = re.sub(r"[^\w\s-]", "", name).strip()
    safe = re.sub(r"[\s]+", "_", safe)
    return safe[:50] or "project"


def _summarize(state: dict) -> dict:
    """Trim the full pipeline state down to what the dashboard needs."""
    analysis = state.get("project_analysis") or {}
    estimation = state.get("cost_estimation") or {}
    web = state.get("web_search_results") or {}
    return {
        "client_name": analysis.get("client_name", "Unspecified Client"),
        "project_name": analysis.get("project_name", ""),
        "project_type": analysis.get("project_type", ""),
        "project_description": analysis.get("project_description", ""),
        "tech_stack_suggested": analysis.get("tech_stack_suggested", []),
        "requirements": analysis.get("requirements", []),
        "assumptions": analysis.get("assumptions", []),
        "risks": analysis.get("risks", []),
        "out_of_scope": analysis.get("out_of_scope", []),
        "role_estimates": estimation.get("role_estimates", []),
        "category_breakdown": estimation.get("category_breakdown", []),
        "total_development_hours": estimation.get("total_development_hours", 0),
        "total_development_cost": estimation.get("total_development_cost", 0),
        "infrastructure_cost_monthly": estimation.get("infrastructure_cost_monthly", 0),
        "third_party_licenses_monthly": estimation.get("third_party_licenses_monthly", 0),
        "contingency_percentage": estimation.get("contingency_percentage", 0),
        "contingency_amount": estimation.get("contingency_amount", 0),
        "grand_total": estimation.get("grand_total", 0),
        "timeline_weeks": estimation.get("timeline_weeks", 0),
        "team_composition": estimation.get("team_composition", []),
        "phases": estimation.get("phases", []),
        "web_search_items": web.get("items", []),
        "has_brd": bool(state.get("brd_markdown")),
        "has_srs": bool(state.get("srs_markdown")),
        "has_quotation": bool(state.get("quotation_markdown")),
    }


async def _run_job(job_id: str, raw_input: str, generate_brd: bool, generate_srs: bool):
    job = JOBS[job_id]
    graph = build_pipeline()
    initial_state = {
        "raw_input": raw_input,
        "generate_brd": generate_brd,
        "generate_srs": generate_srs,
        "errors": [],
        "log": ["Pipeline started"],
        "current_stage": "initialized",
    }
    final_state: dict = {}
    try:
        job["status"] = "running"
        async for update in graph.astream(initial_state, stream_mode="values"):
            final_state = update
            stage = update.get("current_stage", "")
            if stage in STEP_INDEX:
                job["step_index"] = STEP_INDEX[stage]
            if stage.endswith("_failed"):
                job["status"] = "failed"
                job["error"] = "; ".join(update.get("errors", [])) or f"Failed at {stage}"
                job["log"] = update.get("log", [])
                return
            job["log"] = update.get("log", [])

        analysis = final_state.get("project_analysis", {})
        client_name = analysis.get("client_name", "Unspecified Client")
        client_slug = _sanitize_filename(client_name)
        project_name = _sanitize_filename(analysis.get("project_name", "project"))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"{client_slug}__{project_name}_{timestamp}"
        out_dir = Path(config.OUTPUT_DIR)
        profile = organization.load_profile()

        # Apply the letterhead once, up front, so every downstream reader
        # (live job view, saved file, data.json) sees the same lettered content.
        if final_state.get("quotation_markdown"):
            final_state["quotation_markdown"] = apply_letterhead(final_state["quotation_markdown"], profile)
        if final_state.get("brd_markdown"):
            final_state["brd_markdown"] = apply_letterhead(final_state["brd_markdown"], profile)
        if final_state.get("srs_markdown"):
            final_state["srs_markdown"] = apply_letterhead(final_state["srs_markdown"], profile)

        job["state"] = final_state
        job["result"] = _summarize(final_state)
        job["status"] = "complete"
        job["step_index"] = len(STEPS) - 1

        json_data = dict(final_state.get("quotation_json") or {})
        if json_data:
            json_data["client_name"] = client_name
            json_data["brd_markdown"] = final_state.get("brd_markdown", "")
            json_data["srs_markdown"] = final_state.get("srs_markdown", "")

        # Database save
        db = SessionLocal()
        try:
            client = db.query(Client).filter(Client.company_name == client_name).first()
            if not client:
                client = Client(company_name=client_name, created_at=datetime.now())
                db.add(client)
                db.commit()
                db.refresh(client)
            
            est_num = generate_next_serial("EST", db)
            estimation = Estimation(
                id=base_name,
                estimation_number=est_num,
                client_id=client.id,
                project_name=analysis.get("project_name", "project"),
                status="Completed",
                timeline_weeks=float(final_state.get("cost_estimation", {}).get("timeline_weeks", 0.0) or 0.0),
                grand_total=float(final_state.get("cost_estimation", {}).get("grand_total", 0.0) or 0.0),
                raw_pipeline_json=json_data,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(estimation)
            
            if final_state.get("quotation_markdown"):
                qut_num = generate_next_serial("QUT", db)
                doc = Document(
                    document_number=qut_num,
                    estimation_id=base_name,
                    type="quotation",
                    content=final_state["quotation_markdown"],
                    version=1,
                    created_at=datetime.now()
                )
                db.add(doc)
                
            if final_state.get("brd_markdown"):
                brd_num = generate_next_serial("BRD", db)
                doc = Document(
                    document_number=brd_num,
                    estimation_id=base_name,
                    type="brd",
                    content=final_state["brd_markdown"],
                    version=1,
                    created_at=datetime.now()
                )
                db.add(doc)
                
            if final_state.get("srs_markdown"):
                srs_num = generate_next_serial("SRS", db)
                doc = Document(
                    document_number=srs_num,
                    estimation_id=base_name,
                    type="srs",
                    content=final_state["srs_markdown"],
                    version=1,
                    created_at=datetime.now()
                )
                db.add(doc)
                
            db.commit()
        except Exception as db_err:
            db.rollback()
            print(f"Database save failed in run_job: {db_err}")
        finally:
            db.close()

        job["base_name"] = base_name

    except Exception as e:
        job["status"] = "failed"
        job["error"] = str(e)


@app.post("/api/jobs")
async def create_job(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    generate_brd: bool = Form(True),
    generate_srs: bool = Form(True),
):
    raw_input: Optional[str] = None

    if file is not None:
        suffix = Path(file.filename or "upload").suffix or ".txt"
        dest = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
        content = await file.read()
        dest.write_bytes(content)
        raw_input = str(dest.resolve())
    elif url:
        raw_input = url.strip()
    elif text:
        raw_input = text.strip()

    if not raw_input:
        raise HTTPException(400, "Provide a file, url, or text.")

    job_id = uuid.uuid4().hex
    JOBS[job_id] = {
        "id": job_id,
        "status": "queued",
        "step_index": -1,
        "steps": [s["label"] for s in STEPS],
        "log": [],
        "error": None,
        "source_name": file.filename if file else (url or (text[:60] if text else "")),
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    job_task = asyncio.create_task(_run_job(job_id, raw_input, generate_brd, generate_srs))
    JOBS[job_id]["_task"] = job_task
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {
        "id": job["id"],
        "status": job["status"],
        "step_index": job["step_index"],
        "steps": job["steps"],
        "log": job["log"][-20:],
        "error": job.get("error"),
        "source_name": job.get("source_name"),
        "result": job.get("result"),
        "base_name": job.get("base_name"),
        "created_at": job.get("created_at"),
    }


@app.get("/api/jobs/{job_id}/wait")
async def wait_for_job(job_id: str, timeout: int = 90):
    """
    Synchronously wait for a job to complete. 
    Useful for testing tools like JMeter that prefer a single blocking request over polling.
    Will return early if timeout is reached.
    """
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
        
    start_time = time.time()
    while True:
        if job["status"] in ("complete", "failed", "cancelled"):
            return {
                "id": job["id"],
                "status": job["status"],
                "step_index": job["step_index"],
                "error": job.get("error"),
                "result": job.get("result"),
                "base_name": job.get("base_name")
            }
            
        if time.time() - start_time > timeout:
            return {"id": job["id"], "status": "timeout", "message": f"Job still {job['status']} after {timeout} seconds"}
            
        await asyncio.sleep(2)


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] in ("complete", "failed", "cancelled"):
        raise HTTPException(400, f"Job is already {job['status']} and can't be cancelled.")

    task = job.get("_task")
    if task and not task.done():
        task.cancel()

    job["status"] = "cancelled"
    job["error"] = "Cancelled by user"
    return {"status": "cancelled"}


@app.get("/api/jobs/{job_id}/document/{doc_type}", response_class=PlainTextResponse)
async def get_job_document(job_id: str, doc_type: str):
    doc_type = doc_type.lower()
    job = JOBS.get(job_id)
    if not job or job.get("status") != "complete":
        raise HTTPException(404, "Job not ready")
    state = job.get("state", {})
    key = {"quotation": "quotation_markdown", "brd": "brd_markdown", "srs": "srs_markdown"}.get(doc_type)
    if not key:
        raise HTTPException(400, "Unknown document type")
    content = state.get(key, "")
    if not content:
        raise HTTPException(404, f"{doc_type} not generated for this job")
    return PlainTextResponse(content)


@app.get("/api/documents")
async def list_documents():
    db = SessionLocal()
    try:
        estimations = db.query(Estimation).filter(Estimation.is_deleted == False).order_by(Estimation.updated_at.desc()).all()
        if estimations:
            docs = []
            for est in estimations:
                client_name = est.client.company_name if est.client else "Unspecified Client"
                invoice_row = db.query(Invoice).filter(Invoice.estimation_id == est.id).order_by(Invoice.created_at.desc()).first()
                invoice_meta = None
                if invoice_row:
                    invoice_meta = {
                        "invoice_number": invoice_row.invoice_number,
                        "subtotal": invoice_row.subtotal,
                        "tax_amount": invoice_row.gst_amount,
                        "discount": invoice_row.discount,
                        "total_due": invoice_row.total,
                        "amount_paid": invoice_row.amount_paid,
                        "status": invoice_row.status,
                        "due_date": invoice_row.due_date.strftime("%Y-%m-%d") if invoice_row.due_date else None,
                        "paid_on": invoice_row.paid_on.strftime("%Y-%m-%d") if invoice_row.paid_on else None,
                        "payment_mode": invoice_row.payment_mode
                    }

                files_dict = {}
                db_docs = db.query(Document).filter(Document.estimation_id == est.id).all()
                for d in db_docs:
                    files_dict[d.type] = f"{est.id}_{d.type}.md"
                if invoice_row:
                    files_dict["invoice"] = f"{est.id}_invoice.html"
                if est.raw_pipeline_json:
                    files_dict["data"] = f"{est.id}_data.json"
                
                docs.append({
                    "base_name": est.id,
                    "project_name": est.project_name,
                    "client_name": client_name,
                    "files": files_dict,
                    "modified": est.updated_at.isoformat(),
                    "grand_total": est.grand_total,
                    "timeline_weeks": est.timeline_weeks,
                    "has_invoice": invoice_row is not None,
                    "invoice_meta": invoice_meta,
                    "invoice_created_at": invoice_row.created_at.isoformat() if invoice_row else None,
                    "version": est.version,
                })
            return {"documents": docs}
    except Exception as e:
        print(f"DB list_documents failed: {e}")
    finally:
        db.close()

    # Fallback to files
    out_dir = Path(config.OUTPUT_DIR)
    groups: dict[str, dict] = {}
    for f in sorted(out_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
        m = re.match(r"^(.*)_(quotation|brd|srs|data|invoice)\.(md|json|html)$", f.name)
        if not m:
            continue
        base, doc_type, _ext = m.groups()
        g = groups.setdefault(base, {"base_name": base, "files": {}, "modified": f.stat().st_mtime})
        g["files"][doc_type] = f.name
        g["modified"] = max(g["modified"], f.stat().st_mtime)

    docs = []
    for base, g in groups.items():
        project_name = base
        client_name = "Unspecified Client"
        grand_total = None
        timeline_weeks = None
        invoice_meta = None
        if "data" in g["files"]:
            try:
                data = json.loads((out_dir / g["files"]["data"]).read_text(encoding="utf-8"))
                project_name = data.get("project_name") or base
                client_name = data.get("client_name") or (data.get("analysis") or {}).get("client_name") or client_name
                est = data.get("cost_estimation") or {}
                grand_total = est.get("grand_total")
                timeline_weeks = est.get("timeline_weeks")
                invoice_meta = data.get("invoice_meta")
            except Exception:
                pass
        docs.append({
            "base_name": base,
            "project_name": project_name,
            "client_name": client_name,
            "files": g["files"],
            "modified": datetime.fromtimestamp(g["modified"]).isoformat(),
            "grand_total": grand_total,
            "timeline_weeks": timeline_weeks,
            "has_invoice": "invoice" in g["files"],
            "invoice_meta": invoice_meta,
        })
    docs.sort(key=lambda d: d["modified"], reverse=True)
    return {"documents": docs}


@app.get("/api/clients")
async def list_clients():
    docs = (await list_documents())["documents"]
    grouped: dict[str, list[dict]] = {}
    for d in docs:
        grouped.setdefault(d["client_name"], []).append(d)
    clients = [
        {
            "client_name": name,
            "estimations": estimations,
            "estimation_count": len(estimations),
            "latest_modified": max(e["modified"] for e in estimations),
        }
        for name, estimations in grouped.items()
    ]
    clients.sort(key=lambda c: c["latest_modified"], reverse=True)
    return {"clients": clients}


@app.get("/api/documents/{base_name}/data")
async def get_document_data(base_name: str):
    db = SessionLocal()
    try:
        est = db.query(Estimation).filter(Estimation.id == base_name).first()
        if est and est.raw_pipeline_json:
            data = dict(est.raw_pipeline_json)
            data["_has_quotation"] = db.query(Document).filter(Document.estimation_id == base_name, Document.type == "quotation").count() > 0
            data["_has_brd"] = db.query(Document).filter(Document.estimation_id == base_name, Document.type == "brd").count() > 0
            data["_has_srs"] = db.query(Document).filter(Document.estimation_id == base_name, Document.type == "srs").count() > 0
            return data
    except Exception as e:
        print(f"DB get_document_data failed: {e}")
    finally:
        db.close()

    # Legacy file fallback
    out_dir = Path(config.OUTPUT_DIR)
    path = out_dir / f"{base_name}_data.json"
    if not path.exists():
        raise HTTPException(404, "Document not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["_has_quotation"] = (out_dir / f"{base_name}_quotation.md").exists()
    data["_has_brd"] = (out_dir / f"{base_name}_brd.md").exists()
    data["_has_srs"] = (out_dir / f"{base_name}_srs.md").exists()
    return data


@app.get("/api/documents/{base_name}/{doc_type}", response_class=PlainTextResponse)
async def get_document_file(base_name: str, doc_type: str):
    doc_type = doc_type.lower()
    if doc_type not in ("quotation", "brd", "srs", "invoice"):
        raise HTTPException(400, "Unknown document type")
    
    db = SessionLocal()
    try:
        if doc_type == "invoice":
            inv = db.query(Invoice).filter(Invoice.estimation_id == base_name).order_by(Invoice.created_at.desc()).first()
            if inv and inv.invoice_html:
                return PlainTextResponse(inv.invoice_html, media_type="text/html")
        else:
            doc = db.query(Document).filter(Document.estimation_id == base_name, Document.type == doc_type).order_by(Document.version.desc()).first()
            if doc:
                return PlainTextResponse(doc.content, media_type="text/plain")
    except Exception as e:
        print(f"DB get_document_file failed: {e}")
    finally:
        db.close()

    # Fallback to local files
    ext = "html" if doc_type == "invoice" else "md"
    path = Path(config.OUTPUT_DIR) / f"{base_name}_{doc_type}.{ext}"
    if not path.exists():
        raise HTTPException(404, "Document not found")
    media_type = "text/html" if doc_type == "invoice" else "text/plain"
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type=media_type)


@app.get("/api/organization")
async def get_organization():
    return {"profile": organization.load_profile()}


EMAIL_RE = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
PHONE_RE = re.compile(r'^\d{10}$')
GSTIN_RE = re.compile(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$')


class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field("Your Company Name", max_length=255)
    tagline: Optional[str] = Field("", max_length=255)
    address: Optional[str] = Field("", max_length=300)
    email: Optional[str] = Field("", max_length=100)
    phone: Optional[str] = Field("", max_length=10)
    website: Optional[str] = Field("", max_length=100)
    gstin: Optional[str] = Field("", max_length=15)
    registration_number: Optional[str] = Field("", max_length=50)
    certifications: Optional[str] = Field("", max_length=500)
    signatory_name: Optional[str] = Field("", max_length=100)
    signatory_title: Optional[str] = Field("Authorized Signatory", max_length=100)
    bank_name: Optional[str] = Field("", max_length=100)
    bank_account_number: Optional[str] = Field("", max_length=30)
    bank_ifsc: Optional[str] = Field("", max_length=11)
    bank_branch: Optional[str] = Field("", max_length=100)
    invoice_terms: Optional[str] = Field("", max_length=2000)

    @field_validator(
        'name', 'tagline', 'address', 'email', 'phone', 'website',
        'gstin', 'registration_number', 'certifications', 'signatory_name',
        'signatory_title', 'bank_name', 'bank_account_number', 'bank_ifsc',
        'bank_branch', 'invoice_terms',
        mode='before'
    )
    @classmethod
    def coerce_none_to_str(cls, v):
        return v if v is not None else ""

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v and not EMAIL_RE.match(v):
            raise ValueError('Invalid email address')
        return v

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        if v and not PHONE_RE.match(v):
            raise ValueError('Phone number must be exactly 10 digits')
        return v

    @field_validator('gstin')
    @classmethod
    def validate_gstin(cls, v):
        if v and not GSTIN_RE.match(v.upper()):
            raise ValueError('Invalid GSTIN format (expected e.g. 22AAAAA0000A1Z5)')
        return v.upper() if v else v


@app.put("/api/organization")
async def update_organization(payload: OrganizationUpdate, request: Request):
    db = SessionLocal()
    try:
        require_role(request, db, {"Admin"})
    finally:
        db.close()
    profile = organization.save_profile(payload.model_dump())
    return {"profile": profile}


@app.post("/api/organization/apply-branding-history")
async def apply_branding_history(request: Request):
    db = SessionLocal()
    try:
        require_role(request, db, {"Admin"})
        profile = organization.load_profile()
        
        # Process Invoices
        dummy_html, _ = build_invoice({}, profile, "DUMMY")
        header_match = re.search(r'<header[^>]*>.*?</header>', dummy_html, re.DOTALL)
        footer_match = re.search(r'<footer[^>]*>.*?</footer>', dummy_html, re.DOTALL)
        
        if header_match and footer_match:
            new_header = header_match.group(0)
            new_footer = footer_match.group(0)
            
            invoices = db.query(Invoice).all()
            for inv in invoices:
                if inv.invoice_html:
                    html = inv.invoice_html
                    html = re.sub(r'<header[^>]*>.*?</header>', new_header, html, flags=re.DOTALL)
                    html = re.sub(r'<footer[^>]*>.*?</footer>', new_footer, html, flags=re.DOTALL)
                    # For older versions that used a different tag structure, we might not match.
                    inv.invoice_html = html
                    
        # Process Documents (Markdown)
        documents = db.query(Document).filter(Document.type.in_(["quotation", "brd", "srs"])).all()
        for doc in documents:
            if doc.content:
                lines = doc.content.split('\n')
                # Strip top
                for i in range(min(15, len(lines))):
                    if lines[i].strip() == '---':
                        lines = lines[i+1:]
                        break
                # Strip bottom
                for i in range(len(lines)-1, max(-1, len(lines)-15), -1):
                    if lines[i].strip() == '---':
                        lines = lines[:i]
                        break
                        
                stripped = '\n'.join(lines).strip()
                doc.content = apply_letterhead(stripped, profile)
                
        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Failed to apply branding history: {e}")
    finally:
        db.close()


@app.post("/api/organization/{slot}")
async def upload_organization_asset(slot: str, request: Request, file: UploadFile = File(...)):
    db = SessionLocal()
    try:
        require_role(request, db, {"Admin"})
    finally:
        db.close()
    if slot not in ("logo", "signature", "seal"):
        raise HTTPException(400, "Unknown branding asset slot")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds the 5MB limit.")
    try:
        profile = organization.save_branding_file(slot, file.filename or f"{slot}.png", content)
    except organization.InvalidBrandingAssetError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")
    return {"profile": profile}


@app.get("/api/debug/org-profile")
async def debug_org_profile():
    """Diagnostic endpoint — shows raw DB state of organization_profiles table."""
    try:
        from sqlalchemy import text as _text
        with engine.connect() as conn:
            rows = conn.execute(_text("SELECT * FROM organization_profiles")).mappings().all()
            return {"rows": [dict(r) for r in rows], "count": len(rows)}
    except Exception as e:
        return {"error": str(e)}


@app.delete("/api/organization/{slot}")
async def delete_organization_asset(slot: str, request: Request):
    db = SessionLocal()
    try:
        require_role(request, db, {"Admin"})
    finally:
        db.close()
    if slot not in ("logo", "signature", "seal"):
        raise HTTPException(400, "Unknown branding asset slot")
    profile = organization.remove_branding_file(slot)
    return {"profile": profile}


class ManualLineItem(BaseModel):
    description: str
    quantity: float = 1
    rate: float = 0


class ManualEstimationRequest(BaseModel):
    client_name: str
    project_name: str = "Manual Invoice"
    line_items: list[ManualLineItem]


@app.post("/api/estimations/manual")
async def create_manual_estimation(payload: ManualEstimationRequest):
    """Create a lightweight estimation record from hand-entered line items —
    for invoicing something that didn't go through the AI pipeline."""
    if not payload.line_items:
        raise HTTPException(400, "Add at least one line item")

    role_estimates = []
    grand_total = 0.0
    total_hours = 0.0
    for item in payload.line_items:
        amount = item.quantity * item.rate
        grand_total += amount
        total_hours += item.quantity
        role_estimates.append({
            "role_key": "manual",
            "role_label": item.description,
            "hours": item.quantity,
            "rate_per_hour": item.rate,
            "total_cost": amount,
        })

    client_slug = _sanitize_filename(payload.client_name)
    project_slug = _sanitize_filename(payload.project_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{client_slug}__{project_slug}_{timestamp}"

    data = {
        "client_name": payload.client_name,
        "project_name": payload.project_name,
        "analysis": {"client_name": payload.client_name, "project_name": payload.project_name},
        "cost_estimation": {
            "role_estimates": role_estimates,
            "category_breakdown": [],
            "total_development_hours": total_hours,
            "total_development_cost": grand_total,
            "infrastructure_cost_monthly": 0,
            "third_party_licenses_monthly": 0,
            "contingency_percentage": 0,
            "contingency_amount": 0,
            "grand_total": grand_total,
            "timeline_weeks": 0,
        },
        "is_manual": True,
    }

    # Save in DB
    db = SessionLocal()
    try:
        client = db.query(Client).filter(Client.company_name == payload.client_name).first()
        if not client:
            client = Client(company_name=payload.client_name, created_at=datetime.now())
            db.add(client)
            db.commit()
            db.refresh(client)
            
        est_num = generate_next_serial("EST", db)
        estimation = Estimation(
            id=base_name,
            estimation_number=est_num,
            client_id=client.id,
            project_name=payload.project_name,
            status="Completed",
            timeline_weeks=0.0,
            grand_total=grand_total,
            raw_pipeline_json=data,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(estimation)
        db.commit()
    except Exception as db_err:
        db.rollback()
        print(f"DB create_manual_estimation failed: {db_err}")
    finally:
        db.close()

    return {"base_name": base_name}


class InvoiceRequest(BaseModel):
    tax_percentage: float = 18.0
    due_days: int = 15


@app.post("/api/estimations/{base_name}/invoice")
async def generate_invoice(base_name: str, payload: InvoiceRequest):
    # Fetch from database first
    db = SessionLocal()
    data = None
    try:
        est = db.query(Estimation).filter(Estimation.id == base_name).first()
        if est and est.raw_pipeline_json:
            data = dict(est.raw_pipeline_json)
    except Exception as e:
        print(f"DB generate_invoice read failed: {e}")
    finally:
        db.close()

    # Fallback to file read if DB load failed/empty
    if not data:
        out_dir = Path(config.OUTPUT_DIR)
        data_path = out_dir / f"{base_name}_data.json"
        if not data_path.exists():
            raise HTTPException(404, "Estimation not found")
        data = json.loads(data_path.read_text(encoding="utf-8"))

    db = SessionLocal()
    html, meta = None, None
    try:
        invoice_number = generate_next_serial("INV", db)
        profile = organization.load_profile()
        html, meta = build_invoice(
            data,
            profile,
            invoice_number=invoice_number,
            tax_percentage=payload.tax_percentage,
            due_days=payload.due_days,
        )
        
        # Calculate totals
        subtotal = float(meta.get("subtotal", 0.0))
        gst_amount = float(meta.get("tax_amount", 0.0))
        total = float(meta.get("total_due", 0.0))
        
        due_date_str = meta.get("due_date", "")
        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
        except Exception:
            due_date = datetime.now() + timedelta(days=payload.due_days)

        # Check if invoice already exists for this estimation
        inv = db.query(Invoice).filter(Invoice.estimation_id == base_name).first()
        if not inv:
            inv = Invoice(
                invoice_number=invoice_number,
                estimation_id=base_name,
                subtotal=subtotal,
                gst_amount=gst_amount,
                discount=0.0,
                total=total,
                status="Draft",
                due_date=due_date,
                invoice_html=html,
                created_at=datetime.now()
            )
            db.add(inv)
        else:
            inv.subtotal = subtotal
            inv.gst_amount = gst_amount
            inv.total = total
            inv.due_date = due_date
            inv.invoice_html = html
            inv.created_at = datetime.now()
        
        # Update estimation metadata
        est = db.query(Estimation).filter(Estimation.id == base_name).first()
        if est:
            if est.raw_pipeline_json:
                raw_json = dict(est.raw_pipeline_json)
                raw_json["invoice_html"] = html
                raw_json["invoice_meta"] = meta
                est.raw_pipeline_json = raw_json
        
        db.commit()
    except Exception as db_err:
        db.rollback()
        print(f"DB generate_invoice save failed: {db_err}")
        # Fallback local generation if DB failed
        profile = organization.load_profile()
        invoice_number = f"INV-{datetime.now().strftime('%Y%m%d')}-manual"
        html, meta = build_invoice(
            data,
            profile,
            invoice_number=invoice_number,
            tax_percentage=payload.tax_percentage,
            due_days=payload.due_days,
        )
    finally:
        db.close()

    return {"invoice_html": html, "invoice_meta": meta}


@app.get("/api/estimations/{base_name}/invoice")
async def get_invoice(base_name: str):
    db = SessionLocal()
    try:
        inv = db.query(Invoice).filter(Invoice.estimation_id == base_name).order_by(Invoice.created_at.desc()).first()
        if inv:
            meta = {
                "invoice_number": inv.invoice_number,
                "subtotal": inv.subtotal,
                "tax_amount": inv.gst_amount,
                "discount": inv.discount,
                "total_due": inv.total,
                "status": inv.status,
                "due_date": inv.due_date.strftime("%Y-%m-%d") if inv.due_date else None,
                "paid_on": inv.paid_on.strftime("%Y-%m-%d") if inv.paid_on else None,
                "payment_mode": inv.payment_mode
            }
            return {"invoice_html": inv.invoice_html, "invoice_meta": meta}
    except Exception as e:
        print(f"DB get_invoice failed: {e}")
    finally:
        db.close()

    # Fallback to local files
    out_dir = Path(config.OUTPUT_DIR)
    path = out_dir / f"{base_name}_invoice.html"
    data_path = out_dir / f"{base_name}_data.json"
    if not path.exists() or not data_path.exists():
        raise HTTPException(404, "Invoice not generated yet")
    data = json.loads(data_path.read_text(encoding="utf-8"))
    return {"invoice_html": path.read_text(encoding="utf-8"), "invoice_meta": data.get("invoice_meta")}


INVOICE_STATUSES = ("Draft", "Sent", "Paid", "Overdue", "Cancelled")
_STATUS_COLORS = {
    "Draft": ("#FEF3C7", "#92400E"),
    "Sent": ("#DBEAFE", "#1E40AF"),
    "Paid": ("#DCFCE7", "#166534"),
    "Overdue": ("#FEE2E2", "#991B1B"),
    "Cancelled": ("#E2E8F0", "#475569"),
}


class InvoiceStatusUpdate(BaseModel):
    status: str
    amount_paid: Optional[float] = None
    paid_on: Optional[str] = None



@app.put("/api/estimations/{base_name}/invoice/status")
async def update_invoice_status(base_name: str, payload: InvoiceStatusUpdate, request: Request):
    if payload.status not in INVOICE_STATUSES:
        raise HTTPException(400, f"Status must be one of {INVOICE_STATUSES}")

    db = SessionLocal()
    meta = None
    new_html = None
    try:
        require_role(request, db, {"Admin", "Finance"})
        inv = db.query(Invoice).filter(Invoice.estimation_id == base_name).order_by(Invoice.created_at.desc()).first()
        if inv:
            inv.status = payload.status
            if payload.amount_paid is not None:
                inv.amount_paid = payload.amount_paid
            
            if payload.paid_on:
                inv.paid_on = datetime.strptime(payload.paid_on, "%Y-%m-%d")
            elif payload.status == "Paid":
                inv.paid_on = datetime.now()
                if not inv.amount_paid or inv.amount_paid < inv.total:
                    inv.amount_paid = inv.total
            else:
                inv.paid_on = None
            
            # Since amount_paid and paid_on affect the table structure (adding new rows),
            # we need to rebuild the invoice HTML to properly display them.
            est = db.query(Estimation).filter(Estimation.id == base_name).first()
            if est and est.raw_pipeline_json:
                from invoice_builder import build_invoice
                data = dict(est.raw_pipeline_json)
                profile = organization.load_profile()
                tax_percentage = (inv.gst_amount / inv.subtotal * 100) if inv.subtotal > 0 else 18.0
                due_days = (inv.due_date - inv.created_at).days if inv.due_date and inv.created_at else 15
                
                html, _ = build_invoice(
                    data,
                    profile,
                    invoice_number=inv.invoice_number,
                    tax_percentage=tax_percentage,
                    due_days=due_days,
                    invoice_date=inv.created_at.isoformat() if inv.created_at else None,
                    status=inv.status,
                    amount_paid=inv.amount_paid or 0.0,
                    paid_on=inv.paid_on.strftime("%b %d, %Y") if inv.paid_on else None
                )
                inv.invoice_html = html
            
            new_html = inv.invoice_html
            # Update estimation metadata
            est = db.query(Estimation).filter(Estimation.id == base_name).first()
            if est and est.raw_pipeline_json:
                raw_json = dict(est.raw_pipeline_json)
                meta = raw_json.get("invoice_meta") or {}
                meta["status"] = payload.status
                if payload.status == "Paid":
                    meta["paid_on"] = datetime.now().strftime("%Y-%m-%d")
                else:
                    meta["paid_on"] = None
                raw_json["invoice_meta"] = meta
                raw_json["invoice_html"] = new_html
                est.raw_pipeline_json = raw_json

            db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"DB update_invoice_status failed: {e}")
    finally:
        db.close()

    if not meta or not new_html:
        raise HTTPException(404, "Invoice not found or failed to update")

    return {"invoice_meta": meta, "invoice_html": new_html}

    return {"invoice_meta": meta, "invoice_html": new_html}


class DocumentContentUpdate(BaseModel):
    content: str


@app.put("/api/documents/{base_name}/{doc_type}")
async def update_document_content(base_name: str, doc_type: str, payload: DocumentContentUpdate):
    doc_type = doc_type.lower()
    if doc_type not in ("quotation", "brd", "srs", "invoice"):
        raise HTTPException(400, "Unknown document type")

    db = SessionLocal()
    try:
        if doc_type == "invoice":
            inv = db.query(Invoice).filter(Invoice.estimation_id == base_name).order_by(Invoice.created_at.desc()).first()
            if inv:
                inv.invoice_html = strip_script_vectors(payload.content)
                db.commit()
        else:
            latest_doc = db.query(Document).filter(
                Document.estimation_id == base_name, Document.type == doc_type
            ).order_by(Document.version.desc()).first()
            
            next_version = (latest_doc.version + 1) if latest_doc else 1
            doc_num = generate_next_serial(doc_type.upper()[:3], db)
            
            new_doc = Document(
                document_number=doc_num,
                estimation_id=base_name,
                type=doc_type,
                content=payload.content,
                version=next_version,
                created_at=datetime.now()
            )
            db.add(new_doc)
            
            # Update estimation timestamp and cached state
            est = db.query(Estimation).filter(Estimation.id == base_name).first()
            if est:
                est.updated_at = datetime.now()
                if est.raw_pipeline_json:
                    raw_json = dict(est.raw_pipeline_json)
                    raw_json[f"{doc_type}_markdown"] = payload.content
                    est.raw_pipeline_json = raw_json
                    
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"DB update_document_content failed: {e}")
    finally:
        db.close()

    return {"content": payload.content}


@app.get("/api/test-pdf")
def test_pdf():
    import pdf_builder
    try:
        res = pdf_builder.html_to_pdf('<html><body>hello</body></html>')
        return {"status": "success", "len": len(res)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/documents/{base_name}/{doc_type}/pdf")
def download_document_pdf(base_name: str, doc_type: str):
    doc_type = doc_type.lower()
    if doc_type not in ("quotation", "brd", "srs", "invoice"):
        raise HTTPException(400, "Unknown document type")
    
    content = None
    db = SessionLocal()
    try:
        if doc_type == "invoice":
            inv = db.query(Invoice).filter(Invoice.estimation_id == base_name).order_by(Invoice.created_at.desc()).first()
            if inv:
                content = inv.invoice_html
        else:
            doc = db.query(Document).filter(
                Document.estimation_id == base_name, Document.type == doc_type
            ).order_by(Document.version.desc()).first()
            if doc:
                content = doc.content
    except Exception as e:
        print(f"DB download_document_pdf failed: {e}")
    finally:
        db.close()

    if not content:
        # Fallback to local files
        ext = "html" if doc_type == "invoice" else "md"
        path = Path(config.OUTPUT_DIR) / f"{base_name}_{doc_type}.{ext}"
        if not path.exists():
            raise HTTPException(404, "Document not found")
        content = path.read_text(encoding="utf-8")

    pdf_bytes = html_to_pdf(content) if doc_type == "invoice" else markdown_to_pdf(content)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{base_name}_{doc_type}.pdf"'},
    )


@app.get("/api/analytics")
async def get_analytics():
    docs = (await list_documents())["documents"]
    now = datetime.now()
    today_key = now.strftime("%Y-%m-%d")
    month_key = now.strftime("%Y-%m")

    total_project_value = 0.0
    today_count = 0
    month_count = 0
    status_overview: dict[str, int] = {}
    revenue_paid = 0.0
    revenue_pending = 0.0
    invoiced_count = 0

    for d in docs:
        modified = d["modified"]
        if modified.startswith(today_key):
            today_count += 1
        if modified.startswith(month_key):
            month_count += 1
        total_project_value += d.get("grand_total") or 0

        meta = d.get("invoice_meta")
        if d.get("has_invoice") and meta:
            invoiced_count += 1
            status = meta.get("status", "Draft")
            status_overview[status] = status_overview.get(status, 0) + 1
            if status == "Paid":
                revenue_paid += meta.get("total_due", 0)
            else:
                revenue_pending += meta.get("total_due", 0)
        else:
            status_overview["Not Invoiced"] = status_overview.get("Not Invoiced", 0) + 1

    total_estimations = len(docs)
    invoiced_docs = [d for d in docs if d.get("has_invoice")]
    recent_invoices = sorted(
        invoiced_docs,
        key=lambda d: d.get("invoice_created_at") or "",
        reverse=True,
    )[:8]
    return {
        "total_estimations": total_estimations,
        "today_count": today_count,
        "month_count": month_count,
        "total_project_value": total_project_value,
        "average_estimation_value": (total_project_value / total_estimations) if total_estimations else 0,
        "invoiced_count": invoiced_count,
        "revenue_paid": revenue_paid,
        "revenue_pending": revenue_pending,
        "status_overview": status_overview,
        "recent": docs[:8],
        "recent_invoices": recent_invoices,
    }


@app.get("/api/rate-card")
async def get_rate_card():
    return {"rates": config.DEVELOPER_RATES}


class RateCardUpdate(BaseModel):
    rates: dict[str, dict]


@app.put("/api/rate-card")
async def update_rate_card(payload: RateCardUpdate, request: Request):
    db = SessionLocal()
    try:
        require_role(request, db, {"Admin"})
        
        # Handle additions and updates
        for key, value in payload.rates.items():
            new_rate = value.get("rate_per_hour")
            new_label = value.get("label", key)
            if new_rate is not None:
                # Deactivate current active rate if it exists and changed
                current_active = db.query(RateCard).filter(
                    RateCard.role_key == key, RateCard.is_active == True
                ).first()
                
                if current_active:
                    if current_active.rate_per_hour != new_rate or current_active.role_label != new_label:
                        current_active.is_active = False
                        current_active.effective_to = datetime.now()
                        
                        # Create new rate card entry
                        new_db_rate = RateCard(
                            role_key=key,
                            role_label=new_label,
                            rate_per_hour=new_rate,
                            effective_from=datetime.now(),
                            is_active=True
                        )
                        db.add(new_db_rate)
                else:
                    new_db_rate = RateCard(
                        role_key=key,
                        role_label=new_label,
                        rate_per_hour=new_rate,
                        effective_from=datetime.now(),
                        is_active=True
                    )
                    db.add(new_db_rate)
                
                config.DEVELOPER_RATES[key] = {
                    "rate_per_hour": new_rate,
                    "label": new_label,
                    "is_custom": key not in config.SYSTEM_ROLE_KEYS
                }
                
        # Handle deletions (any active role not in payload)
        active_roles = db.query(RateCard).filter(
            RateCard.is_active == True
        ).all()
        for role in active_roles:
            if role.role_key not in payload.rates:
                role.is_active = False
                role.effective_to = datetime.now()
                config.DEVELOPER_RATES.pop(role.role_key, None)

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"DB update_rate_card failed: {e}")
    finally:
        db.close()

    return {"rates": config.DEVELOPER_RATES}


@app.get("/api/config/status")
async def config_status():
    return {
        "mistral_ready": bool(config.MISTRAL_API_KEY),
        "groq_ready": len(config.GROQ_API_KEYS) > 0,
        "gemini_ready": len(config.GEMINI_API_KEYS) > 0,
    }


@app.get("/api/health")
async def health():
    return {"status": "ok"}


def get_current_username(request: Request) -> str:
    """Extracts the calling identity, re-verifying the bearer token's HMAC
    signature and the underlying account's existence here rather than
    trusting that auth_middleware already ran (defense in depth - this used
    to decode the payload unverified and silently fall back to "admin" on
    any parse error, a fail-open trap).

    Requests authenticated via the QA X-API-Key (see auth_middleware) carry
    no Authorization header at all; they resolve to config.QA_TEST_USERNAME
    via request.state instead, so role-gated endpoints behave identically
    for QA tooling and for a real Bearer-token login."""
    qa_username = getattr(request.state, "qa_authenticated_username", None)
    if qa_username:
        return qa_username

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized. Please log in.")
    token = auth_header.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Session expired or invalid token.")
    username = payload.get("user")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token payload.")

    db = SessionLocal()
    try:
        if not is_valid_username(username, db):
            raise HTTPException(status_code=401, detail="Account no longer exists or is inactive.")
    finally:
        db.close()
    return username


def get_current_role(request: Request, db) -> str:
    """Resolves the calling user's role. Falls back to 'Admin' only for the
    bootstrap admin username (no matching User row) - the same identity the
    login endpoint itself trusts before any user account exists. Any other
    username with a validly-signed token but no matching row gets the
    least-privileged role rather than defaulting to admin access."""
    username = get_current_username(request)
    user_row = db.query(User).filter(User.username == username).first()
    if user_row:
        return user_row.role or "Admin"
    if username == config.ADMIN_USERNAME:
        return "Admin"
    return "Developer"


def require_role(request: Request, db, allowed_roles: set[str]) -> str:
    role = get_current_role(request, db)
    if role not in allowed_roles:
        raise HTTPException(status_code=403, detail="You do not have permission to perform this action.")
    return role


@app.patch("/api/estimations/{id}")
async def patch_estimation(id: str, payload: EstimationPatch, request: Request):
    db = SessionLocal()
    try:
        # Admin-only: this endpoint can rewrite grand_total/timeline_weeks,
        # the same financial fields delete_estimation and the rest of the
        # mutating endpoints in this file already gate on role.
        require_role(request, db, {"Admin"})
        est = db.query(Estimation).filter(Estimation.id == id, Estimation.is_deleted == False).first()
        if not est:
            raise HTTPException(status_code=404, detail="Estimation not found")
        
        # Optimistic locking check
        if est.version != payload.version:
            raise HTTPException(status_code=409, detail="Conflict: Estimation version has changed. Please refresh the page.")
        
        username = get_current_username(request)
        user_row = db.query(User).filter(User.username == username).first()
        user_id = user_row.id if user_row else None
        
        # Track changed fields
        changes = {}
        if payload.project_name is not None and est.project_name != payload.project_name:
            changes["project_name"] = {"before": est.project_name, "after": payload.project_name}
            est.project_name = payload.project_name
            
        if payload.timeline_weeks is not None and est.timeline_weeks != payload.timeline_weeks:
            changes["timeline_weeks"] = {"before": est.timeline_weeks, "after": payload.timeline_weeks}
            est.timeline_weeks = payload.timeline_weeks
            
        if payload.grand_total is not None and est.grand_total != payload.grand_total:
            changes["grand_total"] = {"before": est.grand_total, "after": payload.grand_total}
            est.grand_total = payload.grand_total
            
        if changes:
            est.version += 1
            est.updated_at = datetime.utcnow()
            
            # Save audit log
            from db import AuditLog
            audit = AuditLog(
                user_id=user_id,
                action="UPDATE_ESTIMATION",
                details=json.dumps({
                    "estimation_id": est.id,
                    "estimation_number": est.estimation_number,
                    "changes": changes
                }),
                timestamp=datetime.utcnow()
            )
            db.add(audit)
            db.commit()
            db.refresh(est)
            
        return {
            "id": est.id,
            "project_name": est.project_name,
            "timeline_weeks": est.timeline_weeks,
            "grand_total": est.grand_total,
            "version": est.version,
            "updated_at": est.updated_at.isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception("patch_estimation failed")
        raise HTTPException(status_code=500, detail="Failed to update estimation.")
    finally:
        db.close()


@app.delete("/api/estimations/{id}")
async def delete_estimation(id: str, request: Request):
    db = SessionLocal()
    try:
        require_role(request, db, {"Admin"})
        est = db.query(Estimation).filter(
            (Estimation.id == id) | (Estimation.estimation_number == id),
            Estimation.is_deleted == False
        ).first()
        if not est:
            raise HTTPException(status_code=404, detail="Estimation not found")

        username = get_current_username(request)
        user_row = db.query(User).filter(User.username == username).first()
        user_id = user_row.id if user_row else None
        
        est.is_deleted = True
        est.deleted_at = datetime.utcnow()
        
        # Save audit log
        from db import AuditLog
        audit = AuditLog(
            user_id=user_id,
            action="DELETE_ESTIMATION",
            details=json.dumps({
                "estimation_id": est.id,
                "estimation_number": est.estimation_number,
                "project_name": est.project_name
            }),
            timestamp=datetime.utcnow()
        )
        db.add(audit)
        db.commit()
        return {"status": "success", "message": f"Estimation {est.estimation_number} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception("delete_estimation failed")
        raise HTTPException(status_code=500, detail="Failed to delete estimation.")
    finally:
        db.close()


@app.patch("/api/invoices/{id}")
async def patch_invoice(id: str, payload: InvoicePatch, request: Request):
    db = SessionLocal()
    try:
        # Admin-only: this endpoint can set status="Paid", the same effect
        # PUT /api/estimations/{base_name}/invoice/status restricts to
        # Admin/Finance - gate it here too so the two paths agree.
        require_role(request, db, {"Admin"})
        inv = db.query(Invoice).filter(Invoice.id == id).first()
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
            
        username = get_current_username(request)
        user_row = db.query(User).filter(User.username == username).first()
        user_id = user_row.id if user_row else None
        
        changes = {}
        if payload.subtotal is not None and inv.subtotal != payload.subtotal:
            changes["subtotal"] = {"before": inv.subtotal, "after": payload.subtotal}
            inv.subtotal = payload.subtotal
            
        if payload.gst_amount is not None and inv.gst_amount != payload.gst_amount:
            changes["gst_amount"] = {"before": inv.gst_amount, "after": payload.gst_amount}
            inv.gst_amount = payload.gst_amount
            
        if payload.discount is not None and inv.discount != payload.discount:
            changes["discount"] = {"before": inv.discount, "after": payload.discount}
            inv.discount = payload.discount
            
        if payload.total is not None and inv.total != payload.total:
            changes["total"] = {"before": inv.total, "after": payload.total}
            inv.total = payload.total
            
        if payload.status is not None and inv.status != payload.status:
            changes["status"] = {"before": inv.status, "after": payload.status}
            inv.status = payload.status
            if payload.status == "Paid":
                inv.paid_on = datetime.utcnow()
                if not inv.amount_paid or inv.amount_paid < inv.total:
                    changes["amount_paid"] = {"before": inv.amount_paid, "after": inv.total}
                    inv.amount_paid = inv.total
            elif payload.status == "Draft":
                inv.paid_on = None

        if payload.amount_paid is not None and inv.amount_paid != payload.amount_paid:
            changes["amount_paid"] = {"before": inv.amount_paid, "after": payload.amount_paid}
            inv.amount_paid = payload.amount_paid

        if payload.paid_on is not None:
            try:
                new_paid_on = datetime.fromisoformat(payload.paid_on.replace("Z", "+00:00")) if "T" in payload.paid_on else datetime.strptime(payload.paid_on, "%Y-%m-%d")
                if inv.paid_on != new_paid_on:
                    changes["paid_on"] = {"before": inv.paid_on.isoformat() if inv.paid_on else None, "after": new_paid_on.isoformat() if new_paid_on else None}
                    inv.paid_on = new_paid_on
            except ValueError:
                pass

        if changes:
            # Save audit log
            from db import AuditLog
            from invoice_builder import build_invoice
            
            # Regenerate invoice HTML if needed
            est = db.query(Estimation).filter(Estimation.id == inv.estimation_id).first()
            if est and est.raw_pipeline_json:
                data = dict(est.raw_pipeline_json)
                profile = organization.load_profile()
                tax_percentage = (inv.gst_amount / inv.subtotal * 100) if inv.subtotal > 0 else 18.0
                due_days = (inv.due_date - inv.created_at).days if inv.due_date and inv.created_at else 15
                
                html, meta = build_invoice(
                    data,
                    profile,
                    invoice_number=inv.invoice_number,
                    tax_percentage=tax_percentage,
                    due_days=due_days,
                    invoice_date=inv.created_at.isoformat() if inv.created_at else None,
                    status=inv.status,
                    amount_paid=inv.amount_paid or 0.0,
                    paid_on=inv.paid_on.strftime("%b %d, %Y") if inv.paid_on else None
                )
                inv.invoice_html = html

            audit = AuditLog(
                user_id=user_id,
                action="UPDATE_INVOICE",
                details=json.dumps({
                    "invoice_id": inv.id,
                    "invoice_number": inv.invoice_number,
                    "changes": changes
                }),
                timestamp=datetime.utcnow()
            )
            db.add(audit)
            db.commit()
            db.refresh(inv)
            
        return {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "subtotal": inv.subtotal,
            "gst_amount": inv.gst_amount,
            "discount": inv.discount,
            "total": inv.total,
            "amount_paid": inv.amount_paid,
            "status": inv.status,
            "paid_on": inv.paid_on.isoformat() if inv.paid_on else None
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception("patch_invoice failed")
        raise HTTPException(status_code=500, detail="Failed to update invoice.")
    finally:
        db.close()


@app.delete("/api/invoices/{invoice_number}")
async def delete_invoice(invoice_number: str, request: Request):
    db = SessionLocal()
    try:
        require_role(request, db, {"Admin"})
        
        inv = db.query(Invoice).filter(Invoice.invoice_number == invoice_number).first()
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
            
        estimation_id = inv.estimation_id
        db.delete(inv)
        db.flush()
        
        # Check if there are any other invoices for this estimation
        remaining = db.query(Invoice).filter(Invoice.estimation_id == estimation_id).count()
        if remaining == 0:
            est = db.query(Estimation).filter(Estimation.id == estimation_id).first()
            if est and est.status == "Invoiced":
                est.status = "Approved"
                
        db.commit()
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception("delete_invoice failed")
        raise HTTPException(status_code=500, detail="Failed to delete invoice.")
    finally:
        db.close()



# Serve the built React app (frontend/dist) for every non-API route, so the
# SPA's client-side router (React Router) handles the path. Mounted last so
# it never shadows the /api/* routes or /branding static files above.
FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="frontend-assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        dist_root = FRONTEND_DIST.resolve()
        candidate = (dist_root / full_path).resolve()
        if full_path and candidate.is_relative_to(dist_root) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist_root / "index.html")
