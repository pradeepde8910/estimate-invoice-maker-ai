import json
import logging
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

from app.api.dependencies import require_roles
from app.core.database import SessionLocal, generate_next_serial
from app.models.audit import AuditLog
from app.models.estimation import Estimation
from app.models.master import Client
from app.models.user import User

router = APIRouter()
logger = logging.getLogger("pixous.api")

GSTIN_RE = re.compile(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$')


def _sanitize_filename(name: str) -> str:
    safe = re.sub(r"[^\w\s-]", "", name).strip()
    safe = re.sub(r"[\s]+", "_", safe)
    return safe[:50] or "project"


class ManualLineItem(BaseModel):
    description: str
    quantity: float = 1
    rate: float = 0


class ManualEstimationRequest(BaseModel):
    client_name: str
    project_name: str = "Manual Invoice"
    line_items: list[ManualLineItem]


@router.post("/api/estimations/manual")
async def create_manual_estimation(
    payload: ManualEstimationRequest,
    user: User = Depends(require_roles("Admin", "Developer")),
):
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
        raise HTTPException(500, f"Failed to save manual estimation: {db_err}")
    finally:
        db.close()

    return {"base_name": base_name}


# NOTE: v1 also had endpoints here for generating/reading/updating an
# invoice directly attached to an estimation (pre-project-conversion). That
# used a simpler, flat Invoice shape (subtotal/gst_amount/total/status/
# due_date/paid_on/payment_mode/invoice_html on one row keyed by
# estimation_id) that's incompatible with — and would collide with — the
# real V2 Invoice model (project-attached, with separate InvoiceTax/
# InvoiceTDS/Payment tables and a DRAFT/ISSUED/CANCELLED + payment_status
# vocabulary). Deliberately dropped rather than ported: the supported flow
# is now Approve estimation -> Convert to Project -> create invoice, which
# is what this app's invoicing (billing types, PDF rendering, payments) was
# actually built and tested against.


class EstimationClientPatch(BaseModel):
    company_name: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    billing_address: Optional[str] = None
    gstin: Optional[str] = None
    status: Optional[str] = None

    @field_validator('gstin')
    @classmethod
    def validate_gstin(cls, v):
        if v and not GSTIN_RE.match(v.upper()):
            raise ValueError('Invalid GSTIN format (expected e.g. 22AAAAA0000A1Z5)')
        return v.upper() if v else v


@router.patch("/api/estimations/{id}/client")
async def patch_estimation_client(
    id: str,
    payload: EstimationClientPatch,
    request: Request,
    user: User = Depends(require_roles("Admin", "Developer")),
):
    db = SessionLocal()
    try:
        est = db.query(Estimation).filter(Estimation.id == id, Estimation.is_deleted == False).first()
        if not est:
            raise HTTPException(status_code=404, detail="Estimation not found")

        client = db.query(Client).filter(Client.id == est.client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        changes = {}
        for field in ["company_name", "contact_person", "email", "phone", "billing_address", "gstin", "status"]:
            new_val = getattr(payload, field)
            old_val = getattr(client, field)
            if new_val is not None and new_val != old_val:
                changes[f"client_{field}"] = {"before": old_val, "after": new_val}
                setattr(client, field, new_val)

        if changes:
            audit = AuditLog(
                user_id=user.id,
                action="UPDATE_ESTIMATION_CLIENT",
                details=json.dumps({
                    "estimation_id": est.id,
                    "entity_type": "CLIENT",
                    "entity_id": client.id,
                    "changes": changes,
                    "ip_address": request.client.host if request.client else None
                })
            )
            db.add(audit)
            db.commit()
            db.refresh(client)

        return {"status": "success", "client_id": client.id}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


class EstimationPatch(BaseModel):
    project_name: Optional[str] = None
    timeline_weeks: Optional[float] = None
    grand_total: Optional[float] = None
    status: Optional[str] = None
    version: int

    @field_validator('timeline_weeks', 'grand_total')
    @classmethod
    def validate_positive(cls, v):
        if v is not None and v < 0:
            raise ValueError("Value must be non-negative")
        return v


@router.patch("/api/estimations/{id}")
async def patch_estimation(
    id: str,
    payload: EstimationPatch,
    user: User = Depends(require_roles("Admin")),
):
    db = SessionLocal()
    try:
        est = db.query(Estimation).filter(Estimation.id == id, Estimation.is_deleted == False).first()
        if not est:
            raise HTTPException(status_code=404, detail="Estimation not found")

        if est.version != payload.version:
            raise HTTPException(status_code=409, detail="Conflict: Estimation version has changed. Please refresh the page.")

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

        if payload.status is not None and est.status != payload.status:
            changes["status"] = {"before": est.status, "after": payload.status}
            est.status = payload.status

        if changes:
            est.version += 1
            est.updated_at = datetime.utcnow()

            audit = AuditLog(
                user_id=user.id,
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
    except Exception:
        db.rollback()
        logger.exception("patch_estimation failed")
        raise HTTPException(status_code=500, detail="Failed to update estimation.")
    finally:
        db.close()


@router.delete("/api/estimations/{id}")
async def delete_estimation(id: str, user: User = Depends(require_roles("Admin"))):
    db = SessionLocal()
    try:
        est = db.query(Estimation).filter(
            (Estimation.id == id) | (Estimation.estimation_number == id),
            Estimation.is_deleted == False
        ).first()
        if not est:
            raise HTTPException(status_code=404, detail="Estimation not found")

        est.is_deleted = True
        est.deleted_at = datetime.utcnow()

        audit = AuditLog(
            user_id=user.id,
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
    except Exception:
        db.rollback()
        logger.exception("delete_estimation failed")
        raise HTTPException(status_code=500, detail="Failed to delete estimation.")
    finally:
        db.close()
