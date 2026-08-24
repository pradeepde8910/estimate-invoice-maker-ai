from datetime import datetime, timedelta

from sqlalchemy.orm import Session, joinedload

from app.schemas.report import ReportFilter, ReportResult
from app.services.reports.base_report import BaseReport
from app.models.project import Project, ProjectBillingConfig
from app.models.master import Client, BillingType
from app.services.report_filters import apply_common_filters

class ProjectReport(BaseReport):

    def generate(self, db: Session, filters: ReportFilter) -> ReportResult:
        query = db.query(Project).join(Client, Project.client_id == Client.id)
        query = query.options(
            joinedload(Project.client),
            joinedload(Project.billing_config).joinedload(ProjectBillingConfig.billing_type),
        )

        # Project specific date filter applies to created_at. to_date is a
        # calendar day, so it must include everything up to (but not
        # including) the start of the next day — a plain `<=` against a
        # midnight `date` would exclude every project created later that day.
        if filters.from_date:
            query = query.filter(Project.created_at >= filters.from_date)
        if filters.to_date:
            query = query.filter(Project.created_at < filters.to_date + timedelta(days=1))

        query = apply_common_filters(query, filters, Project, date_column=None)

        # Project.billing_type is a computed @property (via ProjectBillingConfig),
        # not a column, so apply_common_filters can't build SQL for it — join
        # and filter explicitly here instead.
        if filters.billing_type:
            query = query.join(ProjectBillingConfig, ProjectBillingConfig.project_id == Project.id)
            query = query.join(BillingType, BillingType.id == ProjectBillingConfig.billing_type_id)
            query = query.filter(BillingType.code == filters.billing_type)

        query = query.order_by(Project.created_at.desc())

        results = query.all()

        columns = [
            "Project Number", "Project Name", "Client Name", "Billing Type", "Status",
            "Contract Value", "Created At"
        ]

        rows = []
        total_contract_value = 0

        for project in results:
            rows.append({
                "Project Number": project.project_number,
                "Project Name": project.project_name,
                "Client Name": project.client_name or "N/A",
                "Billing Type": project.billing_type or "N/A",
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
