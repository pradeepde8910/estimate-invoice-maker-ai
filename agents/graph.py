"""
LangGraph Workflow — Orchestrates the agentic pipeline.

Flow:
  START → Ingestion → (conditional: OCR or skip) → Analysis → Estimation → Web Search → Quotation → END
"""

from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from agents.state import PipelineState
from agents.ingestion_agent import ingestion_node
from agents.ocr_agent import ocr_node
from agents.analysis_agent import analysis_node
from agents.estimation_agent import estimation_node
from agents.web_search_agent import web_search_node
from agents.brd_agent import brd_node
from agents.srs_agent import srs_node
from agents.quotation_agent import quotation_node


def _should_run_ocr(state: PipelineState) -> str:
    """Conditional edge: route to OCR if the document is a PDF, otherwise skip."""
    if state.get("needs_ocr", False):
        return "ocr"
    return "analysis"


def build_pipeline() -> StateGraph:
    """
    Build and compile the LangGraph pipeline.

    Graph structure:
    ┌─────────┐    ┌─────┐    ┌──────────┐    ┌────────────┐    ┌────────────┐    ┌─────┐    ┌─────┐    ┌───────────┐
    │Ingestion│───▸│ OCR │───▸│ Analysis │───▸│ Estimation │───▸│ Web Search │───▸│ BRD │───▸│ SRS │───▸│ Quotation │
    └─────────┘    └─────┘    └──────────┘    └────────────┘    └────────────┘    └─────┘    └─────┘    └───────────┘
         │                         ▲
         └─────── (skip OCR) ──────┘
    """
    builder = StateGraph(PipelineState)

    # ── Add Nodes ──
    builder.add_node("ingestion", ingestion_node)
    builder.add_node("ocr", ocr_node)
    builder.add_node("analysis", analysis_node)
    builder.add_node("estimation", estimation_node)
    builder.add_node("web_search", web_search_node)
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

    # Analysis → Estimation → Web Search → BRD → SRS → Quotation → END
    builder.add_edge("analysis", "estimation")
    builder.add_edge("estimation", "web_search")
    builder.add_edge("web_search", "brd")
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
