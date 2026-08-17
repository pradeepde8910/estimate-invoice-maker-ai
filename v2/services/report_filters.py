from sqlalchemy.orm import Query
from v2.schemas.report import ReportFilter

def apply_common_filters(query: Query, filters: ReportFilter, model, date_column) -> Query:
    """
    Applies standard filters to a SQLAlchemy query.
    `model` should be the primary SQLAlchemy model being queried (e.g. Invoice, Project).
    `date_column` is the specific column to use for the date range filter (e.g. Invoice.invoice_date).
    """
    if filters.client_id:
        # Assumes the model has a client_id column. Outstanding may need custom joins.
        if hasattr(model, 'client_id'):
            query = query.filter(model.client_id == filters.client_id)
            
    if filters.project_id:
        if hasattr(model, 'project_id'):
            query = query.filter(model.project_id == filters.project_id)
        elif hasattr(model, 'id') and model.__tablename__ == 'projects':
            query = query.filter(model.id == filters.project_id)
            
    if filters.statuses and hasattr(model, 'status'):
        query = query.filter(model.status.in_(filters.statuses))
        
    if filters.billing_type and hasattr(model, 'billing_type'):
        query = query.filter(model.billing_type == filters.billing_type)
        
    if date_column is not None:
        if filters.from_date:
            query = query.filter(date_column >= filters.from_date)
        if filters.to_date:
            query = query.filter(date_column <= filters.to_date)
            
    return query
