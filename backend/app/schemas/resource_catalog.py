from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel


# ── Capability ──────────────────────────────────────────────────────────

class CapabilityCreate(BaseModel):
    key: str
    name: str
    category: str  # ai_service | infrastructure | external_service | software_license
    description: Optional[str] = None
    active: bool = True

class CapabilityUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    active: Optional[bool] = None

class CapabilityResponse(BaseModel):
    id: str
    key: str
    name: str
    category: str
    description: Optional[str]
    active: bool

    class Config:
        from_attributes = True


# ── Provider ────────────────────────────────────────────────────────────

class ProviderCreate(BaseModel):
    key: str
    name: str
    website: Optional[str] = None
    active: bool = True

class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    website: Optional[str] = None
    active: Optional[bool] = None

class ProviderResponse(BaseModel):
    id: str
    key: str
    name: str
    website: Optional[str]
    active: bool

    class Config:
        from_attributes = True


# ── Model feature ───────────────────────────────────────────────────────

class ModelFeatureCreate(BaseModel):
    feature_key: str
    feature_value: str

class ModelFeatureResponse(BaseModel):
    id: str
    feature_key: str
    feature_value: str

    class Config:
        from_attributes = True


# ── Pricing rule ────────────────────────────────────────────────────────

class ApiPricingRuleCreate(BaseModel):
    pricing_model: str = "PER_UNIT"  # FLAT | PER_UNIT | TIERED | SUBSCRIPTION_PLUS_USAGE | MINIMUM_COMMITMENT
    unit_type: Optional[str] = None  # e.g. MINUTE, TOKENS_1M, GB_MONTH, PAGE, REQUEST
    price: Decimal
    currency: str = "INR"
    minimum_commitment: Optional[Decimal] = None
    tier_config: Optional[str] = None
    pricing_source: str = "market_estimate"  # verified_catalog | vendor_docs | market_estimate
    source_url: Optional[str] = None
    last_verified_on: Optional[datetime] = None
    active: bool = True

class ApiPricingRuleUpdate(BaseModel):
    pricing_model: Optional[str] = None
    unit_type: Optional[str] = None
    price: Optional[Decimal] = None
    currency: Optional[str] = None
    minimum_commitment: Optional[Decimal] = None
    tier_config: Optional[str] = None
    pricing_source: Optional[str] = None
    source_url: Optional[str] = None
    last_verified_on: Optional[datetime] = None
    active: Optional[bool] = None

class ApiPricingRuleResponse(BaseModel):
    id: str
    model_id: str
    pricing_model: str
    unit_type: Optional[str]
    price: Decimal
    currency: str
    minimum_commitment: Optional[Decimal]
    tier_config: Optional[str]
    pricing_source: str
    source_url: Optional[str]
    last_verified_on: Optional[datetime]
    active: bool

    class Config:
        from_attributes = True


# ── Technology model ────────────────────────────────────────────────────

class TechnologyModelCreate(BaseModel):
    provider_id: str
    capability_id: str
    model_key: str
    model_name: str
    description: Optional[str] = None
    active: bool = True

class TechnologyModelUpdate(BaseModel):
    provider_id: Optional[str] = None
    capability_id: Optional[str] = None
    model_key: Optional[str] = None
    model_name: Optional[str] = None
    description: Optional[str] = None
    active: Optional[bool] = None

class TechnologyModelResponse(BaseModel):
    id: str
    provider_id: str
    capability_id: str
    model_key: str
    model_name: str
    description: Optional[str]
    active: bool
    provider: Optional[ProviderResponse] = None
    capability: Optional[CapabilityResponse] = None
    features: List[ModelFeatureResponse] = []
    pricing_rules: List[ApiPricingRuleResponse] = []

    class Config:
        from_attributes = True
