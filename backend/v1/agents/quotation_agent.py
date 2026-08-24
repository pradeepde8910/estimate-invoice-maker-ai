"""
Quotation Agent — Generates the final structured quotation in Markdown format.
Follows the traceable chain: Requirement → Tasks → Role → Hours → Cost → Phase → Total.

Validation health report is returned separately in pipeline state (internal only).
The client-facing document gets a clean Estimation Notes section.
"""

from __future__ import annotations

import json
from datetime import datetime

import config
from agents.state import PipelineState


def _md_cell(text) -> str:
    """
    Sanitize free text (LLM-authored strings) before it goes into a markdown
    table cell. A raw '|' or newline in the text is column-delimiter syntax to
    the renderer, not a literal character — left unescaped it silently shifts
    every following cell in the row.
    """
    if text is None:
        return ""
    return str(text).replace("|", "/").replace("\n", " ").strip()


async def quotation_node(state: PipelineState) -> dict:
    """
    Generate a structured markdown quotation from all pipeline data.

    Validation already ran (and blocked/retried estimation) in the "validate"
    node upstream — this node only reads the resulting health report, it does
    not re-run checks itself.
    """
    log = ["📄 Quotation: Generating final quotation document"]

    analysis = state.get("project_analysis", {})
    estimation = state.get("cost_estimation", {})
    web_data = state.get("web_search_results", {})
    rates = config.DEVELOPER_RATES

    now = datetime.now().strftime("%B %d, %Y")
    project_name = analysis.get("project_name", "Untitled Project")
    client_name = analysis.get("client_name", "Unspecified Client")

    validation_dict = state.get("quotation_validation", {})
    is_valid = validation_dict.get("is_valid", True)
    error_count = validation_dict.get("error_count", 0)
    warning_count = validation_dict.get("warning_count", 0)
    log.append(f"   🔍 Validation (from upstream gate): {error_count} error(s), {warning_count} warning(s)")
    if not is_valid:
        log.append(f"   ⚠️ Quotation still has validation errors after retries — document generated but flagged for review")

    md = []
    section_num = [0]  # list so the nested closure can mutate it

    def section(title: str) -> str:
        section_num[0] += 1
        return f"## {section_num[0]}. {title}\n"

    # ── Header ──
    md.append(f"# 📋 Project Quotation: {project_name}")
    md.append(f"\n**Prepared for:** {client_name}  ")
    md.append(f"**Generated:** {now}  ")
    md.append(f"**Document Type:** Automated Cost Estimation  ")
    status_flag = "⚠️ Flagged for Review" if not is_valid else "Draft — Subject to Review"
    md.append(f"**Status:** {status_flag}\n")
    md.append("---\n")

    # ── 1. Executive Summary ──
    md.append(section("Executive Summary"))
    md.append("| Field | Details |")
    md.append("|-------|---------|")
    md.append(f"| **Client** | {client_name} |")
    md.append(f"| **Project Name** | {project_name} |")
    md.append(f"| **Project Type** | {analysis.get('project_type', 'N/A')} |")
    md.append(f"| **Target Audience** | {analysis.get('target_audience', 'N/A')} |")
    md.append(f"| **Estimated Duration** | {estimation.get('timeline_weeks', 'TBD')} weeks |")

    unit_estimates = estimation.get("unit_estimates", [])
    total_reqs = sum(len(u.get("requirement_estimates", [])) for u in unit_estimates)
    in_scope_reqs = sum(
        1 for u in unit_estimates
        for r in u.get("requirement_estimates", [])
        if r.get("scope_status", "IN_SCOPE") == "IN_SCOPE"
    )
    out_scope_reqs = total_reqs - in_scope_reqs

    md.append(f"| **Requirements (In Scope)** | {in_scope_reqs} items |")
    if out_scope_reqs:
        md.append(f"| **Requirements (Out of Scope)** | {out_scope_reqs} items |")
    md.append(f"| **Total Development Hours** | {estimation.get('total_development_hours', 0):.0f} hours |")
    md.append(f"| **Grand Total** | **₹{estimation.get('grand_total', 0):,.2f}** |")
    md.append("")
    md.append(f"**Description:** {analysis.get('project_description', 'N/A')}\n")

    # ── 2. Recommended Tech Stack ──
    tech_stack = analysis.get("tech_stack_suggested", [])
    if tech_stack:
        md.append(section("Recommended Technology Stack"))
        md.append("| # | Technology |")
        md.append("|---|-----------|")
        for i, tech in enumerate(tech_stack, 1):
            md.append(f"| {i} | {tech} |")
        md.append("")

    # ── 3. Delivery Structure & Traceable Requirements ──
    if unit_estimates:
        md.append(section("Delivery Structure & Requirements"))
        md.append(
            "> Each requirement is traced from implementation tasks → role → hours → cost. "
            "Out-of-scope items are listed for completeness but excluded from pricing.\n"
        )

        for unit in unit_estimates:
            label = unit.get("label", "Unknown Unit")
            semantic_type = str(unit.get("semantic_type", "other")).upper()
            unit_cost = unit.get("estimate", {}).get("cost", 0)
            unit_hours = unit.get("estimate", {}).get("hours", 0)

            md.append(f"### 📦 {label} `{semantic_type}`")
            md.append(f"**{unit_hours:.0f} hours** | **₹{unit_cost:,.2f}**\n")

            reqs = unit.get("requirement_estimates", [])
            for req in reqs:
                scope = req.get("scope_status", "IN_SCOPE")
                title = req.get("title", "Untitled")
                req_hours = req.get("hours", 0)
                req_cost = req.get("cost", 0)
                tasks = req.get("implementation_tasks", [])
                reason = req.get("adjustment_reason", "")

                if scope == "OUT_OF_SCOPE":
                    md.append(f"#### ❌ ~~{title}~~ *(Out of Scope)*")
                    if reason:
                        md.append(f"> *Reason: {reason}*\n")
                    continue

                md.append(f"#### ✅ {title}")
                md.append(f"**{req_hours:.0f}h** | **₹{req_cost:,.2f}** | *{req.get('category', 'General')}*\n")

                if tasks:
                    md.append("| # | Implementation Task | Role | Hours | Cost (INR) |")
                    md.append("|---|---------------------|------|-------|------------|")
                    for i, t in enumerate(tasks, 1):
                        md.append(
                            f"| {i} | {_md_cell(t.get('task', 'Task'))} | {_md_cell(t.get('role_label', t.get('role_key', '')))} "
                            f"| {t.get('hours', 0):.0f}h | ₹{t.get('cost', 0):,.2f} |"
                        )
                md.append("")

    # ── 4. Team Composition ──
    team = estimation.get("team_composition", [])
    if team:
        md.append(section("Team Composition"))
        md.append("| Role | Count | Billing | Hourly Rate (INR) | Notes |")
        md.append("|------|-------|---------|-------------------|-------|")
        for member in team:
            role_key = member.get("role_key", "")
            rate_info = rates.get(role_key, {})
            billing = member.get("billing_status", "BILLABLE")
            billing_icon = "💰 Billable" if billing == "BILLABLE" else "🔵 Non-billable"
            md.append(
                f"| {_md_cell(rate_info.get('label', role_key))} | {member.get('count', 1)} | {billing_icon} | "
                f"₹{rate_info.get('rate_per_hour', 0):,} | {_md_cell(member.get('justification', ''))} |"
            )
        md.append("")

    # ── 5. Cost Breakdown by Role ──
    role_estimates = estimation.get("role_estimates", [])
    if role_estimates:
        md.append(section("Cost Breakdown by Role"))
        md.append("| Role | Hours | Rate (₹/hr) | Subtotal (INR) |")
        md.append("|------|-------|-------------|----------------|")
        for re in sorted(role_estimates, key=lambda x: x.get("total_cost", 0), reverse=True):
            md.append(
                f"| {re.get('role_label', '')} | {re.get('hours', 0):.0f} | "
                f"₹{re.get('rate_per_hour', 0):,.0f} | ₹{re.get('total_cost', 0):,.2f} |"
            )
        md.append(
            f"| **TOTAL** | **{estimation.get('total_development_hours', 0):.0f}** | "
            f"— | **₹{estimation.get('total_development_cost', 0):,.2f}** |"
        )
        md.append("")

    # ── 6. Cost Breakdown by Category ──
    cat_breakdown = estimation.get("category_breakdown", [])
    if cat_breakdown:
        md.append(section("Cost Breakdown by Category"))
        md.append("| Category | Requirements | Hours | Cost (INR) |")
        md.append("|----------|-------------|-------|------------|")
        for cb in sorted(cat_breakdown, key=lambda x: x.get("total_cost", 0), reverse=True):
            md.append(
                f"| {cb.get('category', '')} | {cb.get('requirements_count', 0)} | "
                f"{cb.get('total_hours', 0):.0f} | ₹{cb.get('total_cost', 0):,.2f} |"
            )
        md.append("")

    # ── 7. Infrastructure & Third-Party Costs ──
    web_items = web_data.get("items", [])
    if web_items:
        md.append(section("Infrastructure & Service Cost Assumptions"))
        md.append(
            "> Costs are market-rate estimates based on stated configuration assumptions. "
            "Final costs depend on actual usage and selected service provider.\n"
        )
        md.append("| # | Service | Category | Configuration | Billing Model | Monthly Cost (INR) | Basis |")
        md.append("|---|---------|----------|---------------|---------------|--------------------|-------|")
        for i, item in enumerate(web_items, 1):
            config_obj = item.get("configuration", {})
            config_str = ""
            if config_obj:
                parts = []
                if config_obj.get("tier"):
                    parts.append(config_obj["tier"])
                qty = config_obj.get("quantity")
                unit = config_obj.get("unit", "")
                if qty and unit:
                    parts.append(f"{qty} {unit}")
                if config_obj.get("usage_assumption"):
                    parts.append(config_obj["usage_assumption"])
                # NOTE: must not be " | " — that's markdown table column syntax,
                # not a literal separator, and corrupts every column after it.
                config_str = "; ".join(parts) if parts else "—"
            else:
                config_str = "—"

            cost = item.get("monthly_cost_inr") or item.get("estimated_cost")
            cost_str = f"₹{cost:,.2f}" if cost else "TBD"
            service_cat = item.get("service_category", "other").replace("_", " ").title()
            billing = item.get("billing_model", item.get("cost_type", "—"))
            basis = item.get("cost_basis", "Market average")[:60]

            md.append(
                f"| {i} | {_md_cell(item.get('service_name', item.get('query', 'Unknown')))} | {_md_cell(service_cat)} | "
                f"{_md_cell(config_str)} | {_md_cell(billing)} | {cost_str} | {_md_cell(basis)} |"
            )
        md.append("")
        md.append(f"**Total Monthly Infrastructure:** ₹{estimation.get('infrastructure_cost_monthly', 0):,.2f}  ")
        md.append(f"**Total Monthly Licenses & Services:** ₹{estimation.get('third_party_licenses_monthly', 0):,.2f}\n")

    # ── 8. Project Timeline ──
    phases = estimation.get("phases", [])
    if phases:
        md.append(section("Project Timeline"))
        md.append("| Phase | Duration | Description |")
        md.append("|-------|----------|-------------|")
        for phase in phases:
            md.append(
                f"| {_md_cell(phase.get('name', ''))} | {phase.get('duration_weeks', 0)} weeks | "
                f"{_md_cell(phase.get('description', ''))} |"
            )
        md.append(f"\n**Total Estimated Duration:** {estimation.get('timeline_weeks', 'TBD')} weeks\n")

    # ── 9. Grand Total Summary ──
    md.append(section("💰 Grand Total Summary"))
    md.append("| Cost Component | Amount (INR) |")
    md.append("|----------------|--------------|")
    md.append(f"| Development Cost | ₹{estimation.get('total_development_cost', 0):,.2f} |")
    contingency_pct = estimation.get('contingency_percentage', 15)
    md.append(f"| Contingency ({contingency_pct}%) | ₹{estimation.get('contingency_amount', 0):,.2f} |")

    infra_6mo = estimation.get("infrastructure_cost_monthly", 0) * 6
    license_6mo = estimation.get("third_party_licenses_monthly", 0) * 6
    if infra_6mo > 0:
        md.append(f"| Infrastructure (6 months) | ₹{infra_6mo:,.2f} |")
    if license_6mo > 0:
        md.append(f"| Licenses & Services (6 months) | ₹{license_6mo:,.2f} |")

    md.append(f"| **GRAND TOTAL** | **₹{estimation.get('grand_total', 0):,.2f}** |")
    md.append("")

    # ── 10. Estimation Assumptions ──
    estimation_assumptions = estimation.get("estimation_assumptions", [])
    analysis_assumptions = analysis.get("assumptions", [])
    all_assumptions = estimation_assumptions + [
        a for a in analysis_assumptions if a not in estimation_assumptions
    ]
    if all_assumptions:
        md.append(section("Estimation Assumptions"))
        md.append(
            "These assumptions underpin all hour and cost estimates. "
            "Changes to these assumptions may require re-estimation.\n"
        )
        for a in all_assumptions:
            md.append(f"- {a}")
        md.append("")

    # ── 11. Scope Boundaries ──
    risks = analysis.get("risks", [])
    out_of_scope = analysis.get("out_of_scope", [])

    out_of_scope_section_num = None
    if out_of_scope:
        out_of_scope_section_num = section_num[0] + 1
        md.append(section("Out of Scope"))
        for o in out_of_scope:
            md.append(f"- ❌ {_md_cell(o)}")
        md.append("")

    if risks:
        md.append(section("Identified Risks"))
        for r in risks:
            md.append(f"- ⚠️ {_md_cell(r)}")
        md.append("")

    # ── Estimation Notes (client-safe) ──
    md.append(section("Estimation Notes"))
    md.append("- All estimates are based on stated assumptions and are subject to detailed technical review.")
    md.append("- Infrastructure and third-party service costs are based on current market pricing and may vary.")
    if out_of_scope_section_num:
        md.append(f"- Out-of-scope items listed in Section {out_of_scope_section_num} are excluded from all cost calculations.")
    md.append(f"- A {contingency_pct}% contingency is applied to development cost to account for estimation uncertainty.")
    md.append("- Final pricing is subject to scope confirmation and formal contract agreement.\n")

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
