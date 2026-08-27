from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import date
from typing import Optional

from app.database import get_db
from app.api.dependencies import require_roles
from app.services.alert_service import evaluate_daily_alerts, process_triggered_alerts

router = APIRouter(prefix="/alerts", tags=["Alerts (Admin/Ops)"])

@router.post("/evaluate")
def trigger_evaluation(
    eval_date: Optional[date] = None, 
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin"))
):
    """
    Manually triggers the daily evaluator.
    Normally invoked by a cron scheduler.
    """
    try:
        evaluate_daily_alerts(db, current_date=eval_date)
        return {"status": "success", "message": "Evaluation completed."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process")
def trigger_processing(
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin"))
):
    """
    Manually triggers the delivery worker.
    Normally invoked by a frequent cron or queue.
    """
    try:
        process_triggered_alerts(db)
        return {"status": "success", "message": "Processing completed."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
