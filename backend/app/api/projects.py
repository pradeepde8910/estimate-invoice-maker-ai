from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from pydantic import BaseModel
from decimal import Decimal
import uuid

from app.database import get_db
from app.api.dependencies import require_roles
from app.models.project import Project, ProjectBillingConfig, ProjectMilestone
from app.models.invoice import InvoiceItem, Invoice
from app.schemas.project_summary import BillingPreviewResponse, BillingPreviewMilestone, BillingPreviewTask, BillingPreviewClassification

router = APIRouter()

class MilestoneCreate(BaseModel):
    name: str
    amount: Decimal

class ProjectCreateRequest(BaseModel):
    client_id: str
    project_name: str
    project_number: str
    contract_value: Decimal
    billing_type_id: str
    gst_percentage: Decimal = Decimal('18.00')
    tds_applicable: str = "NO"
    milestones: List[MilestoneCreate] = []

class ProjectResponse(BaseModel):
    id: str
    project_name: str
    project_number: str
    contract_value: Decimal
    status: str
    billing_type: str | None = None
    client_id: str | None = None
    client_name: str | None = None

    class Config:
        from_attributes = True

@router.get("", response_model=List[ProjectResponse])
def list_projects(
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance"))
):
    return (
        db.query(Project)
        .options(
            joinedload(Project.billing_config).joinedload(ProjectBillingConfig.billing_type),
            joinedload(Project.client),
        )
        .all()
    )

@router.post("", response_model=ProjectResponse)
def create_project(
    req: ProjectCreateRequest,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance"))
):
    project = Project(
        client_id=req.client_id,
        project_name=req.project_name,
        project_number=req.project_number,
        contract_value=req.contract_value
    )
    db.add(project)
    db.flush()

    billing_config = ProjectBillingConfig(
        project_id=project.id,
        billing_type_id=req.billing_type_id,
        gst_percentage=req.gst_percentage,
        tds_applicable=req.tds_applicable
    )
    db.add(billing_config)

    for m in req.milestones:
        db.add(ProjectMilestone(
            project_id=project.id,
            name=m.name,
            amount=m.amount
        ))

    db.commit()
    db.refresh(project)
    return project

from app.core.database import SessionLocal as V1SessionLocal
from app.models.estimation import Estimation
from app.models.master import Client as V1Client
from app.models.master import Client as V2Client

@router.post("/estimations/{estimation_id}/convert")
def convert_estimation_to_project(
    estimation_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance"))
):
    v1_db = V1SessionLocal()
    try:
        est = v1_db.query(Estimation).filter(Estimation.id == estimation_id).first()
        if not est:
            raise HTTPException(status_code=404, detail="Estimation not found")
        
        if est.status != "Approved":
            raise HTTPException(status_code=400, detail="Only Approved estimations can be converted")
            
        if est.converted_project_id:
            raise HTTPException(status_code=400, detail="Estimation has already been converted")

        # 1. Handle Client Cross-DB sync
        v1_client = v1_db.query(V1Client).filter(V1Client.id == est.client_id).first()
        if not v1_client:
            raise HTTPException(status_code=400, detail="Associated client not found in V1")
            
        if v1_client.status != "CONFIRMED":
            raise HTTPException(status_code=400, detail="Client details must be confirmed before converting to a project.")
            
        if not v1_client.company_name and not v1_client.contact_person:
            raise HTTPException(status_code=400, detail="Client must have either a Company Name or Contact Person.")
            
        # Check if client exists in V2
        # Try matching by company_name if it exists, else by contact_person
        v2_client = None
        if v1_client.company_name:
            v2_client = db.query(V2Client).filter(V2Client.company_name == v1_client.company_name).first()
        elif v1_client.contact_person:
            v2_client = db.query(V2Client).filter(V2Client.contact_person == v1_client.contact_person, V2Client.company_name.is_(None)).first()
            
        if not v2_client:
            v2_client = V2Client(
                company_name=v1_client.company_name,
                contact_person=v1_client.contact_person,
                email=v1_client.email,
                phone=v1_client.phone,
                gstin=v1_client.gstin,
                billing_address=v1_client.billing_address,
                status="CONFIRMED"
            )
            db.add(v2_client)
            db.flush() # get ID
            
        # 2. Create Project in V2
        import uuid
        project = Project(
            client_id=v2_client.id,
            project_number=f"PRJ-{uuid.uuid4().hex[:6].upper()}",
            project_name=est.project_name,
            contract_value=est.grand_total,
            estimation_id=est.id,
            status="Active"
        )
        db.add(project)
        db.flush()
        
        # 3. Create Project Milestones and Commercial Components from the AI
        # billing units FIRST — the billing type/label decided below reflects
        # whatever structure this estimation actually produced, rather than
        # assuming every converted project is milestone-billed.
        import json
        from app.models.project_component import ProjectCommercialComponent
        from app.models.master import BillingClassification, BillingType
        from app.services.billing_classification_service import match_billing_classifications
        from app.services.invoice_service import MIN_AUTO_MATCH_SCORE

        all_classifications = db.query(BillingClassification).filter_by(active=True).all()

        def _get_classification(description: str):
            matches = match_billing_classifications(description, all_classifications, limit=1)
            if matches and matches[0]["score"] >= MIN_AUTO_MATCH_SCORE:
                return matches[0]["id"], "AUTO_MATCHED"
            return None, "UNCLASSIFIED"

        def _get_or_create_billing_type(code: str, description: str) -> "BillingType":
            b_type = db.query(BillingType).filter_by(code=code).first()
            if not b_type:
                b_type = BillingType(code=code, description=description)
                db.add(b_type)
                db.flush()
            return b_type

        billing_units: list = []
        has_components = False

        if est.raw_pipeline_json:
            result_data = est.raw_pipeline_json
            cost_data = result_data.get("cost_estimation", result_data)

            unit_estimates = cost_data.get("unit_estimates", [])
            if not unit_estimates:
                unit_estimates = cost_data.get("phase_estimates", [])
            total_dev_cost = Decimal(str(cost_data.get("total_development_cost", 0)))
            contingency_amt = Decimal(str(cost_data.get("contingency_amount", 0)))
            infra_monthly = Decimal(str(cost_data.get("infrastructure_cost_monthly", 0)))
            license_monthly = Decimal(str(cost_data.get("third_party_licenses_monthly", 0)))

            for unit in unit_estimates:
                is_billing = unit.get("billing", {}).get("is_billing_unit")
                if is_billing is None:
                    is_billing = unit.get("relevance", {}).get("billing")
                if is_billing is True:
                    billing_units.append(unit)

            if billing_units:
                total_billing_amount = Decimal('0.00')
                for unit in billing_units:
                    cost = Decimal(str(unit.get("estimate", {}).get("cost", 0)))
                    total_billing_amount += cost

                if total_billing_amount > total_dev_cost + Decimal('1.00'):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Safety check failed: Total billing milestones amount (₹{total_billing_amount:,.2f}) exceeds total project development cost (₹{total_dev_cost:,.2f})."
                    )

                for unit in billing_units:
                    cost = Decimal(str(unit.get("estimate", {}).get("cost", 0)))
                    name = unit.get("label", "Untitled Milestone")
                    bc_id, c_source = _get_classification(name)
                    db.add(ProjectMilestone(
                        project_id=project.id,
                        name=name,
                        amount=cost,
                        status="PENDING",
                        source_unit_id=unit.get("unit_id") or unit.get("phase_id"),
                        billing_classification_id=bc_id,
                        classification_source=c_source
                    ))

            # Commercial Components for non-milestone costs — these can exist
            # standalone (a project billed purely on infra/license/contingency,
            # with no milestone breakdown at all) or alongside milestones.
            if contingency_amt > 0:
                has_components = True
                name = "Project Contingency"
                bc_id, c_source = _get_classification(name)
                db.add(ProjectCommercialComponent(
                    project_id=project.id,
                    name=name,
                    amount=contingency_amt,
                    component_type="contingency",
                    billing_policy="conditional",
                    status="RESERVED",
                    billing_classification_id=bc_id,
                    classification_source=c_source
                ))

            if infra_monthly > 0:
                has_components = True
                infra_cost = infra_monthly * 6  # standard 6mo estimation
                name = "Infrastructure (6 months)"
                bc_id, c_source = _get_classification(name)
                db.add(ProjectCommercialComponent(
                    project_id=project.id,
                    name=name,
                    amount=infra_cost,
                    component_type="infrastructure",
                    billing_policy="recurring",
                    status="AVAILABLE",
                    billing_classification_id=bc_id,
                    classification_source=c_source
                ))

            if license_monthly > 0:
                has_components = True
                lic_cost = license_monthly * 6
                name = "Licenses & Services (6 months)"
                bc_id, c_source = _get_classification(name)
                db.add(ProjectCommercialComponent(
                    project_id=project.id,
                    name=name,
                    amount=lic_cost,
                    component_type="licenses",
                    billing_policy="upfront",
                    status="AVAILABLE",
                    billing_classification_id=bc_id,
                    classification_source=c_source
                ))

        # 3.5 Decide the project's billing type from what was actually built
        # above, instead of hardcoding MILESTONE regardless of structure —
        # see app/services/billing_type_service.py (unit-tested) for the
        # decision rationale.
        from app.services.billing_type_service import (
            BILLING_TYPE_DESCRIPTIONS, decide_billing_type, infer_delivery_unit_label,
        )

        billing_type_code, default_label = decide_billing_type(billing_units, has_components)
        b_type = _get_or_create_billing_type(billing_type_code, BILLING_TYPE_DESCRIPTIONS[billing_type_code])
        delivery_unit_label = infer_delivery_unit_label(billing_type_code, billing_units, default_label)

        bc = ProjectBillingConfig(
            project_id=project.id,
            billing_type_id=b_type.id,
            gst_percentage=18.00,
            tds_applicable="NO",
            delivery_unit_label=delivery_unit_label
        )
        db.add(bc)

        # 4. Mark V1 Estimation as Converted
        est.status = "Converted"
        est.converted_project_id = project.id
        
        # Commit both
        db.commit()
        v1_db.commit()
        
        return {"project_id": project.id, "message": "Successfully converted to Project"}
    except HTTPException:
        db.rollback()
        v1_db.rollback()
        raise
    except Exception as e:
        db.rollback()
        v1_db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
        v1_db.close()

@router.get("/{project_id}/billing-preview", response_model=BillingPreviewResponse)
def get_billing_preview(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance"))
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    v1_db = V1SessionLocal()
    try:
        est = v1_db.query(Estimation).filter(Estimation.id == project.estimation_id).first()
        if not est or not est.raw_pipeline_json:
            return BillingPreviewResponse(milestones=[])

        cost_data = est.raw_pipeline_json.get("cost_estimation", est.raw_pipeline_json)
        unit_estimates = cost_data.get("unit_estimates", [])
        if not unit_estimates:
            unit_estimates = cost_data.get("phase_estimates", [])

        milestones = db.query(ProjectMilestone).filter(
            ProjectMilestone.project_id == project.id,
            ProjectMilestone.status.in_(["PENDING", "PARTIALLY_BILLED"])
        ).all()

        if not milestones:
            return BillingPreviewResponse(milestones=[])

        from app.models.master import BillingClassification
        from app.services.billing_classification_service import match_billing_classifications
        all_classifications = db.query(BillingClassification).filter_by(active=True).all()
        classifications_by_id = {c.id: c for c in all_classifications}

        milestone_ids = [m.id for m in milestones]
        # Query all billed or draft invoice items across all milestones in a single batch query
        billed_items = (
            db.query(InvoiceItem.milestone_id, InvoiceItem.task_key)
            .join(InvoiceItem.invoice)
            .filter(
                InvoiceItem.milestone_id.in_(milestone_ids),
                InvoiceItem.task_key.isnot(None),
                Invoice.status.in_(["ISSUED", "DRAFT"])
            )
            .all()
        )
        billed_task_keys = {(item.milestone_id, item.task_key) for item in billed_items}

        preview_milestones = []

        for m in milestones:
            # Find matching unit
            unit = next((u for u in unit_estimates if (u.get("unit_id") or u.get("phase_id")) == m.source_unit_id), None)
            if not unit:
                continue

            reqs = unit.get("requirement_estimates", [])
            preview_tasks = []

            for i, req in enumerate(reqs):
                tasks = req.get("implementation_tasks", [])
                for j, task in enumerate(tasks):
                    task_name = task.get("task", "Unknown Task")
                    task_cost = Decimal(str(task.get("cost", 0)))
                    # Stable identity: e.g. "unit_id:req_index:task_index"
                    task_key = f"{m.source_unit_id}:req-{i}:task-{j}"

                    # Check if already billed or in draft in O(1) in-memory lookup
                    if (m.id, task_key) in billed_task_keys:
                        continue

                    # Auto-match HSN/SAC
                    matches = match_billing_classifications(task_name, all_classifications, limit=1)
                    cls_data = None
                    if matches and matches[0]["score"] >= 2:
                        cls_obj = classifications_by_id.get(matches[0]["id"])
                        if cls_obj:
                            cls_data = BillingPreviewClassification(
                                id=cls_obj.id,
                                hsn_sac=cls_obj.hsn_sac_code,
                                gst_rate=cls_obj.gst_rate
                            )

                    preview_tasks.append(BillingPreviewTask(
                        task_key=task_key,
                        requirement_name=req.get("title", "Unknown Requirement"),
                        description=task_name,
                        amount=task_cost,
                        hours=Decimal(str(task.get("hours", 0))) if task.get("hours") is not None else None,
                        classification=cls_data
                    ))

            if preview_tasks:
                preview_milestones.append(BillingPreviewMilestone(
                    id=m.id,
                    name=m.name,
                    status=m.status,
                    tasks=preview_tasks
                ))

        return BillingPreviewResponse(milestones=preview_milestones)
    finally:
        v1_db.close()
