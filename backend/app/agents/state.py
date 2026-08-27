"""
LangGraph State — the shared data structure passed between all agent nodes.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Optional, TypedDict


class PipelineState(TypedDict, total=False):
    """
    Shared state for the LangGraph pipeline.
    Each node reads what it needs and writes its outputs.
    """

    # ── Input ──
    raw_input: str                       # Original input (file path, URL, or pasted text)
    input_type: str                      # "file", "url", or "text"

    # ── Stage 1: Ingestion ──
    ingested_text: str                   # Text extracted from DOCX/text/URL (non-PDF)
    file_path: str                       # Path to file (for PDF → OCR)
    file_type: str                       # pdf, docx, text
    needs_ocr: bool                      # Whether OCR is required

    # ── Stage 2: OCR ──
    ocr_result: dict                     # OCRResult as dict
    document_text: str                   # Final clean text for analysis

    # ── Stage 3: Requirement Analysis ──
    project_analysis: dict               # ProjectAnalysis as dict

    # ── Stage 4: Cost Estimation ──
    cost_estimation: dict                # CostEstimation as dict
    estimation_retry_count: int           # How many times estimation has been re-run to fix validation errors
    validation_feedback: list[str]        # Errors from the last failed validation, fed back into re-estimation

    # ── Stage 5: Web Search ──
    web_search_results: dict             # WebSearchResults as dict
    web_search_cache: dict               # {signature, web_search_results, total_infra, total_licenses} — skips
                                          # re-searching Gemini when a validation retry didn't change queries

    # ── Stage 5b: Validation gate ──
    quotation_validation: dict           # Internal health report (errors/warnings) — computed once, blocking

    # ── Stage 6: Quotation ──
    quotation_markdown: str              # Final MD quotation
    quotation_json: dict                 # Full quotation as JSON

    # ── Stage 7: BRD & SRS ──
    generate_brd: bool                   # Whether to generate BRD
    generate_srs: bool                   # Whether to generate SRS
    brd_markdown: str                    # Final MD Business Requirements Document
    srs_markdown: str                    # Final MD Software Requirements Specification

    # ── Metadata ──
    errors: Annotated[list[str], operator.add]   # Accumulate errors
    log: Annotated[list[str], operator.add]      # Accumulate log messages
    current_stage: str                   # Current processing stage
