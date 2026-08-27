"""
A minimal, always-succeeding report used only to prove the report registry
in app/api/report.py / app/api/reports.py is genuinely extensible — adding
a 6th report type should require nothing more than a new BaseReport
subclass and one registry entry, no changes to the export pipeline
(CSV/Excel/PDF) or the API route itself. Not exposed as a real business
report; ReportType.TEST exists specifically to exercise this.
"""

from sqlalchemy.orm import Session

from app.schemas.report import ReportFilter, ReportResult
from app.services.reports.base_report import BaseReport


class TestReport(BaseReport):

    def generate(self, db: Session, filters: ReportFilter) -> ReportResult:
        return ReportResult(
            report_type="TEST",
            columns=["Check", "Result"],
            rows=[{"Check": "Report registry extensibility", "Result": "OK"}],
            totals={},
        )
