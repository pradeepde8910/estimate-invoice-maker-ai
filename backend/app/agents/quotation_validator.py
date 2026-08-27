"""
Quotation Validator — Runs deterministic consistency checks on the
estimation output before the quotation document is generated.

Returns a QuotationValidationResult with errors, warnings, and
a structured summary for the internal health report.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.state import PipelineState


@dataclass
class QuotationValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
        }


def validate_quotation(analysis: dict, estimation: dict) -> QuotationValidationResult:
    """
    Run 13 deterministic checks against the pipeline output.
    All arithmetic uses Python float comparison with a ₹1 epsilon for rounding.
    No LLM calls are made.
    """
    result = QuotationValidationResult()
    epsilon = 1.0  # ₹1 tolerance for float rounding

    unit_estimates = estimation.get("unit_estimates", [])
    team_composition = estimation.get("team_composition", [])
    phases = estimation.get("phases", [])
    estimation_assumptions = estimation.get("estimation_assumptions", [])
    total_development_cost = float(estimation.get("total_development_cost", 0))
    contingency_amount = float(estimation.get("contingency_amount", 0))
    infra_monthly = float(estimation.get("infrastructure_cost_monthly", 0))
    license_monthly = float(estimation.get("third_party_licenses_monthly", 0))
    grand_total = float(estimation.get("grand_total", 0))
    contingency_pct = float(estimation.get("contingency_percentage", 15))

    # Build a flat requirement map across all units
    req_to_units: dict[str, list[str]] = {}  # req_id -> [unit labels]
    all_req_estimates: list[dict] = []
    for u in unit_estimates:
        u_label = u.get("label", u.get("unit_id", "Unknown"))
        for req in u.get("requirement_estimates", []):
            rid = req.get("requirement_id", "")
            if rid:
                req_to_units.setdefault(rid, []).append(u_label)
            all_req_estimates.append(req)

    # Build set of all original requirement IDs from analysis
    original_req_ids: set[str] = set()
    for pu in analysis.get("project_units", []):
        for req in pu.get("requirements", []):
            rid = req.get("id", "")
            if rid:
                original_req_ids.add(rid)

    # ── Check 1: Every requirement is mapped to at least one unit ──
    unmapped = original_req_ids - set(req_to_units.keys())
    if unmapped:
        result.errors.append(
            f"Check 1 FAIL — {len(unmapped)} requirement(s) not mapped to any unit: {', '.join(sorted(unmapped))}"
        )

    # ── Check 2: No requirement is mapped to more than one unit ──
    duplicate_mapped = {rid: units for rid, units in req_to_units.items() if len(units) > 1}
    if duplicate_mapped:
        for rid, units in duplicate_mapped.items():
            result.errors.append(
                f"Check 2 FAIL — Requirement '{rid}' mapped to multiple units: {', '.join(units)}"
            )

    # ── Checks 3, 4, 5, 6: Per-requirement scope/task/hours/role checks ──
    for req in all_req_estimates:
        rid = req.get("requirement_id", "?")
        title = req.get("title", rid)
        scope = req.get("scope_status", "IN_SCOPE").upper()
        tasks = req.get("implementation_tasks", [])
        hours = float(req.get("hours", 0))
        reason = req.get("adjustment_reason", "")

        if scope == "IN_SCOPE":
            # Check 3: IN_SCOPE must have hours > 0
            if hours <= 0:
                result.errors.append(
                    f"Check 3 FAIL — IN_SCOPE requirement '{title}' ({rid}) has 0 hours."
                )
            # Check 5: Must have at least one task
            if not tasks:
                result.errors.append(
                    f"Check 5 FAIL — IN_SCOPE requirement '{title}' ({rid}) has no implementation tasks."
                )
            else:
                # Check 6: Every task must have a role and hours > 0
                for i, t in enumerate(tasks):
                    if not t.get("role_key"):
                        result.errors.append(
                            f"Check 6 FAIL — Task #{i+1} of '{title}' ({rid}) has no role assigned."
                        )
                    if float(t.get("hours", 0)) <= 0:
                        result.errors.append(
                            f"Check 6 FAIL — Task #{i+1} of '{title}' ({rid}) has 0 hours."
                        )
        elif scope == "OUT_OF_SCOPE":
            # Check 4: OUT_OF_SCOPE must have hours == 0 and a reason
            if hours > 0:
                result.errors.append(
                    f"Check 4 FAIL — OUT_OF_SCOPE requirement '{title}' ({rid}) has non-zero hours ({hours}h)."
                )
            if not reason or reason.lower() == "no change":
                result.errors.append(
                    f"Check 4 FAIL — OUT_OF_SCOPE requirement '{title}' ({rid}) has no exclusion reason."
                )

    # ── Check 7: sum(unit costs) == total_development_cost ──
    sum_unit_costs = sum(float(u.get("estimate", {}).get("cost", 0)) for u in unit_estimates)
    diff_7 = abs(sum_unit_costs - total_development_cost)
    if diff_7 >= epsilon:
        result.errors.append(
            f"Check 7 FAIL — Sum of unit costs (₹{sum_unit_costs:,.2f}) ≠ "
            f"total_development_cost (₹{total_development_cost:,.2f}). Delta: ₹{diff_7:,.2f}"
        )

    # ── Check 8: sum(category costs) == total_development_cost ──
    category_breakdown = estimation.get("category_breakdown", [])
    sum_cat_costs = sum(float(c.get("total_cost", 0)) for c in category_breakdown)
    diff_8 = abs(sum_cat_costs - total_development_cost)
    if category_breakdown and diff_8 >= epsilon:
        result.errors.append(
            f"Check 8 FAIL — Sum of category costs (₹{sum_cat_costs:,.2f}) ≠ "
            f"total_development_cost (₹{total_development_cost:,.2f}). Delta: ₹{diff_8:,.2f}"
        )

    # ── Check 9: grand_total == development + contingency + infra + licenses ──
    infra_6mo = infra_monthly * 6
    license_6mo = license_monthly * 6
    expected_grand = total_development_cost + contingency_amount + infra_6mo + license_6mo
    diff_9 = abs(grand_total - expected_grand)
    if diff_9 >= epsilon:
        result.errors.append(
            f"Check 9 FAIL — grand_total (₹{grand_total:,.2f}) ≠ "
            f"development + contingency + infra + licenses (₹{expected_grand:,.2f}). Delta: ₹{diff_9:,.2f}"
        )

    # ── Check 10: Every BILLABLE team role has allocated task hours > 0 ──
    # Build set of role_keys that actually have task hours
    role_keys_with_hours: set[str] = set()
    for u in unit_estimates:
        for req in u.get("requirement_estimates", []):
            for t in req.get("implementation_tasks", []):
                rk = t.get("role_key", "")
                if rk and float(t.get("hours", 0)) > 0:
                    role_keys_with_hours.add(rk)

    for member in team_composition:
        rk = member.get("role_key", "")
        billing = member.get("billing_status", "BILLABLE").upper()
        if billing == "BILLABLE" and rk not in role_keys_with_hours:
            # This is a hard error, not a warning: a BILLABLE role at a nonzero
            # hourly rate with zero task hours means its cost is silently
            # missing from grand_total while the document still lists it as
            # a paid team member — a real pricing misrepresentation, not just
            # a cosmetic inconsistency.
            result.errors.append(
                f"Check 10 FAIL — BILLABLE team role '{rk}' has no allocated task hours anywhere, "
                f"so its cost is missing from grand_total. Either assign it real implementation_tasks "
                f"hours, or mark it NON_BILLABLE with a justification (e.g. cost absorbed into contingency)."
            )
        # NON_BILLABLE roles with hours would be a data inconsistency too
        if billing == "NON_BILLABLE" and rk in role_keys_with_hours:
            result.warnings.append(
                f"Check 10 WARN — NON_BILLABLE team role '{rk}' has task hours allocated — consider marking BILLABLE."
            )

    # ── Check 11: Billing unit cost delta (WARNING only) ──
    billing_units = [u for u in unit_estimates if u.get("billing", {}).get("is_billing_unit") is True]
    if billing_units:
        sum_billing = sum(float(u.get("estimate", {}).get("cost", 0)) for u in billing_units)
        delta_11 = abs(sum_billing - total_development_cost)
        if delta_11 >= epsilon:
            result.warnings.append(
                f"Check 11 WARN — Billing unit total (₹{sum_billing:,.2f}) ≠ "
                f"development cost (₹{total_development_cost:,.2f}). Delta: ₹{delta_11:,.2f}. "
                f"Verify this is intentional (partial billing scenario)."
            )

    # ── Check 12: Timeline phases correspond to a priced unit ──
    unit_labels_lower = {u.get("label", "").lower().strip() for u in unit_estimates}
    for phase in phases:
        phase_name = phase.get("name", "").lower().strip()
        if phase_name and phase_name not in unit_labels_lower:
            # Partial match fallback
            matched = any(phase_name in lbl or lbl in phase_name for lbl in unit_labels_lower)
            if not matched:
                result.warnings.append(
                    f"Check 12 WARN — Timeline phase '{phase.get('name')}' has no corresponding priced unit. "
                    f"Ghost work may appear in timeline but not in costing."
                )

    # ── Check 13: Infrastructure costs backed by structured assumptions ──
    web_items_raw = []  # Not directly in estimation — checked via presence of estimation_assumptions
    # If infrastructure cost is present, each item should have configuration + billing_model
    # We can check estimation_assumptions as a proxy (they are set by the estimation agent)
    if (infra_monthly > 0 or license_monthly > 0) and not estimation_assumptions:
        result.warnings.append(
            "Check 13 WARN — Infrastructure/license costs present but no estimation_assumptions provided. "
            "Service costs should be accompanied by configuration assumptions (tier, usage, billing model)."
        )

    # ── Check 14: Cross-unit capability overlap detection ──
    # Multi-level similarity: normalized title + keyword intersection.
    # Flags WARNING when two requirements in different units share substantial overlap,
    # but does NOT auto-delete either — it surfaces them for human review.
    def _normalize_title(title: str) -> set:
        """Lowercase, strip punctuation, remove stop words."""
        import re as _re
        stop = {"a", "an", "the", "and", "or", "of", "for", "to", "in",
                "with", "by", "on", "at", "from", "is", "are", "that",
                "this", "it", "its", "as", "be", "will", "shall"}
        words = _re.sub(r"[^a-z0-9\s]", "", title.lower()).split()
        return set(w for w in words if w not in stop and len(w) > 2)

    # Build requirement index per unit for Check 14, keeping each unit's own
    # label keywords (phase/entity name) alongside the requirement title
    # keywords — needed below to distinguish accidental duplication from
    # intentional per-entity/per-phase scope replication.
    unit_req_index: list[tuple[str, str, str, set, set]] = []
    # (unit_id, req_id, title, title_keywords, unit_label_keywords)
    for u in unit_estimates:
        u_id = u.get("unit_id", "")
        label_kw = _normalize_title(u.get("label", u_id))
        for r in u.get("requirement_estimates", []):
            if r.get("scope_status", "IN_SCOPE").upper() == "IN_SCOPE":
                title = r.get("title", "")
                kw = _normalize_title(title)
                if len(kw) >= 2:
                    unit_req_index.append((u_id, r.get("requirement_id", ""), title, kw, label_kw))

    overlap_warnings: list[str] = []
    seen_overlap_pairs: set[frozenset] = set()
    for i in range(len(unit_req_index)):
        u_id_a, req_id_a, title_a, kw_a, label_kw_a = unit_req_index[i]
        for j in range(i + 1, len(unit_req_index)):
            u_id_b, req_id_b, title_b, kw_b, label_kw_b = unit_req_index[j]
            # Only check cross-unit pairs
            if u_id_a == u_id_b:
                continue
            pair = frozenset([req_id_a, req_id_b])
            if pair in seen_overlap_pairs:
                continue
            seen_overlap_pairs.add(pair)
            if not (kw_a and kw_b):
                continue
            # Jaccard similarity on normalised keyword sets
            intersection = len(kw_a & kw_b)
            union = len(kw_a | kw_b)
            similarity = intersection / union if union > 0 else 0
            if similarity < 0.5:  # below 50% keyword overlap → not worth flagging
                continue

            # Entity/phase-qualifier correlation filter: two units almost
            # always differ in their label (different phase number, entity
            # name, region, ...). If a word that is UNIQUE to one unit's own
            # label (e.g. "uae", present in the UAE phase's label but not the
            # India phase's) also shows up in that same unit's requirement
            # title, the title is explicitly self-tagged with its unit's
            # distinguishing qualifier — e.g. "UAE Payroll Configuration" in
            # the UAE phase vs "India Payroll Configuration" in the India
            # phase. That is the standard shape of legitimate incremental
            # scope across parallel entity/phase rollouts, not accidental
            # duplication, so it's suppressed rather than flagged.
            label_diff_a = label_kw_a - label_kw_b
            label_diff_b = label_kw_b - label_kw_a
            entity_correlated = bool((kw_a & label_diff_a) or (kw_b & label_diff_b))
            if entity_correlated:
                continue

            unit_label_a = next((u.get("label", u_id_a) for u in unit_estimates if u.get("unit_id") == u_id_a), u_id_a)
            unit_label_b = next((u.get("label", u_id_b) for u in unit_estimates if u.get("unit_id") == u_id_b), u_id_b)
            overlap_warnings.append(
                f"Check 14 WARN — Possible capability overlap ({similarity:.0%} similarity): "
                f"'{title_a}' ({req_id_a}, {unit_label_a}) vs "
                f"'{title_b}' ({req_id_b}, {unit_label_b}). "
                f"Review whether this is duplicate scope or legitimate incremental scope."
            )

    # Limit to top 10 most actionable overlap warnings to keep the report readable
    result.warnings.extend(overlap_warnings[:10])
    if len(overlap_warnings) > 10:
        result.warnings.append(
            f"Check 14 WARN — {len(overlap_warnings) - 10} additional potential overlaps found. "
            "Consider restructuring scope to reduce cross-unit duplication."
        )

    # ── Check 15: Full cost reconciliation audit trail ──
    # Verifies: Σ(task hours × role rate) == total_development_cost
    # This provides a complete mathematical audit trail for the quotation.
    computed_dev_cost = 0.0
    computed_total_hours = 0.0
    for u in unit_estimates:
        for r in u.get("requirement_estimates", []):
            for t in r.get("implementation_tasks", []):
                t_hours = float(t.get("hours", 0))
                t_role = t.get("role_key", "")
                # Get rate from estimation data (already computed in estimation_agent)
                t_cost = float(t.get("cost", 0))
                computed_dev_cost += t_cost
                computed_total_hours += t_hours

    diff_15_cost = abs(computed_dev_cost - total_development_cost)
    if diff_15_cost >= epsilon:
        result.errors.append(
            f"Check 15 FAIL — Cost reconciliation: Σ(task costs) ₹{computed_dev_cost:,.2f} ≠ "
            f"total_development_cost ₹{total_development_cost:,.2f}. Delta: ₹{diff_15_cost:,.2f}. "
            f"This means cost arithmetic is inconsistent — the quotation cannot be audited."
        )

    total_dev_hours_reported = float(estimation.get("total_development_hours", 0))
    diff_15_hours = abs(computed_total_hours - total_dev_hours_reported)
    if diff_15_hours >= 0.5:  # 0.5h tolerance for rounding
        result.warnings.append(
            f"Check 15 WARN — Hour reconciliation: Σ(task hours) {computed_total_hours:.1f}h ≠ "
            f"total_development_hours {total_dev_hours_reported:.1f}h. Delta: {diff_15_hours:.1f}h."
        )

    # Final grand total reconciliation
    expected_grand = total_development_cost + contingency_amount + infra_monthly * 6 + license_monthly * 6
    diff_grand = abs(grand_total - expected_grand)
    if diff_grand >= epsilon:
        result.errors.append(
            f"Check 15 FAIL — Grand total reconciliation: reported ₹{grand_total:,.2f} ≠ "
            f"development + contingency + infra + licenses = ₹{expected_grand:,.2f}. "
            f"Delta: ₹{diff_grand:,.2f}."
        )

    return result



async def validate_node(state: PipelineState) -> dict:
    """
    Blocking validation gate — runs after web_search (once infra/license costs
    are in cost_estimation) and before brd/quotation.

    On hard errors, route back to estimation with the specific failures so the
    LLM can fix them, instead of shipping a flagged-but-still-generated document.
    Bounded by config.MAX_ESTIMATION_VALIDATION_RETRIES so a persistently broken
    estimation can't loop forever.
    """
    from app import config

    log = ["🔍 Validation: Running quotation consistency checks"]

    analysis = state.get("project_analysis", {})
    estimation = state.get("cost_estimation", {})
    retry_count = state.get("estimation_retry_count", 0)

    result = validate_quotation(analysis, estimation)
    log.append(f"   {len(result.errors)} error(s), {len(result.warnings)} warning(s)")

    if result.errors and retry_count < config.MAX_ESTIMATION_VALIDATION_RETRIES:
        log.append(
            f"   ⚠️ Hard validation errors found — sending back to estimation "
            f"(retry {retry_count + 1}/{config.MAX_ESTIMATION_VALIDATION_RETRIES})"
        )
        return {
            "quotation_validation": result.to_dict(),
            "validation_feedback": result.errors,
            "estimation_retry_count": retry_count + 1,
            "log": log,
            "current_stage": "validation_failed_retrying",
        }

    if result.errors:
        log.append(
            f"   ❌ Validation still failing after {retry_count} retries — "
            f"shipping document flagged for manual review"
        )
    else:
        log.append("   ✅ Validation passed")

    return {
        "quotation_validation": result.to_dict(),
        "validation_feedback": [],
        "log": log,
        "current_stage": "validation_complete",
    }
