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
import os
import re
import tempfile
import uuid
import hmac
import hashlib
import time
import base64
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

import config
from agents.graph import build_pipeline
from invoice_builder import build_invoice
from letterhead import apply_letterhead
from pdf_builder import markdown_to_pdf, html_to_pdf
import organization
from db import init_db, SessionLocal, User, Client, Estimation, Document, Invoice, generate_next_serial

app = FastAPI(title="Pixous Technologies API")

@app.on_event("startup")
def startup_event():
    init_db()

# --- Token helpers for authentication ---
def create_token(username: str) -> str:
    # Token valid for 24 hours
    exp = int(time.time()) + 86400
    payload = {"user": username, "exp": exp}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signature = hmac.new(config.JWT_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"

def verify_token(token: str) -> bool:
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return False
        payload_b64, signature = parts
        expected_signature = hmac.new(config.JWT_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            return False
        
        padding = "=" * (4 - len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64 + padding).decode()
        payload = json.loads(payload_json)
        if int(time.time()) > payload.get("exp", 0):
            return False
        return True
    except Exception:
        return False

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

    @field_validator('subtotal', 'gst_amount', 'discount', 'total')
    @classmethod
    def validate_positive(cls, v):
        if v is not None and v < 0:
            raise ValueError("Value must be non-negative")
        return v

@app.post("/api/auth/login")
async def login_endpoint(payload: LoginRequest):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == payload.username).first()
        # Fallback to config defaults if no users exist in the DB
        if not user and db.query(User).count() == 0:
            if payload.username == config.ADMIN_USERNAME and payload.password == config.ADMIN_PASSWORD:
                token = create_token(payload.username)
                return {"token": token}
        
        # If user exists, check password hash
        if user and user.password_hash == payload.password:
            token = create_token(payload.username)
            return {"token": token}
            
        raise HTTPException(status_code=401, detail="Invalid username or password")
    finally:
        db.close()

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    # Exclude login, static branding files, and preflight requests (OPTIONS)
    if path.startswith("/api") and path != "/api/auth/login" and request.method != "OPTIONS":
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized. Please log in."})
        token = auth_header.split(" ")[1]
        if not verify_token(token):
            return JSONResponse(status_code=401, content={"detail": "Session expired or invalid token."})
            
    response = await call_next(request)
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/branding", StaticFiles(directory=str(organization.BRANDING_DIR)), name="branding")

UPLOAD_DIR = Path(config.OUTPUT_DIR).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

RATE_CARD_OVERRIDES_PATH = Path(__file__).parent / "rate_card_overrides.json"
if RATE_CARD_OVERRIDES_PATH.exists():
    try:
        overrides = json.loads(RATE_CARD_OVERRIDES_PATH.read_text(encoding="utf-8"))
        config.DEVELOPER_RATES.update(overrides)
    except Exception:
        pass

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
        "created_at": datetime.now().isoformat(),
    }
    asyncio.create_task(_run_job(job_id, raw_input, generate_brd, generate_srs))
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
    }


@app.get("/api/jobs/{job_id}/document/{doc_type}", response_class=PlainTextResponse)
async def get_job_document(job_id: str, doc_type: str):
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


class OrganizationUpdate(BaseModel):
    name: str = "Your Company Name"
    tagline: str = ""
    address: str = ""
    email: str = ""
    phone: str = ""
    website: str = ""
    gstin: str = ""
    registration_number: str = ""
    certifications: str = ""
    signatory_name: str = ""
    signatory_title: str = "Authorized Signatory"
    bank_name: str = ""
    bank_account_number: str = ""
    bank_ifsc: str = ""
    bank_branch: str = ""


@app.put("/api/organization")
async def update_organization(payload: OrganizationUpdate):
    profile = organization.save_profile(payload.model_dump())
    return {"profile": profile}


@app.post("/api/organization/{slot}")
async def upload_organization_asset(slot: str, file: UploadFile = File(...)):
    if slot not in ("logo", "signature", "seal"):
        raise HTTPException(400, "Unknown branding asset slot")
    content = await file.read()
    profile = organization.save_branding_file(slot, file.filename or f"{slot}.png", content)
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


@app.put("/api/estimations/{base_name}/invoice/status")
async def update_invoice_status(base_name: str, payload: InvoiceStatusUpdate):
    if payload.status not in INVOICE_STATUSES:
        raise HTTPException(400, f"Status must be one of {INVOICE_STATUSES}")

    db = SessionLocal()
    meta = None
    new_html = None
    try:
        inv = db.query(Invoice).filter(Invoice.estimation_id == base_name).order_by(Invoice.created_at.desc()).first()
        if inv:
            inv.status = payload.status
            if payload.status == "Paid":
                inv.paid_on = datetime.now()
            else:
                inv.paid_on = None
            
            # Update HTML badge in DB
            bg, fg = _STATUS_COLORS.get(payload.status, _STATUS_COLORS["Draft"])
            content = inv.invoice_html or ""
            new_content, count = re.subn(
                r'(<div class="badge" style="background:)[^;]+;color:[^;"]+;("[^>]*>)[^<]*(</div>)',
                rf"\g<1>{bg};color:{fg};\g<2>{payload.status}\g<3>",
                content,
            )
            if count:
                inv.invoice_html = new_content
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
    if doc_type not in ("quotation", "brd", "srs", "invoice"):
        raise HTTPException(400, "Unknown document type")

    db = SessionLocal()
    try:
        if doc_type == "invoice":
            inv = db.query(Invoice).filter(Invoice.estimation_id == base_name).order_by(Invoice.created_at.desc()).first()
            if inv:
                inv.invoice_html = payload.content
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


@app.get("/api/documents/{base_name}/{doc_type}/pdf")
async def download_document_pdf(base_name: str, doc_type: str):
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
    }


@app.get("/api/rate-card")
async def get_rate_card():
    return {"rates": config.DEVELOPER_RATES}


class RateCardUpdate(BaseModel):
    rates: dict[str, dict]


@app.put("/api/rate-card")
async def update_rate_card(payload: RateCardUpdate):
    db = SessionLocal()
    try:
        for key, value in payload.rates.items():
            if key in config.DEVELOPER_RATES:
                new_rate = value.get("rate_per_hour")
                if new_rate is not None:
                    # Deactivate current active rate
                    current_active = db.query(RateCard).filter(
                        RateCard.role_key == key, RateCard.is_active == True
                    ).first()
                    
                    if current_active:
                        if current_active.rate_per_hour != new_rate:
                            current_active.is_active = False
                            current_active.effective_to = datetime.now()
                            
                            # Create new rate card entry
                            new_db_rate = RateCard(
                                role_key=key,
                                role_label=config.DEVELOPER_RATES[key]["label"],
                                rate_per_hour=new_rate,
                                effective_from=datetime.now(),
                                is_active=True
                            )
                            db.add(new_db_rate)
                    else:
                        new_db_rate = RateCard(
                            role_key=key,
                            role_label=config.DEVELOPER_RATES[key]["label"],
                            rate_per_hour=new_rate,
                            effective_from=datetime.now(),
                            is_active=True
                        )
                        db.add(new_db_rate)
                    
                    config.DEVELOPER_RATES[key]["rate_per_hour"] = new_rate
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"DB update_rate_card failed: {e}")
    finally:
        db.close()

    try:
        RATE_CARD_OVERRIDES_PATH.write_text(
            json.dumps(config.DEVELOPER_RATES, indent=2), encoding="utf-8"
        )
    except Exception:
        pass

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
    try:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            parts = token.split(".")
            if len(parts) == 2:
                payload_b64 = parts[0]
                padding = "=" * (4 - len(payload_b64) % 4)
                payload_json = base64.urlsafe_b64decode(payload_b64 + padding).decode()
                payload = json.loads(payload_json)
                return payload.get("user") or "admin"
    except Exception:
        pass
    return "admin"


@app.patch("/api/estimations/{id}")
async def patch_estimation(id: str, payload: EstimationPatch, request: Request):
    db = SessionLocal()
    try:
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
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.delete("/api/estimations/{id}")
async def delete_estimation(id: str, request: Request):
    db = SessionLocal()
    try:
        est = db.query(Estimation).filter(Estimation.id == id, Estimation.is_deleted == False).first()
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
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.patch("/api/invoices/{id}")
async def patch_invoice(id: str, payload: InvoicePatch, request: Request):
    db = SessionLocal()
    try:
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
            else:
                inv.paid_on = None
                
        if changes:
            # Save audit log
            from db import AuditLog
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
            "status": inv.status,
            "paid_on": inv.paid_on.isoformat() if inv.paid_on else None
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
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
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
