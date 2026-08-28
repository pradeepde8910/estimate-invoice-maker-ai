import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.core.database import engine, Base, init_db
from app.services import organization_service as organization

from app.api import (
    hello, reports, alerts, auth, billing_classification,
    resource_catalog, quotations, master,
    jobs, estimations, documents, organization as org_api,
    rate_cards, system, clients, invoices, projects, project_summary
)

# Initialize DB (creates tables, syncs rate cards, restores branding)
init_db()

app = FastAPI(title="Pixous Technologies API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/branding", StaticFiles(directory=str(organization.BRANDING_DIR)), name="branding")

# V2 Core Routers
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(hello.router, prefix="/api/v2/hello", tags=["Hello"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["Alerts"])
app.include_router(master.router, prefix="/api/master", tags=["Master Data"])
app.include_router(billing_classification.router, prefix="/api/master/billing-classifications", tags=["Billing Classifications"])
app.include_router(resource_catalog.router, prefix="/api/master/resource-catalog", tags=["Resource & Capability Catalog"])
app.include_router(quotations.router, prefix="/api/quotations", tags=["Quotations"])
app.include_router(invoices.router, prefix="/api/invoices", tags=["Invoices"])
app.include_router(projects.router, prefix="/api/projects", tags=["Projects"])
app.include_router(project_summary.router, prefix="/api/projects", tags=["Project Summary"])

# Legacy V1 Extracted Routers
app.include_router(jobs.router, tags=["Jobs"])
app.include_router(estimations.router, tags=["Estimations"])
app.include_router(documents.router, tags=["Documents"])
app.include_router(org_api.router, tags=["Organization"])
app.include_router(rate_cards.router, tags=["Rate Cards"])
app.include_router(system.router, tags=["System"])
app.include_router(clients.router, tags=["Clients"])

# Serve the built frontend (frontend/dist) from this same service, so the
# Render URL works as a single-origin app instead of returning FastAPI's bare
# 404 for "/". Registered last so it never shadows an /api/* route above —
# FastAPI matches routes in registration order. Guarded by existence so local
# backend-only dev (frontend not built) is unaffected.
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if FRONTEND_DIST.is_dir():
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
