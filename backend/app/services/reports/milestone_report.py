from sqlalchemy.orm import Session
from datetime import datetime

from app.schemas.report import ReportFilter, ReportResult
from app.services.reports.base_report import BaseReport
from app.models.project import Project, ProjectMilestone
from app.models.master import Client

class MilestoneReport(BaseReport):
    
    def generate(self, db: Session, filters: ReportFilter) -> ReportResult:
        query = db.query(ProjectMilestone, Project, Client).join(
            Project, ProjectMilestone.project_id == Project.id
        ).join(
            Client, Project.client_id == Client.id
        )
        
        if filters.from_date:
            query = query.filter(ProjectMilestone.due_date >= filters.from_date)
        if filters.to_date:
            query = query.filter(ProjectMilestone.due_date <= filters.to_date)
            
        if filters.client_id:
            query = query.filter(Project.client_id == filters.client_id)
        if filters.project_id:
            query = query.filter(ProjectMilestone.project_id == filters.project_id)
        if filters.statuses:
            query = query.filter(ProjectMilestone.status.in_(filters.statuses))
            
        query = query.order_by(ProjectMilestone.due_date.asc().nullslast())
        
        results = query.all()
        
        columns = [
            "Milestone Name", "Project Name", "Client Name", "Status",
            "Due Date", "Amount"
        ]
        
        rows = []
        total_amount = 0
        
        for ms, project, client in results:
            rows.append({
                "Milestone Name": ms.name,
                "Project Name": project.project_name,
                "Client Name": client.company_name,
                "Status": ms.status,
                "Due Date": str(ms.due_date.date()) if ms.due_date else "",
                "Amount": float(ms.amount)
            })
            total_amount += float(ms.amount)
            
        totals = {
            "Total Milestone Amount": total_amount
        }
        
        return ReportResult(
            report_type="MILESTONE",
            columns=columns,
            rows=rows,
            totals=totals,
            generated_at=datetime.utcnow()
        )
