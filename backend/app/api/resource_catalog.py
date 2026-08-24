from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.api.dependencies import require_roles
from app.models.resource_catalog import (
    Capability, TechnologyProvider, TechnologyModel, ModelFeature, ApiPricingRule,
)
from app.schemas.resource_catalog import (
    CapabilityCreate, CapabilityUpdate, CapabilityResponse,
    ProviderCreate, ProviderUpdate, ProviderResponse,
    TechnologyModelCreate, TechnologyModelUpdate, TechnologyModelResponse,
    ModelFeatureCreate, ModelFeatureResponse,
    ApiPricingRuleCreate, ApiPricingRuleUpdate, ApiPricingRuleResponse,
)

router = APIRouter()


# ── Capabilities ────────────────────────────────────────────────────────

@router.get("/capabilities", response_model=List[CapabilityResponse])
def list_capabilities(
    active_only: bool = True,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance")),
):
    q = db.query(Capability)
    if active_only:
        q = q.filter(Capability.active.is_(True))
    return q.order_by(Capability.category, Capability.name).all()

@router.post("/capabilities", response_model=CapabilityResponse)
def create_capability(
    data: CapabilityCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    existing = db.query(Capability).filter_by(key=data.key).first()
    if existing:
        if not existing.active:
            for key, value in data.dict().items():
                setattr(existing, key, value)
            existing.active = True
            db.commit()
            db.refresh(existing)
            return existing
        raise HTTPException(status_code=400, detail=f"Capability key '{data.key}' already exists")
    capability = Capability(**data.dict())
    db.add(capability)
    db.commit()
    db.refresh(capability)
    return capability

@router.put("/capabilities/{id}", response_model=CapabilityResponse)
def update_capability(
    id: str, data: CapabilityUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    capability = db.query(Capability).filter_by(id=id).first()
    if not capability:
        raise HTTPException(status_code=404, detail="Capability not found")
    for key, value in data.dict(exclude_unset=True).items():
        setattr(capability, key, value)
    db.commit()
    db.refresh(capability)
    return capability

@router.delete("/capabilities/{id}")
def deactivate_capability(
    id: str,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    capability = db.query(Capability).filter_by(id=id).first()
    if not capability:
        raise HTTPException(status_code=404, detail="Capability not found")
    capability.active = False
    db.commit()
    return {"message": "Capability disabled"}


# ── Providers ───────────────────────────────────────────────────────────

@router.get("/providers", response_model=List[ProviderResponse])
def list_providers(
    active_only: bool = True,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance")),
):
    q = db.query(TechnologyProvider)
    if active_only:
        q = q.filter(TechnologyProvider.active.is_(True))
    return q.order_by(TechnologyProvider.name).all()

@router.post("/providers", response_model=ProviderResponse)
def create_provider(
    data: ProviderCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    existing = db.query(TechnologyProvider).filter_by(key=data.key).first()
    if existing:
        if not existing.active:
            for key, value in data.dict().items():
                setattr(existing, key, value)
            existing.active = True
            db.commit()
            db.refresh(existing)
            return existing
        raise HTTPException(status_code=400, detail=f"Provider key '{data.key}' already exists")
    provider = TechnologyProvider(**data.dict())
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider

@router.put("/providers/{id}", response_model=ProviderResponse)
def update_provider(
    id: str, data: ProviderUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    provider = db.query(TechnologyProvider).filter_by(id=id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    for key, value in data.dict(exclude_unset=True).items():
        setattr(provider, key, value)
    db.commit()
    db.refresh(provider)
    return provider

@router.delete("/providers/{id}")
def deactivate_provider(
    id: str,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    provider = db.query(TechnologyProvider).filter_by(id=id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    provider.active = False
    db.commit()
    return {"message": "Provider disabled"}


# ── Technology models (+ nested features/pricing) ──────────────────────

@router.get("/models", response_model=List[TechnologyModelResponse])
def list_models(
    capability_id: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Finance")),
):
    q = db.query(TechnologyModel).options(
        joinedload(TechnologyModel.provider),
        joinedload(TechnologyModel.capability),
        joinedload(TechnologyModel.features),
        joinedload(TechnologyModel.pricing_rules),
    )
    if active_only:
        q = q.filter(TechnologyModel.active.is_(True))
    if capability_id:
        q = q.filter(TechnologyModel.capability_id == capability_id)
    return q.order_by(TechnologyModel.model_name).all()

@router.post("/models", response_model=TechnologyModelResponse)
def create_model(
    data: TechnologyModelCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    if not db.query(TechnologyProvider).filter_by(id=data.provider_id).first():
        raise HTTPException(status_code=400, detail="provider_id does not exist")
    if not db.query(Capability).filter_by(id=data.capability_id).first():
        raise HTTPException(status_code=400, detail="capability_id does not exist")
    model = TechnologyModel(**data.dict())
    db.add(model)
    db.commit()
    db.refresh(model)
    return model

@router.put("/models/{id}", response_model=TechnologyModelResponse)
def update_model(
    id: str, data: TechnologyModelUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    model = db.query(TechnologyModel).filter_by(id=id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    for key, value in data.dict(exclude_unset=True).items():
        setattr(model, key, value)
    db.commit()
    db.refresh(model)
    return model

@router.delete("/models/{id}")
def deactivate_model(
    id: str,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    model = db.query(TechnologyModel).filter_by(id=id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    model.active = False
    db.commit()
    return {"message": "Model disabled"}


# ── Model features ──────────────────────────────────────────────────────

@router.post("/models/{model_id}/features", response_model=ModelFeatureResponse)
def add_model_feature(
    model_id: str, data: ModelFeatureCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    if not db.query(TechnologyModel).filter_by(id=model_id).first():
        raise HTTPException(status_code=404, detail="Model not found")
    feature = ModelFeature(model_id=model_id, **data.dict())
    db.add(feature)
    db.commit()
    db.refresh(feature)
    return feature

@router.delete("/features/{id}")
def delete_model_feature(
    id: str,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    feature = db.query(ModelFeature).filter_by(id=id).first()
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    db.delete(feature)
    db.commit()
    return {"message": "Feature removed"}


# ── Pricing rules ───────────────────────────────────────────────────────

@router.post("/models/{model_id}/pricing", response_model=ApiPricingRuleResponse)
def add_pricing_rule(
    model_id: str, data: ApiPricingRuleCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    if not db.query(TechnologyModel).filter_by(id=model_id).first():
        raise HTTPException(status_code=404, detail="Model not found")
    rule = ApiPricingRule(model_id=model_id, **data.dict())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule

@router.put("/pricing/{id}", response_model=ApiPricingRuleResponse)
def update_pricing_rule(
    id: str, data: ApiPricingRuleUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    rule = db.query(ApiPricingRule).filter_by(id=id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Pricing rule not found")
    for key, value in data.dict(exclude_unset=True).items():
        setattr(rule, key, value)
    db.commit()
    db.refresh(rule)
    return rule

@router.delete("/pricing/{id}")
def deactivate_pricing_rule(
    id: str,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    rule = db.query(ApiPricingRule).filter_by(id=id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Pricing rule not found")
    rule.active = False
    db.commit()
    return {"message": "Pricing rule disabled"}
