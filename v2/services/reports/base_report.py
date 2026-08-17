from abc import ABC, abstractmethod
from sqlalchemy.orm import Session
from v2.schemas.report import ReportFilter, ReportResult

class BaseReport(ABC):
    
    @abstractmethod
    def generate(self, db: Session, filters: ReportFilter) -> ReportResult:
        """
        Generates the report data from the database using the provided filters.
        Returns a structured ReportResult independent of any export format.
        """
        pass
