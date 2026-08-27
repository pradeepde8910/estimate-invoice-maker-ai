from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import joinedload

from app import config
from app.api.dependencies import require_roles
from app.core.database import SessionLocal
from app.models.estimation import Estimation
from app.models.user import User

router = APIRouter()


@router.get("/api/health")
async def health():
    return {"status": "ok"}


@router.get("/api/config/status")
async def config_status(user: User = Depends(require_roles("Admin"))):
    return {
        "mistral_ready": bool(config.MISTRAL_API_KEY),
        "gemini_ready": len(config.GEMINI_API_KEYS) > 0,
    }


@router.get("/api/analytics")
async def get_analytics(user: User = Depends(require_roles("Admin", "Developer", "Finance"))):
    db = SessionLocal()
    try:
        # joinedload(Estimation.client): est.client is accessed below after
        # this session closes to build `recent` — without eager-loading it
        # here, that's a lazy-load on a detached instance (DetachedInstanceError),
        # which only surfaces once there's real data to iterate (an empty
        # estimations list never touches .client, which is why this passed
        # every test run against an empty test DB).
        estimations = (
            db.query(Estimation)
            .options(joinedload(Estimation.client))
            .filter(Estimation.is_deleted == False)
            .order_by(Estimation.updated_at.desc())
            .all()
        )
    finally:
        db.close()

    now = datetime.now()
    today_key = now.strftime("%Y-%m-%d")
    month_key = now.strftime("%Y-%m")

    total_project_value = 0.0
    today_count = 0
    month_count = 0

    for est in estimations:
        modified = est.updated_at.isoformat()
        if modified.startswith(today_key):
            today_count += 1
        if modified.startswith(month_key):
            month_count += 1
        total_project_value += est.grand_total or 0

    total_estimations = len(estimations)
    recent = [
        {
            "base_name": est.id,
            "project_name": est.project_name,
            "client_name": est.client.company_name if est.client else "Unspecified Client",
            "modified": est.updated_at.isoformat(),
            "grand_total": est.grand_total,
        }
        for est in estimations[:8]
    ]

    return {
        "total_estimations": total_estimations,
        "today_count": today_count,
        "month_count": month_count,
        "total_project_value": total_project_value,
        "average_estimation_value": (total_project_value / total_estimations) if total_estimations else 0,
        "recent": recent,
    }
