import sys
import os

# Insert backend/v1 into sys.path so V1 imports (like `import db`, `import config`) resolve correctly
v1_path = os.path.join(os.path.dirname(__file__), "v1")
sys.path.insert(0, v1_path)

from v1.api import app as v1_app

# Now import V2 routers
from app.api import hello, invoice, payment, project_summary, report, alert, auth, project, billing_classification, resource_catalog, quotation, master
from app.database import engine
from app.models.base import Base

# Create DB tables for V2 (if not handled by migrations)
Base.metadata.create_all(bind=engine)

# Use the V1 app as the main app, and mount V2 routers onto it
app = v1_app

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])

app.include_router(hello.router, prefix="/api/v2/hello", tags=["Hello"])
app.include_router(invoice.router, prefix="/api/invoices", tags=["Invoices"])
app.include_router(payment.router, prefix="/api/payments", tags=["Payments"])
app.include_router(project_summary.router, prefix="/api/projects", tags=["Projects Summary"])
app.include_router(project.router, prefix="/api/projects", tags=["Projects"])
app.include_router(report.router, prefix="/api/reports", tags=["Reports"])
app.include_router(alert.router, prefix="/api/alerts", tags=["Alerts"])
app.include_router(master.router, prefix="/api/master", tags=["Master Data"])
app.include_router(billing_classification.router, prefix="/api/master/billing-classifications", tags=["Billing Classifications"])
app.include_router(resource_catalog.router, prefix="/api/master/resource-catalog", tags=["Resource & Capability Catalog"])
app.include_router(quotation.router, prefix="/api/quotations", tags=["Quotations"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
