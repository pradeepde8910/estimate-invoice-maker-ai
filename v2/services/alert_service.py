import logging
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_, and_

from v2.models.alert import Alert
from v2.models.project import ProjectMilestone
from v2.models.invoice import Invoice

logger = logging.getLogger(__name__)

def evaluate_daily_alerts(db: Session, current_date: date = None):
    if current_date is None:
        current_date = datetime.utcnow().date()
        
    # 1. Milestone Alerts: 3 Days Before Due
    target_milestone_date = current_date + timedelta(days=3)
    milestones = db.query(ProjectMilestone).filter(
        ProjectMilestone.status == "PENDING",
        ProjectMilestone.due_date != None
    ).all()
    
    for m in milestones:
        if m.due_date.date() == target_milestone_date:
            alert = Alert(
                entity_type="MILESTONE",
                entity_id=m.id,
                alert_rule="3_DAYS_BEFORE_DUE",
                message=f"Milestone '{m.name}' is due in 3 days."
            )
            db.add(alert)
            try:
                db.commit()
            except IntegrityError:
                db.rollback() # Duplicate ignored
                
    # 2. Invoice Alerts: Overdue Rules
    invoices = db.query(Invoice).filter(
        Invoice.status == "ISSUED",
        Invoice.payment_status != "PAID",
        Invoice.due_date != None
    ).all()
    
    for inv in invoices:
        if inv.due_date.date() >= current_date:
            continue # Not overdue yet
            
        delta = current_date - inv.due_date.date()
        days_overdue = delta.days
        
        rule = None
        message = ""
        
        if days_overdue == 1:
            rule = "OVERDUE"
            message = f"Invoice {inv.invoice_number} is now overdue."
        elif days_overdue == 7:
            rule = "7_DAYS_OVERDUE"
            message = f"Invoice {inv.invoice_number} is 7 days overdue."
        elif days_overdue == 15:
            rule = "15_DAYS_OVERDUE"
            message = f"Invoice {inv.invoice_number} is 15 days overdue."
        elif days_overdue == 30:
            rule = "30_DAYS_OVERDUE"
            message = f"Invoice {inv.invoice_number} is 30 days overdue. Please follow up immediately."
            
        if rule:
            alert = Alert(
                entity_type="INVOICE",
                entity_id=inv.id,
                alert_rule=rule,
                message=message
            )
            db.add(alert)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()

# Dummy email sender for the worker
class EmailDeliveryError(Exception):
    pass

def simulate_send_email(to: str, message: str):
    # In tests, we might monkey-patch this or mock it
    pass

def process_triggered_alerts(db: Session, max_retries: int = 3):
    now = datetime.utcnow()
    
    alerts_to_process = db.query(Alert).filter(
        or_(
            Alert.status == "TRIGGERED",
            and_(
                Alert.status == "FAILED",
                Alert.next_retry_at <= now,
                Alert.attempt_count < max_retries
            )
        )
    ).all()
    
    for alert in alerts_to_process:
        alert.last_attempt_at = now
        alert.attempt_count += 1
        
        try:
            # Look up the target email (simplified for now)
            # In a real app, join entity to get client email.
            simulate_send_email("client@example.com", alert.message)
            
            alert.status = "SENT"
            alert.sent_at = now
            alert.failure_reason = None
            db.commit()
            
        except Exception as e:
            alert.status = "FAILED"
            alert.failure_reason = str(e)
            if alert.attempt_count < max_retries:
                # Exponential backoff: 1hr, 2hr, 4hr, etc.
                backoff_hours = 2 ** (alert.attempt_count - 1)
                alert.next_retry_at = now + timedelta(hours=backoff_hours)
            db.commit()
