"""
Client service — two deliberately separate client concepts, not yet
unified (see the reviewed Phase 2 migration plan: "defer /api/clients
until the estimation/document migration").

- list_derived_clients(): clients as grouped from estimation records
  (filesystem-era concept, kept working as-is).
- list_db_clients(): real rows in the clients table (app.models.master.Client).

These stay separate until estimations/documents fully own client identity;
unifying them earlier would silently conflate two things that currently
disagree with each other in real data (a derived "client name" grouping
vs. an actual Client row with contact/billing details).
"""

from sqlalchemy.orm import joinedload

from app.core.database import SessionLocal
from app.models.estimation import Estimation
from app.models.master import Client


def list_derived_clients() -> list[dict]:
    db = SessionLocal()
    try:
        # est.client is accessed below after this session closes — must be
        # eager-loaded here or it's a lazy-load on a detached instance
        # (DetachedInstanceError), same bug fixed in app/api/system.py's
        # get_analytics. Only surfaces once there's real data to iterate.
        estimations = (
            db.query(Estimation)
            .options(joinedload(Estimation.client))
            .filter(Estimation.is_deleted == False)
            .order_by(Estimation.updated_at.desc())
            .all()
        )
    finally:
        db.close()

    grouped: dict[str, list[dict]] = {}
    for est in estimations:
        client_name = est.client.company_name if est.client else "Unspecified Client"
        grouped.setdefault(client_name, []).append({
            "base_name": est.id,
            "project_name": est.project_name,
            "modified": est.updated_at.isoformat(),
            "grand_total": est.grand_total,
        })

    clients = [
        {
            "client_name": name,
            "estimations": estimations_for_client,
            "estimation_count": len(estimations_for_client),
            "latest_modified": max(e["modified"] for e in estimations_for_client),
        }
        for name, estimations_for_client in grouped.items()
    ]
    clients.sort(key=lambda c: c["latest_modified"], reverse=True)
    return clients


def list_db_clients() -> list[dict]:
    db = SessionLocal()
    try:
        clients = db.query(Client).filter(Client.company_name != None).order_by(Client.created_at.desc()).all()
        seen = set()
        unique_clients = []
        for c in clients:
            if not c.company_name:
                continue
            normalized = c.company_name.strip().lower()
            if normalized not in seen:
                seen.add(normalized)
                unique_clients.append({
                    "id": c.id,
                    "company_name": c.company_name,
                    "contact_person": c.contact_person,
                    "email": c.email,
                    "phone": c.phone,
                    "gstin": c.gstin,
                    "billing_address": c.billing_address,
                })
        return unique_clients
    finally:
        db.close()
