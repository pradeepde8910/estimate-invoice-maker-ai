"""
Estimation job orchestration — runs the LangGraph pipeline (app/agents/)
asynchronously and tracks progress in an in-memory registry.

This is a faithful port of v1/api.py's job machinery (_run_job, STEPS,
JOBS), not a new "queue" — it's still an in-process dict + asyncio task,
same as before. A real distributed queue (Celery/Redis) is a deliberate
non-goal here; if that's ever needed, this module's public surface
(create_job/get_job/wait_for_job/cancel_job) is what a real queue-backed
implementation would replace, without the API routers needing to change.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import asyncio
import time

from fastapi import HTTPException, UploadFile

from app import config
from app.agents.graph import build_pipeline
from app.core.database import SessionLocal, generate_next_serial
from app.models.master import Client
from app.models.estimation import Estimation, Document
from app.utils import organization
from app.utils.letterhead import apply_letterhead

UPLOAD_DIR = Path(config.OUTPUT_DIR).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

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
        "estimation_assumptions": estimation.get("estimation_assumptions", []),
        "web_search_items": web.get("items", []),
        "has_brd": bool(state.get("brd_markdown")),
        "has_srs": bool(state.get("srs_markdown")),
        "has_quotation": bool(state.get("quotation_markdown")),
        "quotation_validation": state.get("quotation_validation", {}),
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
        client_info = analysis.get("client", {})
        client_name_for_file = client_info.get("company_name") or client_info.get("contact_person") or "Unspecified Client"
        client_slug = _sanitize_filename(client_name_for_file)
        project_name = _sanitize_filename(analysis.get("project_name", "project"))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"{client_slug}__{project_name}_{timestamp}"
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
        job["step_index"] = len(STEPS) - 1

        json_data = dict(final_state.get("quotation_json") or {})
        if json_data:
            json_data["client_info"] = client_info
            json_data["brd_markdown"] = final_state.get("brd_markdown", "")
            json_data["srs_markdown"] = final_state.get("srs_markdown", "")

        # Database save
        db = SessionLocal()
        try:
            # Only match if there is a company name
            client = db.query(Client).filter(Client.company_name == client_info.get("company_name")).first() if client_info.get("company_name") else None
            if not client:
                client = Client(
                    company_name=client_info.get("company_name"),
                    contact_person=client_info.get("contact_person"),
                    email=client_info.get("email"),
                    phone=client_info.get("phone"),
                    billing_address=client_info.get("billing_address"),
                    gstin=client_info.get("gstin"),
                    status="DRAFT",
                    created_at=datetime.now()
                )
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
                db.add(Document(
                    document_number=qut_num, estimation_id=base_name, type="quotation",
                    content=final_state["quotation_markdown"], version=1, created_at=datetime.now()
                ))

            if final_state.get("brd_markdown"):
                brd_num = generate_next_serial("BRD", db)
                db.add(Document(
                    document_number=brd_num, estimation_id=base_name, type="brd",
                    content=final_state["brd_markdown"], version=1, created_at=datetime.now()
                ))

            if final_state.get("srs_markdown"):
                srs_num = generate_next_serial("SRS", db)
                db.add(Document(
                    document_number=srs_num, estimation_id=base_name, type="srs",
                    content=final_state["srs_markdown"], version=1, created_at=datetime.now()
                ))

            db.commit()
            job["status"] = "complete"
        except Exception as db_err:
            db.rollback()
            print(f"Database save failed in run_job: {db_err}")
            job["status"] = "failed"
            job["error"] = f"Failed to save estimation to database: {db_err}"
        finally:
            db.close()

        job["base_name"] = base_name

    except Exception as e:
        job["status"] = "failed"
        job["error"] = str(e)


async def create_job(
    file: Optional[UploadFile],
    url: Optional[str],
    text: Optional[str],
    generate_brd: bool,
    generate_srs: bool,
) -> str:
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
    return job_id


def get_job_status(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    result = job.get("result")
    # `result` is a snapshot captured once, when the pipeline finished — it
    # never changes afterward, so a client identity confirmed/edited via
    # ClientDetailsEditor (which writes straight to the DB) would otherwise
    # never be reflected here even after re-fetching the job. Overlay the
    # live DB record on every read instead.
    if result and job.get("base_name"):
        db = SessionLocal()
        try:
            est = db.query(Estimation).filter(Estimation.id == job["base_name"]).first()
            if est and est.client:
                result = dict(result)
                result["client_info"] = {
                    "company_name": est.client.company_name,
                    "contact_person": est.client.contact_person,
                    "email": est.client.email,
                    "phone": est.client.phone,
                    "billing_address": est.client.billing_address,
                    "gstin": est.client.gstin,
                    "status": est.client.status,
                }
        except Exception as e:
            print(f"DB get_job client_info refresh failed: {e}")
        finally:
            db.close()

    return {
        "id": job["id"],
        "status": job["status"],
        "step_index": job["step_index"],
        "steps": job["steps"],
        "log": job["log"][-20:],
        "error": job.get("error"),
        "source_name": job.get("source_name"),
        "result": result,
        "base_name": job.get("base_name"),
        "created_at": job.get("created_at"),
    }


async def wait_for_job(job_id: str, timeout: int = 90) -> dict:
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


def cancel_job(job_id: str) -> dict:
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


def get_job_document(job_id: str, doc_type: str) -> str:
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
    return content
