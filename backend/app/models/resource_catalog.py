"""
Resource & Capability Costing Engine — the data layer only, for now.

This deliberately mirrors app/models/master.py's BillingClassification
pattern (an admin-managed catalog, not something the estimation agent writes
to directly) and is designed so that "speech-to-text" and "object storage"
and "WhatsApp messaging" are all just rows of data, not special-cased code
paths. Nothing here is wired into the estimation agent yet — that's a later
phase, once this foundation (capability -> provider -> model -> pricing) is
in place and populated with real, verified numbers.

Layering, cheapest to most specific:
  Capability        — the canonical vocabulary of what a project might need
                       (speech_to_text, object_storage, llm_inference, ...).
  TechnologyProvider — a vendor (Sarvam, OpenAI, AWS, ...).
  TechnologyModel    — one vendor's specific offering for one capability.
  ModelFeature       — free-form key/value attributes on a model (language
                       support, streaming, region, ...) so filtering by
                       constraint (Phase 5, the resolver) doesn't require a
                       schema change every time a new kind of constraint
                       shows up.
  ApiPricingRule     — a model's price. Deliberately generic on unit_type
                       and pricing_model so "per audio minute", "per 1M
                       tokens", "per GB/month", and "flat monthly" all use
                       the same table instead of one column per unit kind.

ResourceRequirement is the per-project link (project needs capability X,
resolved to model Y) — the schema exists now so later phases have somewhere
to write to, but nothing populates it yet.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base


class Capability(Base):
    """The canonical, extensible vocabulary of what a project might need —
    an admin can add 'video_transcoding' later without any code change."""
    __tablename__ = "capabilities"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String(100), unique=True, nullable=False, index=True)  # e.g. "speech_to_text"
    name = Column(String(150), nullable=False)  # e.g. "Speech-to-Text"
    # A property of the capability itself, not of any one provider —
    # "speech_to_text" is always an ai_service, "object_storage" is always infrastructure.
    category = Column(String(50), nullable=False)  # ai_service | infrastructure | external_service | software_license
    description = Column(Text, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    models = relationship("TechnologyModel", back_populates="capability")


class TechnologyProvider(Base):
    """A vendor — Sarvam, OpenAI, AWS, Twilio, ... . Vendor-neutral by
    design: nothing here is estimation logic, just an identity record."""
    __tablename__ = "technology_providers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String(100), unique=True, nullable=False, index=True)  # e.g. "sarvam"
    name = Column(String(150), nullable=False)  # e.g. "Sarvam AI"
    website = Column(String(255), nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    models = relationship("TechnologyModel", back_populates="provider")


class TechnologyModel(Base):
    """One vendor's specific offering that satisfies one capability —
    e.g. Sarvam's speech-to-text model. Pricing lives separately
    (ApiPricingRule) since one model can have multiple pricing rules over
    time (effective_from/to) or multiple pricing tiers."""
    __tablename__ = "technology_models"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id = Column(String(36), ForeignKey("technology_providers.id", ondelete="RESTRICT"), nullable=False)
    capability_id = Column(String(36), ForeignKey("capabilities.id", ondelete="RESTRICT"), nullable=False)
    model_key = Column(String(100), nullable=False)  # e.g. "saarika-v2"
    model_name = Column(String(150), nullable=False)  # e.g. "Saarika v2"
    description = Column(Text, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    provider = relationship("TechnologyProvider", back_populates="models")
    capability = relationship("Capability", back_populates="models")
    features = relationship("ModelFeature", back_populates="model", cascade="all, delete-orphan")
    pricing_rules = relationship("ApiPricingRule", back_populates="model", cascade="all, delete-orphan")


class ModelFeature(Base):
    """Free-form key/value attribute on a model — 'language': 'Tamil',
    'streaming': 'true', 'region': 'India'. A model can have many rows for
    the same feature_key (e.g. one per supported language). This is what
    lets the resolver (a later phase) filter "must support Tamil" without
    a schema migration every time a new constraint type appears."""
    __tablename__ = "model_features"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    model_id = Column(String(36), ForeignKey("technology_models.id", ondelete="CASCADE"), nullable=False)
    feature_key = Column(String(100), nullable=False)  # e.g. "language", "streaming", "region"
    feature_value = Column(String(255), nullable=False)  # e.g. "Tamil", "true", "India"

    model = relationship("TechnologyModel", back_populates="features")


class ApiPricingRule(Base):
    """A model's price. unit_type and pricing_model are free strings, not
    enums — the whole point of this table is that 'per audio minute', 'per
    1M tokens', and 'per GB/month' all fit the same shape instead of one
    column per unit kind. tier_config holds structured tiered-pricing data
    (JSON text) for when pricing_model = 'TIERED'; unused otherwise.

    pricing_source distinguishes a verified, sourced number from a rough
    guess — never let an unverified number get treated as authoritative in
    a quotation. last_verified_on/source_url exist so staleness is visible
    rather than silently trusted."""
    __tablename__ = "api_pricing_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    model_id = Column(String(36), ForeignKey("technology_models.id", ondelete="CASCADE"), nullable=False)

    pricing_model = Column(String(30), nullable=False, default="PER_UNIT")
    # FLAT | PER_UNIT | TIERED | SUBSCRIPTION_PLUS_USAGE | MINIMUM_COMMITMENT
    unit_type = Column(String(50), nullable=True)  # e.g. MINUTE, TOKENS_1M, GB_MONTH, PAGE, REQUEST — null for FLAT
    price = Column(Numeric(12, 4), nullable=False)
    currency = Column(String(10), nullable=False, default="INR")
    minimum_commitment = Column(Numeric(12, 2), nullable=True)
    tier_config = Column(Text, nullable=True)  # JSON text, only used when pricing_model = TIERED

    pricing_source = Column(String(30), nullable=False, default="market_estimate")
    # verified_catalog | vendor_docs | market_estimate
    source_url = Column(String(500), nullable=True)
    last_verified_on = Column(DateTime, nullable=True)

    effective_from = Column(DateTime, default=datetime.utcnow)
    effective_to = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    model = relationship("TechnologyModel", back_populates="pricing_rules")


class ResourceRequirement(Base):
    """Per-project link: 'this project needs capability X', optionally
    resolved to a specific model with a stated reason. Schema only for
    now — nothing populates this until the analysis agent is updated to
    extract structured resource requirements and the resolver picks a
    model for them (later phases)."""
    __tablename__ = "resource_requirements"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    estimation_id = Column(String(255), nullable=True)  # V1 estimation id — cross-DB, not a real FK (see Invoice.project_id pattern)
    requirement_id = Column(String(100), nullable=True)  # source requirement id from the analysis output, if any

    capability_id = Column(String(36), ForeignKey("capabilities.id", ondelete="RESTRICT"), nullable=False)
    resolved_model_id = Column(String(36), ForeignKey("technology_models.id", ondelete="SET NULL"), nullable=True)

    vendor_constraint_provider_id = Column(String(36), ForeignKey("technology_providers.id", ondelete="SET NULL"), nullable=True)
    vendor_constraint_type = Column(String(20), nullable=True)  # mandatory | preferred | candidate

    usage_metric = Column(String(100), nullable=True)  # e.g. "audio_minutes"
    usage_value = Column(Numeric(14, 2), nullable=True)
    usage_period = Column(String(20), nullable=True)  # e.g. "month"
    usage_source = Column(String(30), nullable=True)  # llm_estimate | client_provided
    usage_confidence = Column(String(20), nullable=True)  # low | medium | high

    selection_reason = Column(Text, nullable=True)
    monthly_cost = Column(Numeric(12, 2), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    capability = relationship("Capability")
    resolved_model = relationship("TechnologyModel")
    vendor_constraint_provider = relationship("TechnologyProvider")
