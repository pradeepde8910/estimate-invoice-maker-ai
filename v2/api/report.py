from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from v2.database import get_db
from v2.api.dependencies import require_roles
from v2.schemas.report import ReportRequest, ReportType, ExportFormat
from v2.services.reports.project_report import ProjectReport
from v2.services.reports.invoice_report import InvoiceReport
from v2.services.reports.payment_report import PaymentReport
from v2.services.reports.outstanding_report import OutstandingReport
from v2.services.reports.milestone_report import MilestoneReport
from v2.services.reports.test_report import TestReport

from v2.exporters.csv_exporter import export_csv
from v2.exporters.excel_exporter import export_excel
from v2.exporters.pdf_exporter import export_pdf

router = APIRouter(prefix="/reports", tags=["Reports"])

REPORT_REGISTRY = {
    ReportType.PROJECT: ProjectReport(),
    ReportType.INVOICE: InvoiceReport(),
    ReportType.PAYMENT: PaymentReport(),
    ReportType.OUTSTANDING: OutstandingReport(),
    ReportType.MILESTONE: MilestoneReport(),
    ReportType.TEST: TestReport()
}

@router.post("/{report_type}/export")
def export_report(
    report_type: ReportType, 
    request: ReportRequest, 
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance"))
):
    """
    Generates a report based on provided filters and returns it in the requested format.
    """
    report_engine = REPORT_REGISTRY.get(report_type)
    if not report_engine:
        raise HTTPException(status_code=400, detail="Unsupported report type")
        
    try:
        # 1. Generate standard dataset
        dataset = report_engine.generate(db, request.filters)
        
        # 2. Export based on requested format
        if request.format == ExportFormat.CSV:
            content = export_csv(dataset)
            media_type = "text/csv"
            extension = "csv"
        elif request.format == ExportFormat.EXCEL:
            content = export_excel(dataset)
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            extension = "xlsx"
        elif request.format == ExportFormat.PDF:
            content = export_pdf(dataset)
            media_type = "application/pdf"
            extension = "pdf"
        else:
            raise HTTPException(status_code=400, detail="Unsupported export format")
            
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={report_type.value.lower()}_report.{extension}"
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
