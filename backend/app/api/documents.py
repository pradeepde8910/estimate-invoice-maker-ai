import json
import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import PlainTextResponse

from app import config
from app.api.dependencies import require_roles
from app.core.database import SessionLocal
from app.models.estimation import Estimation, Document
from app.models.user import User
from app.services.estimation_excel_exporter import build_full_workbook, build_timeline_workbook
from app.utils.pdf_builder import markdown_to_pdf

router = APIRouter()


def _safe_output_path(filename: str) -> Path:
    """Resolves filename against OUTPUT_DIR and rejects any path-traversal
    escape (e.g. a `base_name` path parameter containing "../../etc/passwd")
    before the caller ever opens it."""
    out_dir = Path(config.OUTPUT_DIR).resolve()
    candidate = (out_dir / filename).resolve()
    try:
        candidate.relative_to(out_dir)
    except ValueError:
        raise HTTPException(400, "Invalid document identifier")
    return candidate


@router.get("/api/documents")
async def list_documents(user: User = Depends(require_roles("Admin", "Developer", "Finance"))):
    db = SessionLocal()
    try:
        estimations = db.query(Estimation).filter(Estimation.is_deleted == False).order_by(Estimation.updated_at.desc()).all()
        if estimations:
            docs = []
            for est in estimations:
                client_name = est.client.company_name if est.client else "Unspecified Client"

                files_dict = {}
                db_docs = db.query(Document).filter(Document.estimation_id == est.id).all()
                for d in db_docs:
                    files_dict[d.type] = f"{est.id}_{d.type}.md"
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
        m = re.match(r"^(.*)_(quotation|brd|srs|data)\.(md|json)$", f.name)
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
        if "data" in g["files"]:
            try:
                data = json.loads((out_dir / g["files"]["data"]).read_text(encoding="utf-8"))
                project_name = data.get("project_name") or base
                client_name = data.get("client_name") or (data.get("analysis") or {}).get("client_name") or client_name
                est_data = data.get("cost_estimation") or {}
                grand_total = est_data.get("grand_total")
                timeline_weeks = est_data.get("timeline_weeks")
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
        })
    docs.sort(key=lambda d: d["modified"], reverse=True)
    return {"documents": docs}


@router.get("/api/documents/{base_name}/data")
async def get_document_data(base_name: str, user: User = Depends(require_roles("Admin", "Developer", "Finance"))):
    db = SessionLocal()
    try:
        est = db.query(Estimation).filter(Estimation.id == base_name).first()
        if est and est.raw_pipeline_json:
            data = dict(est.raw_pipeline_json)
            data["_has_quotation"] = db.query(Document).filter(Document.estimation_id == base_name, Document.type == "quotation").count() > 0
            data["_has_brd"] = db.query(Document).filter(Document.estimation_id == base_name, Document.type == "brd").count() > 0
            data["_has_srs"] = db.query(Document).filter(Document.estimation_id == base_name, Document.type == "srs").count() > 0
            data["status"] = est.status
            data["converted_project_id"] = est.converted_project_id
            data["version"] = est.version
            if est.client:
                data["client_info"] = {
                    "company_name": est.client.company_name,
                    "contact_person": est.client.contact_person,
                    "email": est.client.email,
                    "phone": est.client.phone,
                    "billing_address": est.client.billing_address,
                    "gstin": est.client.gstin,
                    "status": est.client.status,
                }
            return data
    except Exception as e:
        print(f"DB get_document_data failed: {e}")
    finally:
        db.close()

    # Legacy file fallback
    path = _safe_output_path(f"{base_name}_data.json")
    if not path.exists():
        raise HTTPException(404, "Document not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["_has_quotation"] = _safe_output_path(f"{base_name}_quotation.md").exists()
    data["_has_brd"] = _safe_output_path(f"{base_name}_brd.md").exists()
    data["_has_srs"] = _safe_output_path(f"{base_name}_srs.md").exists()
    return data


def _load_estimation_export_data(base_name: str, db) -> tuple[dict, Estimation]:
    """
    Shared lookup for both Excel export endpoints below. Only supports
    DB-backed estimations (unlike get_document_data, no legacy-file
    fallback) — the Excel export is a new feature with no pre-existing
    file-based estimations that would need it.
    """
    est = db.query(Estimation).filter(Estimation.id == base_name).first()
    if not est or not est.raw_pipeline_json:
        raise HTTPException(404, "Estimation not found or has no pipeline data")
    data = dict(est.raw_pipeline_json)
    data["status"] = est.status
    data["version"] = est.version
    return data, est


@router.get("/api/documents/{base_name}/excel")
def download_estimation_excel(base_name: str, user: User = Depends(require_roles("Admin", "Developer", "Finance"))):
    """Complete multi-sheet estimation workbook — overview, timeline (with
    Gantt chart), cost breakdowns, requirements, task-level detail, team,
    infrastructure/license costs, and risks/assumptions, each with charts
    where there's something worth visualizing.

    Registered here (before the generic /{base_name}/{doc_type} route just
    below) so FastAPI's path matching — first route registered whose
    pattern matches wins — doesn't let that wildcard swallow "/excel" as a
    doc_type value before this specific route ever gets a chance."""
    db = SessionLocal()
    try:
        data, est = _load_estimation_export_data(base_name, db)
        workbook_bytes = build_full_workbook(data, est, est.client)
    finally:
        db.close()

    return Response(
        content=workbook_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{base_name}_estimation.xlsx"'},
    )


@router.get("/api/documents/{base_name}/timeline/excel")
def download_estimation_timeline_excel(base_name: str, user: User = Depends(require_roles("Admin", "Developer", "Finance"))):
    """Standalone timeline-only workbook (phases + Gantt chart), for when
    just the schedule is needed rather than the full estimation."""
    db = SessionLocal()
    try:
        data, est = _load_estimation_export_data(base_name, db)
        workbook_bytes = build_timeline_workbook(data, est)
    finally:
        db.close()

    return Response(
        content=workbook_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{base_name}_timeline.xlsx"'},
    )


@router.get("/api/documents/{base_name}/{doc_type}", response_class=PlainTextResponse)
async def get_document_file(
    base_name: str,
    doc_type: str,
    user: User = Depends(require_roles("Admin", "Developer", "Finance")),
):
    doc_type = doc_type.lower()
    if doc_type not in ("quotation", "brd", "srs"):
        raise HTTPException(400, "Unknown document type")

    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.estimation_id == base_name, Document.type == doc_type).order_by(Document.version.desc()).first()
        if doc:
            return PlainTextResponse(doc.content, media_type="text/plain")
    except Exception as e:
        print(f"DB get_document_file failed: {e}")
    finally:
        db.close()

    # Fallback to local files
    path = _safe_output_path(f"{base_name}_{doc_type}.md")
    if not path.exists():
        raise HTTPException(404, "Document not found")
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/plain")


@router.get("/api/documents/{base_name}/{doc_type}/pdf")
def download_document_pdf(
    base_name: str,
    doc_type: str,
    user: User = Depends(require_roles("Admin", "Developer", "Finance")),
):
    doc_type = doc_type.lower()
    if doc_type not in ("quotation", "brd", "srs"):
        raise HTTPException(400, "Unknown document type")

    content = None
    db = SessionLocal()
    try:
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
        path = _safe_output_path(f"{base_name}_{doc_type}.md")
        if not path.exists():
            raise HTTPException(404, "Document not found")
        content = path.read_text(encoding="utf-8")

    pdf_bytes = markdown_to_pdf(content)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{base_name}_{doc_type}.pdf"'},
    )
