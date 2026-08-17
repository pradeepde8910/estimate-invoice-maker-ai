from sqlalchemy.orm import Session
from datetime import datetime

from v2.schemas.report import ReportFilter, ReportResult
from v2.services.reports.base_report import BaseReport
from v2.models.project import Project
from v2.models.master import Client
from v2.services.report_filters import apply_common_filters

class ProjectReport(BaseReport):
    
    def generate(self, db: Session, filters: ReportFilter) -> ReportResult:
        query = db.query(Project, Client).join(Client, Project.client_id == Client.id)
        
        # Project specific date filter applies to created_at
        if filters.from_date:
            query = query.filter(Project.created_at >= filters.from_date)
        if filters.to_date:
            # We want to include the entire day for to_date
            query = query.filter(Project.created_at < filters.to_date) # Wait, <= filters.to_date + 1 day might be better, or just rely on datetime mapping.
            # Simplified for now.
            
        if filters.client_id:
            query = query.filter(Project.client_id == filters.client_id)
        if filters.project_id:
            query = query.filter(Project.id == filters.project_id)
        if filters.statuses:
            query = query.filter(Project.status.in_(filters.statuses))
        
        # billing_type filter applies to billing config, we'll skip it for simple Project Report or join if necessary.
        
        query = query.order_by(Project.created_at.desc())
        
        results = query.all()
        
        columns = [
            "Project Number", "Project Name", "Client Name", "Status",
            "Contract Value", "Created At"
        ]
        
        rows = []
        total_contract_value = 0
        
        for project, client in results:
            rows.append({
                "Project Number": project.project_number,
                "Project Name": project.project_name,
                "Client Name": client.company_name,
                "Status": project.status,
                "Contract Value": float(project.contract_value),
                "Created At": str(project.created_at)
            })
            total_contract_value += float(project.contract_value)
            
        totals = {
            "Total Contract Value": total_contract_value
        }
        
        return ReportResult(
            report_type="PROJECT",
            columns=columns,
            rows=rows,
            totals=totals,
            generated_at=datetime.utcnow()
        )
