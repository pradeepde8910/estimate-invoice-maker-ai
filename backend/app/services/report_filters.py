from sqlalchemy.orm import Query
from sqlalchemy.orm.attributes import InstrumentedAttribute
from app.schemas.report import ReportFilter


def _column(model, attr_name):
    """
    Returns `attr_name` off `model` only if it's a real SQLAlchemy column/
    relationship (InstrumentedAttribute) — not a plain Python @property.
    hasattr() alone isn't safe here: some models (e.g. Project.billing_type)
    expose computed @property attributes with the same names these generic
    filters look for. `Model.some_property == value` doesn't raise — it just
    evaluates as a plain Python `False`, and `query.filter(False)` silently
    returns zero rows instead of erroring, which is worse than a crash.
    """
    attr = getattr(model, attr_name, None)
    return attr if isinstance(attr, InstrumentedAttribute) else None


def apply_common_filters(query: Query, filters: ReportFilter, model, date_column) -> Query:
    """
    Applies standard filters to a SQLAlchemy query.
    `model` should be the primary SQLAlchemy model being queried (e.g. Invoice, Project).
    `date_column` is the specific column to use for the date range filter (e.g. Invoice.invoice_date).
    """
    if filters.client_id:
        col = _column(model, 'client_id')
        if col is not None:
            query = query.filter(col == filters.client_id)

    if filters.project_id:
        col = _column(model, 'project_id')
        if col is not None:
            query = query.filter(col == filters.project_id)
        elif model.__tablename__ == 'projects':
            query = query.filter(model.id == filters.project_id)

    if filters.project_ids:
        col = _column(model, 'project_id')
        if col is not None:
            query = query.filter(col.in_(filters.project_ids))
        elif model.__tablename__ == 'projects':
            query = query.filter(model.id.in_(filters.project_ids))

    if filters.statuses:
        col = _column(model, 'status')
        if col is not None:
            query = query.filter(col.in_(filters.statuses))

    if filters.billing_type:
        col = _column(model, 'billing_type')
        if col is not None:
            query = query.filter(col == filters.billing_type)
        # else: models like Project expose billing_type as a computed
        # @property (via ProjectBillingConfig) rather than a column — those
        # need their own explicit join-based filter in the report generator.

    if date_column is not None:
        if filters.from_date:
            query = query.filter(date_column >= filters.from_date)
        if filters.to_date:
            query = query.filter(date_column <= filters.to_date)

    return query
