"""
Quotation Agent — Generates the final structured quotation in Markdown format
with proper tables, combining all pipeline outputs.
"""

from __future__ import annotations

import json
from datetime import datetime

import config
from agents.state import PipelineState


async def quotation_node(state: PipelineState) -> dict:
    """
    Generate a structured markdown quotation from all pipeline data.
    """
    log = ["📄 Quotation: Generating final quotation document"]

    analysis = state.get("project_analysis", {})
    estimation = state.get("cost_estimation", {})
    web_data = state.get("web_search_results", {})
    rates = config.DEVELOPER_RATES

    now = datetime.now().strftime("%B %d, %Y")
    project_name = analysis.get("project_name", "Untitled Project")

    md = []

    # ── Header ──
    md.append(f"# 📋 Project Quotation: {project_name}")
    md.append(f"\n**Generated:** {now}  ")
    md.append(f"**Document Type:** Automated Cost Estimation  ")
    md.append(f"**Status:** Draft — Subject to Review\n")
    md.append("---\n")

    # ── 1. Executive Summary ──
    md.append("## 1. Executive Summary\n")
    md.append(f"| Field | Details |")
    md.append(f"|-------|---------|")
    md.append(f"| **Project Name** | {project_name} |")
    md.append(f"| **Project Type** | {analysis.get('project_type', 'N/A')} |")
    md.append(f"| **Target Audience** | {analysis.get('target_audience', 'N/A')} |")
    md.append(f"| **Estimated Duration** | {estimation.get('timeline_weeks', 'TBD')} weeks |")
    md.append(f"| **Total Requirements** | {len(analysis.get('requirements', []))} items |")
    md.append(f"| **Grand Total** | **₹{estimation.get('grand_total', 0):,.2f}** |")
    md.append("")
    md.append(f"**Description:** {analysis.get('project_description', 'N/A')}\n")

    # ── 2. Recommended Tech Stack ──
    tech_stack = analysis.get("tech_stack_suggested", [])
    if tech_stack:
        md.append("## 2. Recommended Technology Stack\n")
        md.append("| # | Technology |")
        md.append("|---|-----------|")
        for i, tech in enumerate(tech_stack, 1):
            md.append(f"| {i} | {tech} |")
        md.append("")

    # ── 3. Requirements Breakdown ──
    requirements = analysis.get("requirements", [])
    adjusted = {r["id"]: r for r in estimation.get("adjusted_requirements", [])}

    if requirements:
        md.append("## 3. Requirements Breakdown\n")

        # Group by category
        categories = {}
        for req in requirements:
            cat = req.get("category", "General")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(req)

        for cat, reqs in categories.items():
            md.append(f"### 📂 {cat}\n")
            md.append("| ID | Requirement | Priority | Complexity | Hours | Role |")
            md.append("|-----|------------|----------|-----------|-------|------|")
            for req in reqs:
                req_id = req.get("id", "")
                adj = adjusted.get(req_id, {})
                hours = adj.get("estimated_hours", req.get("estimated_hours", 0))
                role_key = adj.get("required_role", req.get("required_role", "mid_developer"))
                role_label = rates.get(role_key, {}).get("label", role_key)
                md.append(
                    f"| {req_id} | {req.get('title', '')} | "
                    f"{req.get('priority', 'Medium')} | {req.get('complexity', 'Medium')} | "
                    f"{hours:.0f} | {role_label} |"
                )
            md.append("")

    # ── 4. Team Composition ──
    team = estimation.get("team_composition", [])
    if team:
        md.append("## 4. Team Composition\n")
        md.append("| Role | Count | Hourly Rate (INR) | Justification |")
        md.append("|------|-------|--------------------|---------------|")
        for member in team:
            role_key = member.get("role_key", "")
            rate_info = rates.get(role_key, {})
            md.append(
                f"| {rate_info.get('label', role_key)} | {member.get('count', 1)} | "
                f"₹{rate_info.get('rate_per_hour', 0)} | {member.get('justification', '')} |"
            )
        md.append("")

    # ── 5. Cost Breakdown by Role ──
    role_estimates = estimation.get("role_estimates", [])
    if role_estimates:
        md.append("## 5. Cost Breakdown by Role\n")
        md.append("| Role | Hours | Rate (₹/hr) | Subtotal (INR) |")
        md.append("|------|-------|-------------|----------------|")
        for re in sorted(role_estimates, key=lambda x: x.get("total_cost", 0), reverse=True):
            md.append(
                f"| {re.get('role_label', '')} | {re.get('hours', 0):.0f} | "
                f"₹{re.get('rate_per_hour', 0):.0f} | ₹{re.get('total_cost', 0):,.2f} |"
            )
        md.append(
            f"| **TOTAL** | **{estimation.get('total_development_hours', 0):.0f}** | "
            f"— | **₹{estimation.get('total_development_cost', 0):,.2f}** |"
        )
        md.append("")

    # ── 6. Cost Breakdown by Category ──
    cat_breakdown = estimation.get("category_breakdown", [])
    if cat_breakdown:
        md.append("## 6. Cost Breakdown by Category\n")
        md.append("| Category | Requirements | Hours | Cost (INR) |")
        md.append("|----------|-------------|-------|------------|")
        for cb in sorted(cat_breakdown, key=lambda x: x.get("total_cost", 0), reverse=True):
            md.append(
                f"| {cb.get('category', '')} | {cb.get('requirements_count', 0)} | "
                f"{cb.get('total_hours', 0):.0f} | ₹{cb.get('total_cost', 0):,.2f} |"
            )
        md.append("")

    # ── 7. Infrastructure & Third-Party Costs (from Web Search) ──
    web_items = web_data.get("items", [])
    if web_items:
        md.append("## 7. Infrastructure & Third-Party Costs (Web Research)\n")
        md.append("| # | Item | Estimated Cost | Type | Details |")
        md.append("|---|------|---------------|------|---------|")
        for i, item in enumerate(web_items, 1):
            cost = item.get("estimated_cost")
            cost_str = f"₹{cost:,.2f}" if cost else "TBD"
            md.append(
                f"| {i} | {item.get('query', '')} | {cost_str} | "
                f"{item.get('cost_type', 'N/A')} | {item.get('answer', '')[:100]}... |"
            )
        md.append("")
        md.append(f"**Monthly Infrastructure Cost:** ₹{estimation.get('infrastructure_cost_monthly', 0):,.2f}  ")
        md.append(f"**Monthly License/Service Cost:** ₹{estimation.get('third_party_licenses_monthly', 0):,.2f}\n")

    # ── 8. Project Phases & Timeline ──
    phases = estimation.get("phases", [])
    if phases:
        md.append("## 8. Project Timeline\n")
        md.append("| Phase | Duration | Description |")
        md.append("|-------|----------|-------------|")
        for phase in phases:
            md.append(
                f"| {phase.get('name', '')} | {phase.get('duration_weeks', 0)} weeks | "
                f"{phase.get('description', '')} |"
            )
        md.append(f"\n**Total Estimated Duration:** {estimation.get('timeline_weeks', 'TBD')} weeks\n")

    # ── 9. Grand Total Summary ──
    md.append("## 9. 💰 Grand Total Summary\n")
    md.append("| Cost Component | Amount (INR) |")
    md.append("|----------------|--------------|")
    md.append(f"| Development Cost | ₹{estimation.get('total_development_cost', 0):,.2f} |")
    md.append(f"| Contingency ({estimation.get('contingency_percentage', 15)}%) | ₹{estimation.get('contingency_amount', 0):,.2f} |")

    infra_6mo = estimation.get("infrastructure_cost_monthly", 0) * 6
    license_6mo = estimation.get("third_party_licenses_monthly", 0) * 6
    if infra_6mo > 0:
        md.append(f"| Infrastructure (6 months) | ₹{infra_6mo:,.2f} |")
    if license_6mo > 0:
        md.append(f"| Licenses & Services (6 months) | ₹{license_6mo:,.2f} |")

    md.append(f"| **GRAND TOTAL** | **₹{estimation.get('grand_total', 0):,.2f}** |")
    md.append("")

    # ── 10. Assumptions & Risks ──
    assumptions = analysis.get("assumptions", [])
    risks = analysis.get("risks", [])
    out_of_scope = analysis.get("out_of_scope", [])

    if assumptions:
        md.append("## 10. Assumptions\n")
        for a in assumptions:
            md.append(f"- {a}")
        md.append("")

    if risks:
        md.append("## 11. Identified Risks\n")
        for r in risks:
            md.append(f"- ⚠️ {r}")
        md.append("")

    if out_of_scope:
        md.append("## 12. Out of Scope\n")
        for o in out_of_scope:
            md.append(f"- ❌ {o}")
        md.append("")

    # ── Footer ──
    md.append("---\n")
    md.append("*This quotation was auto-generated by Pixous Technologies.*  ")
    md.append("*All estimates are subject to detailed technical review and scope confirmation.*  ")
    md.append(f"*Generated on {now}.*")

    quotation_md = "\n".join(md)

    # Build JSON output
    quotation_json = {
        "project_name": project_name,
        "generated_at": now,
        "analysis": analysis,
        "cost_estimation": estimation,
        "web_search_data": web_data,
    }

    log.append(f"   ✅ Quotation generated ({len(quotation_md)} chars)")

    return {
        "quotation_markdown": quotation_md,
        "quotation_json": quotation_json,
        "log": log,
        "current_stage": "quotation_complete",
    }
