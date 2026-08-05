"""
Pydantic data models for structured data flow across the pipeline.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# ─── OCR Output ──────────────────────────────────────────────────────────────

class PageContent(BaseModel):
    """Single page of OCR output."""
    page_number: int
    text: str
    has_tables: bool = False
    has_images: bool = False


class OCRResult(BaseModel):
    """Complete OCR extraction result."""
    total_pages: int = 0
    pages: list[PageContent] = Field(default_factory=list)
    full_text: str = ""
    source_file: str = ""
    source_type: str = ""  # pdf, docx, text, url


# ─── Requirement Analysis ────────────────────────────────────────────────────

class Requirement(BaseModel):
    """Individual requirement extracted from the document."""
    id: str = ""
    title: str = ""
    description: str = ""
    category: str = ""           # e.g., Frontend, Backend, Database, DevOps, etc.
    priority: str = "Medium"     # High, Medium, Low
    complexity: str = "Medium"   # High, Medium, Low
    estimated_hours: float = 0.0
    required_role: str = ""      # maps to DEVELOPER_RATES key
    technologies: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)


class ProjectAnalysis(BaseModel):
    """Structured analysis of the requirement document."""
    client_name: str = "Unspecified Client"
    project_name: str = ""
    project_description: str = ""
    project_type: str = ""         # Web App, Mobile App, API, etc.
    target_audience: str = ""
    tech_stack_suggested: list[str] = Field(default_factory=list)
    requirements: list[Requirement] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)


# ─── Cost Estimation ─────────────────────────────────────────────────────────

class RoleEstimate(BaseModel):
    """Hours and cost for a specific role."""
    role_key: str = ""
    role_label: str = ""
    hours: float = 0.0
    rate_per_hour: float = 0.0
    total_cost: float = 0.0


class CategoryBreakdown(BaseModel):
    """Cost breakdown by requirement category."""
    category: str = ""
    requirements_count: int = 0
    total_hours: float = 0.0
    total_cost: float = 0.0
    items: list[dict] = Field(default_factory=list)


class CostEstimation(BaseModel):
    """Full project cost estimation."""
    role_estimates: list[RoleEstimate] = Field(default_factory=list)
    category_breakdown: list[CategoryBreakdown] = Field(default_factory=list)
    total_development_hours: float = 0.0
    total_development_cost: float = 0.0
    # Extras determined via web search
    infrastructure_cost_monthly: float = 0.0
    third_party_licenses_monthly: float = 0.0
    miscellaneous_costs: float = 0.0
    contingency_percentage: float = 15.0
    contingency_amount: float = 0.0
    grand_total: float = 0.0


# ─── Web Search Results ──────────────────────────────────────────────────────

class WebSearchItem(BaseModel):
    """Single web search result."""
    query: str = ""
    answer: str = ""
    estimated_cost: Optional[float] = None
    cost_type: str = ""           # monthly, one-time, per-unit
    sources: list[str] = Field(default_factory=list)


class WebSearchResults(BaseModel):
    """Collection of web search verification results."""
    items: list[WebSearchItem] = Field(default_factory=list)
    infrastructure_estimates: list[WebSearchItem] = Field(default_factory=list)
    technology_cost_estimates: list[WebSearchItem] = Field(default_factory=list)


# ─── Final Quotation ─────────────────────────────────────────────────────────

class Quotation(BaseModel):
    """Final structured quotation."""
    project_name: str = ""
    generated_at: str = ""
    analysis: Optional[ProjectAnalysis] = None
    cost_estimation: Optional[CostEstimation] = None
    web_search_data: Optional[WebSearchResults] = None
    quotation_markdown: str = ""
