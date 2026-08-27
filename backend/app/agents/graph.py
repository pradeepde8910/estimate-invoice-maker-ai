"""
LangGraph Workflow — Orchestrates the agentic pipeline.

Flow:
  START → Ingestion → (conditional: OCR or skip) → Analysis → Estimation → Web Search
        → Validate → (conditional: back to Estimation on hard error, else BRD) → SRS → Quotation → END
"""

from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from app.agents.state import PipelineState
from app.agents.ingestion_agent import ingestion_node
from app.agents.ocr_agent import ocr_node
from app.agents.analysis_agent import analysis_node
from app.agents.estimation_agent import estimation_node
from app.agents.web_search_agent import web_search_node
from app.agents.quotation_validator import validate_node
from app.agents.brd_agent import brd_node
from app.agents.srs_agent import srs_node
from app.agents.quotation_agent import quotation_node


def _should_run_ocr(state: PipelineState) -> str:
    """Conditional edge: route to OCR if the document is a PDF, otherwise skip."""
    if state.get("needs_ocr", False):
        return "ocr"
    return "analysis"


def _should_retry_estimation(state: PipelineState) -> str:
    """Conditional edge: send hard validation failures back to estimation for a bounded number of retries."""
    if state.get("current_stage") == "validation_failed_retrying":
        return "estimation"
    return "brd"


def build_pipeline() -> StateGraph:
    """
    Build and compile the LangGraph pipeline.

    Graph structure:
    ┌─────────┐    ┌─────┐    ┌──────────┐    ┌────────────┐    ┌────────────┐    ┌──────────┐    ┌─────┐    ┌─────┐    ┌───────────┐
    │Ingestion│───▸│ OCR │───▸│ Analysis │───▸│ Estimation │◂──▸│ Web Search │───▸│ Validate │───▸│ BRD │───▸│ SRS │───▸│ Quotation │
    └─────────┘    └─────┘    └──────────┘    └────────────┘    └────────────┘    └──────────┘    └─────┘    └─────┘    └───────────┘
         │                         ▲                                                    │
         └─────── (skip OCR) ──────┘                                                    └── (bounded retry on hard error) ──┘
    """
    builder = StateGraph(PipelineState)

    # ── Add Nodes ──
    builder.add_node("ingestion", ingestion_node)
    builder.add_node("ocr", ocr_node)
    builder.add_node("analysis", analysis_node)
    builder.add_node("estimation", estimation_node)
    builder.add_node("web_search", web_search_node)
    builder.add_node("validate", validate_node)
    builder.add_node("brd", brd_node)
    builder.add_node("srs", srs_node)
    builder.add_node("quotation", quotation_node)

    # ── Add Edges ──
    # START → Ingestion
    builder.add_edge(START, "ingestion")

    # Ingestion → Conditional (OCR or skip to Analysis)
    builder.add_conditional_edges(
        "ingestion",
        _should_run_ocr,
        {
            "ocr": "ocr",
            "analysis": "analysis",
        },
    )

    # OCR → Analysis
    builder.add_edge("ocr", "analysis")

    # Analysis → Estimation → Web Search → Validate
    builder.add_edge("analysis", "estimation")
    builder.add_edge("estimation", "web_search")
    builder.add_edge("web_search", "validate")

    # Validate → Conditional (back to Estimation on hard error, else continue to BRD)
    builder.add_conditional_edges(
        "validate",
        _should_retry_estimation,
        {
            "estimation": "estimation",
            "brd": "brd",
        },
    )

    # BRD → SRS → Quotation → END
    builder.add_edge("brd", "srs")
    builder.add_edge("srs", "quotation")
    builder.add_edge("quotation", END)

    # Compile
    graph = builder.compile()
    return graph


async def run_pipeline(
    raw_input: str,
    generate_brd: bool = False,
    generate_srs: bool = False
) -> PipelineState:
    """
    Execute the full pipeline on the given input.

    Args:
        raw_input: File path, URL, or pasted text content.
        generate_brd: Whether to generate the Business Requirements Document.
        generate_srs: Whether to generate the Software Requirements Specification.

    Returns:
        Final PipelineState with all results.
    """
    graph = build_pipeline()

    initial_state: PipelineState = {
        "raw_input": raw_input,
        "generate_brd": generate_brd,
        "generate_srs": generate_srs,
        "errors": [],
        "log": ["🚀 Pipeline started"],
        "current_stage": "initialized",
    }

    final_state = await graph.ainvoke(initial_state)
    return final_state
