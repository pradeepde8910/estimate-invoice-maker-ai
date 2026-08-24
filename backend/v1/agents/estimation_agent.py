"""
Estimation Agent — Uses Gemini LLM + predefined rate card to calculate
development costs from the structured requirements using Map-Reduce.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections import defaultdict

from google import genai
import json_repair

import config
from agents.state import PipelineState
from utils.key_manager import KeyManager

_gemini_keys = KeyManager(config.GEMINI_API_KEYS)

# These are GUARDRAILS, not hard limits. The LLM may exceed them when justified.
_COMPLEXITY_GUIDE = """
Complexity-to-effort GUARDRAILS (suggested ranges, NOT hard limits):
  - Low complexity:    4-12h   (simple CRUD, UI form, config)
  - Medium complexity: 16-40h  (multi-step workflow, integration, stateful logic)
  - High complexity:   40-80h  (distributed, security-sensitive, migration, multi-tenancy)

IMPORTANT: If estimated effort EXCEEDS the suggested range for a requirement:
  1. Explain WHY in the adjustment_reason field.
  2. Break the requirement into GRANULAR named sub-tasks (do NOT lump into one task).
  3. The total MAY exceed the range when justified — credibility matters more than fitting a bracket.
"""

ESTIMATION_MAP_PROMPT_TEMPLATE = """You are an expert software project estimator.
You are given a SUBSET of project units and requirements to estimate.

""" + _COMPLEXITY_GUIDE + """

You MUST respond with ONLY valid JSON — no markdown, no explanations:
{{
  "adjusted_project_units": [
    {{
      "unit_id": "MUST EXACTLY MATCH the id of the original project_unit",
      "adjusted_requirements": [
        {{
          "id": "MUST EXACTLY MATCH the original requirement id",
          "title": "keep original title",
          "category": "string",
          "scope_status": "IN_SCOPE or OUT_OF_SCOPE",
          "adjustment_reason": "no change, or reason. If hours exceed complexity guardrail, explain here.",
          "incremental_scope_note": "null, or describe ONLY what is new vs a shared global capability",
          "implementation_tasks": [
            {{
              "task": "concrete named activity — NOT generic Implement X",
              "role_key": "MUST EXACTLY MATCH a key from DEVELOPER_RATES",
              "hours": number
            }}
          ]
        }}
      ]
    }}
  ],
  "web_search_queries": [
    {{
      "query": "specific search for current market pricing",
      "category": "infrastructure|license|third_party|technology",
      "context": "what this cost is for in the project"
    }}
  ]
}}

STRICT RULES:
- Output an adjusted requirement for EVERY requirement provided — do NOT skip any.
- IN_SCOPE requirements MUST have at least one implementation_task with hours > 0.
- OUT_OF_SCOPE requirements MUST have empty implementation_tasks and a clear adjustment_reason.
- role_key MUST exactly match a key in DEVELOPER_RATES below.
- DEDUPLICATION: If a requirement in this chunk overlaps with a capability already listed in another unit (see GLOBAL SCOPE CONTEXT below), estimate ONLY the incremental scope introduced here. Set incremental_scope_note to describe what is new vs reused.
- Do NOT produce financial totals.

Available developer roles and their hourly rates (INR):
{developer_rates}
"""

ESTIMATION_REDUCE_PROMPT_TEMPLATE = """You are an expert project manager and cost analyst.
You are given an aggregated summary of the estimated project. Your job is to:
1. Compose the project team (roles, counts, billing status).
2. Determine the project timeline in weeks (based on total hours, team size, and parallelism).
3. Define major phases corresponding to the provided project units.
4. Write a per-phase estimation_note explaining the effort allocation.
5. Produce defensible estimation assumptions.
6. Write a contingency_rationale based on the risk context provided.

Respond with ONLY valid JSON — no markdown, no explanations:
{{
  "team_composition": [
    {{
      "role_key": "key from rate card",
      "count": number,
      "billing_status": "BILLABLE or NON_BILLABLE",
      "justification": "if NON_BILLABLE, explain why"
    }}
  ],
  "timeline_weeks": number,
  "phases": [
    {{
      "name": "MUST correspond to a unit label from the project_units_summary",
      "duration_weeks": number,
      "description": "string",
      "estimation_note": "explain why this phase takes this many weeks"
    }}
  ],
  "estimation_assumptions": [
    "each assumption that makes the timeline and team defensible"
  ],
  "contingency_rationale": "explain why the contingency % is justified given the risk factors"
}}

Available developer roles and their hourly rates (INR):
{developer_rates}
"""


async def _call_gemini(text: str, system_prompt: str, max_retries: int = 3) -> str:
    """Call Gemini LLM with key rotation and retry logic."""
    last_error = None
    for attempt in range(max_retries):
        api_key = await _gemini_keys.get_key()
        try:
            client = genai.Client(api_key=api_key)
            response = await client.aio.models.generate_content(
                model=config.GEMINI_LLM_MODEL,
                contents=system_prompt + "\n\n" + text,
            )
            return response.text
        except Exception as e:
            last_error = e
            await _gemini_keys.mark_failed(api_key)
            if attempt < max_retries - 1:
                await asyncio.sleep(config.RETRY_DELAY_SECONDS * (attempt + 1))
    raise Exception(f"All Gemini attempts failed. Last error: {last_error}")


def _parse_json(text: str) -> dict:
    text = text.strip()
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if match:
        text = match.group(1).strip()
    else:
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            text = text[start_idx:end_idx + 1]
    result = json_repair.repair_json(text, return_objects=True)
    if not isinstance(result, dict):
        snippet = text[:200] + ("..." if len(text) > 200 else "")
        raise ValueError(f"Parsed result is not a dict: type={type(result)}\nSnippet: {snippet}")
    return result


def _calculate_risk_aware_contingency(analysis: dict) -> tuple:
    """
    Deterministically calculate contingency % from project risk signals.
    Returns (percentage: float, rationale: str).

    Base: 10%
    Each risk factor adds 5% (capped at 25% total).
    """
    base = 10.0
    reasons = []

    all_reqs = []
    for unit in analysis.get("project_units", []):
        all_reqs.extend(unit.get("requirements", []))

    high_complexity = sum(1 for r in all_reqs if str(r.get("complexity", "")).lower() == "high")
    security_reqs = sum(1 for r in all_reqs if str(r.get("category", "")).lower() == "security")
    integration_reqs = sum(1 for r in all_reqs if str(r.get("category", "")).lower() == "integration")

    combined_text = (
        " ".join(analysis.get("risks", [])) + " " +
        " ".join(analysis.get("assumptions", []))
    ).lower()

    has_migration = any(kw in combined_text for kw in ["migration", "legacy", "remediation", "existing system"])
    has_multi_tenant = any(kw in combined_text for kw in ["multi-tenant", "multi tenant", "multitenant", "tenancy"])
    has_third_party = integration_reqs >= 3 or "third-party" in combined_text or "external api" in combined_text

    added = 0.0
    if high_complexity >= 4:
        added += 5.0
        reasons.append(f"{high_complexity} high-complexity requirements")
    if security_reqs >= 3:
        added += 5.0
        reasons.append(f"{security_reqs} security-sensitive requirements")
    if has_third_party:
        added += 5.0
        reasons.append("significant third-party/external integrations")
    if has_migration:
        added += 5.0
        reasons.append("legacy system remediation or data migration")
    if has_multi_tenant:
        added += 5.0
        reasons.append("multi-tenancy architecture complexity")

    pct = min(25.0, base + added)

    if reasons:
        rationale = (
            f"{pct:.0f}% contingency applied (base 10% + {added:.0f}% risk premium) "
            f"due to: {'; '.join(reasons)}."
        )
    else:
        rationale = (
            f"{pct:.0f}% base contingency applied. "
            "No significant risk multipliers detected."
        )

    return pct, rationale


async def estimation_node(state: PipelineState) -> dict:
    """
    Calculate cost estimation based on project analysis using Map-Reduce.

    Map:    Parallel LLM calls per unit chunk with cross-unit deduplication context.
    Reduce: Single LLM call to synthesise team, timeline, phases.
    Math:   All arithmetic is deterministic Python.
    """
    log = ["💰 Estimation: Calculating project costs (Map-Reduce)"]

    analysis = state.get("project_analysis")
    if not analysis:
        return {
            "errors": ["Estimation: No project analysis available."],
            "log": log + ["   ❌ No analysis data found"],
            "current_stage": "estimation_failed",
        }

    original_units = analysis.get("project_units", [])
    validation_feedback = state.get("validation_feedback", [])
    feedback_block = ""
    if validation_feedback:
        feedback_block = (
            "\n\nYOUR PREVIOUS ESTIMATION FAILED DETERMINISTIC VALIDATION. "
            "Fix EVERY issue below — do not repeat these mistakes:\n"
            + "\n".join(f"- {err}" for err in validation_feedback)
        )

    rates = config.DEVELOPER_RATES
    rates_json = json.dumps(rates, indent=2)

    # Build prompt templates with developer rates
    map_prompt = ESTIMATION_MAP_PROMPT_TEMPLATE.format(developer_rates=rates_json)
    reduce_prompt_template = ESTIMATION_REDUCE_PROMPT_TEMPLATE.format(developer_rates=rates_json)

    # ─── GLOBAL SCOPE INDEX ───────────────────────────────────────────────────
    # Flat list of ALL requirements across ALL units, injected into every chunk
    # so the LLM can detect cross-unit overlaps and estimate only incremental scope.
    global_scope_lines = []
    for unit in original_units:
        for req in unit.get("requirements", []):
            title = req.get("title", "")
            if title:
                global_scope_lines.append(
                    f"  [{req.get('id', '?')}] {title}  (unit: {unit.get('label', '?')})"
                )

    global_scope_block = (
        "\n\nGLOBAL SCOPE CONTEXT — all capabilities across this project:\n"
        + "\n".join(global_scope_lines)
        + "\n\nDEDUPLICATION INSTRUCTION: If the current chunk contains a requirement "
        "that represents a capability already covered in another unit, estimate ONLY "
        "the incremental scope this unit introduces. Do NOT re-estimate the shared baseline."
    )

    # ─── MAP STAGE ────────────────────────────────────────────────────────────
    log.append(
        f"   Map Stage: {len(original_units)} units → "
        f"{(len(original_units) + 1) // 2} parallel chunks (concurrency limit=5)"
    )
    semaphore = asyncio.Semaphore(5)

    async def process_chunk(units_chunk, chunk_idx):
        async with semaphore:
            prompt = (
                f"Estimate these project units:\n\n{json.dumps(units_chunk, indent=2)}"
                f"{global_scope_block}"
                f"{feedback_block}"
            )
            for attempt in range(3):
                try:
                    resp_text = await _call_gemini(prompt, map_prompt)
                    return _parse_json(resp_text)
                except Exception as e:
                    if attempt == 2:
                        log.append(f"   ⚠️ Chunk {chunk_idx + 1} failed after 3 retries: {e}")
                        return {"adjusted_project_units": [], "web_search_queries": []}
                    await asyncio.sleep(2 ** attempt)  # exponential backoff

    chunk_size = 2
    chunks = [original_units[i:i + chunk_size] for i in range(0, len(original_units), chunk_size)]
    map_results = await asyncio.gather(*[process_chunk(c, i) for i, c in enumerate(chunks)])

    # Merge map outputs
    adjusted_units = []
    web_search_queries = []
    for res in map_results:
        if res:
            adjusted_units.extend(res.get("adjusted_project_units", []))
            web_search_queries.extend(res.get("web_search_queries", []))

    # Deduplicate web queries by query string
    seen_queries: set = set()
    deduped_queries = []
    for q in web_search_queries:
        key = q.get("query", "").strip().lower()
        if key and key not in seen_queries:
            seen_queries.add(key)
            deduped_queries.append(q)
    web_search_queries = deduped_queries

    # ─── PYTHON MATH (Deterministic) ─────────────────────────────────────────
    adj_unit_map: dict = {}
    for idx, u in enumerate(adjusted_units):
        uid = u.get("unit_id") or u.get("id")
        adj_unit_map[uid if uid else str(idx)] = u

    unit_estimates = []
    total_development_hours = 0.0
    total_development_cost = 0.0
    missing_requirements = 0

    for idx, orig_unit in enumerate(original_units):
        unit_id = orig_unit.get("id", f"UNIT-{(idx + 1):03d}")
        adj_unit = adj_unit_map.get(unit_id, adj_unit_map.get(str(idx), {}))

        unit_hours = 0.0
        unit_cost = 0.0
        req_estimates = []

        adj_reqs = adj_unit.get("adjusted_requirements", adj_unit.get("requirements", []))
        adj_req_map = {r.get("id"): r for r in adj_reqs if r.get("id")}

        for r_idx, req in enumerate(orig_unit.get("requirements", [])):
            req_id = req.get("id", "")
            adj_req = adj_req_map.get(req_id, {})
            if not adj_req and r_idx < len(adj_reqs):
                adj_req = adj_reqs[r_idx]  # positional fallback
            if not adj_req:
                missing_requirements += 1

            scope_status = adj_req.get("scope_status", req.get("scope_status", "IN_SCOPE")).upper()
            adjustment_reason = adj_req.get("adjustment_reason", "no change")
            incremental_note = adj_req.get("incremental_scope_note")
            category = adj_req.get("category", req.get("category", "General"))

            tasks_raw = adj_req.get("implementation_tasks", [])
            task_estimates = []
            req_hours = 0.0
            req_cost = 0.0

            if scope_status == "IN_SCOPE":
                if tasks_raw:
                    for t in tasks_raw:
                        t_role = t.get("role_key", "mid_developer")
                        t_hours = float(t.get("hours", 0))
                        if t_role not in rates:
                            t_role = "mid_developer"
                        t_rate = rates[t_role]["rate_per_hour"]
                        if t_hours <= 0:
                            t_hours = 4.0  # safe minimum
                        t_cost = t_hours * t_rate
                        req_hours += t_hours
                        req_cost += t_cost
                        task_estimates.append({
                            "task": t.get("task", "Unnamed task"),
                            "role_key": t_role,
                            "role_label": rates[t_role]["label"],
                            "hours": t_hours,
                            "cost": t_cost,
                        })
                else:
                    # LLM skipped tasks — use complexity-based fallback hours
                    role_key = adj_req.get("required_role", req.get("required_role", "mid_developer"))
                    if role_key not in rates:
                        role_key = "mid_developer"
                    complexity = req.get("complexity", "Medium").lower()
                    default_hours = {"low": 8.0, "medium": 24.0, "high": 48.0}.get(complexity, 24.0)
                    req_hours = float(adj_req.get("estimated_hours", req.get("estimated_hours", default_hours)))
                    if req_hours <= 0:
                        req_hours = default_hours
                    req_cost = req_hours * rates[role_key]["rate_per_hour"]
                    task_estimates.append({
                        "task": req.get("title", "Implementation"),
                        "role_key": role_key,
                        "role_label": rates[role_key]["label"],
                        "hours": req_hours,
                        "cost": req_cost,
                    })

            unit_hours += req_hours
            unit_cost += req_cost

            req_estimates.append({
                "requirement_id": req_id,
                "title": req.get("title", "Untitled Requirement"),
                "scope_status": scope_status,
                "hours": req_hours,
                "cost": req_cost,
                "adjustment_reason": adjustment_reason,
                "incremental_scope_note": incremental_note,
                "category": category,
                "complexity": req.get("complexity", "Medium"),
                "implementation_tasks": task_estimates,
            })

        total_development_hours += unit_hours
        total_development_cost += unit_cost

        unit_estimates.append({
            "unit_id": unit_id,
            "label": orig_unit.get("label", "Unknown Unit"),
            "semantic_type": orig_unit.get("semantic_type", "other"),
            "billing": orig_unit.get("billing", {}),
            "relevance": orig_unit.get("relevance", {}),
            "requirement_estimates": req_estimates,
            "estimate": {"hours": unit_hours, "cost": unit_cost}
        })

    if missing_requirements > 0:
        log.append(f"   ⚠️ Map Stage missed {missing_requirements} requirements; complexity-based fallback applied.")

    # ─── RISK-AWARE CONTINGENCY (Deterministic) ───────────────────────────────
    contingency_percentage, contingency_rationale = _calculate_risk_aware_contingency(analysis)
    contingency_amount = total_development_cost * (contingency_percentage / 100)
    grand_total = total_development_cost + contingency_amount

    # ─── REDUCE STAGE ─────────────────────────────────────────────────────────
    log.append("   Reduce Stage: synthesising team composition, timeline, and phases...")

    reduce_role_totals: dict = defaultdict(float)
    for u in unit_estimates:
        for r in u["requirement_estimates"]:
            for t in r.get("implementation_tasks", []):
                reduce_role_totals[t.get("role_key", "mid_developer")] += t.get("hours", 0)

    reduce_payload = {
        "project_name": analysis.get("project_name", "Unknown"),
        "project_type": analysis.get("project_type", "Unknown"),
        "total_development_hours": total_development_hours,
        "contingency_percentage": contingency_percentage,
        "contingency_rationale_context": contingency_rationale,
        "role_hours_summary": dict(reduce_role_totals),
        "project_units_summary": [
            {
                "unit_id": u["unit_id"],
                "label": u["label"],
                "hours": u["estimate"]["hours"],
                "requirement_count": len(u["requirement_estimates"])
            }
            for u in unit_estimates
        ]
    }

    reduce_user_prompt = (
        f"Determine the team composition, timeline, and phases for this project:\n\n"
        f"{json.dumps(reduce_payload, indent=2)}\n{feedback_block}"
    )

    try:
        reduce_resp = await _call_gemini(reduce_user_prompt, reduce_prompt_template)
        reduce_data = _parse_json(reduce_resp)
        log.append("   ✅ Reduce stage complete")
    except Exception as e:
        log.append(f"   ⚠️ Reduce stage failed ({e}) — using deterministic fallback")
        reduce_data = {
            "team_composition": [
                {"role_key": "mid_developer", "count": 2, "billing_status": "BILLABLE", "justification": ""}
            ],
            "timeline_weeks": max(4, int(total_development_hours / 40)),
            "phases": [
                {
                    "name": u["label"],
                    "duration_weeks": max(1, int(u["estimate"]["hours"] / 40)),
                    "description": "",
                    "estimation_note": ""
                }
                for u in unit_estimates
            ],
            "estimation_assumptions": ["Standard defaults applied due to reduce stage failure."],
            "contingency_rationale": contingency_rationale
        }

    team_composition = reduce_data.get("team_composition", [])
    timeline_weeks = reduce_data.get("timeline_weeks", 12)
    phases = reduce_data.get("phases", [])
    estimation_assumptions = reduce_data.get("estimation_assumptions", [])
    final_contingency_rationale = reduce_data.get("contingency_rationale") or contingency_rationale

    # Prepend contingency rationale to assumptions for document visibility
    if final_contingency_rationale:
        prefix = f"Contingency ({contingency_percentage:.0f}%): {final_contingency_rationale}"
        if prefix not in estimation_assumptions:
            estimation_assumptions = [prefix] + estimation_assumptions

    # ─── AGGREGATION (Deterministic) ─────────────────────────────────────────
    category_totals: dict = defaultdict(float)
    category_hours_agg: dict = defaultdict(float)
    role_totals: dict = defaultdict(float)
    role_hours_agg: dict = defaultdict(float)

    for u in unit_estimates:
        for r in u["requirement_estimates"]:
            cat = r.get("category", "General")
            category_totals[cat] += r["cost"]
            category_hours_agg[cat] += r["hours"]
            for t in r.get("implementation_tasks", []):
                role = t.get("role_key", "mid_developer")
                role_totals[role] += t.get("cost", 0)
                role_hours_agg[role] += t.get("hours", 0)

    category_breakdown = [
        {"category": k, "total_cost": v, "total_hours": category_hours_agg[k]}
        for k, v in category_totals.items()
    ]

    role_estimates = [
        {
            "role_key": k,
            "role_label": rates.get(k, {}).get("label", k),
            "hours": role_hours_agg[k],
            "rate_per_hour": rates.get(k, {}).get("rate_per_hour", 0),
            "total_cost": v
        }
        for k, v in role_totals.items()
    ]

    log.append("   ✅ Estimation complete:")
    log.append(f"      Total hours: {total_development_hours:.1f}")
    log.append(f"      Total dev cost: \u20b9{total_development_cost:,.2f}")
    log.append(f"      Contingency: {contingency_percentage:.0f}% (\u20b9{contingency_amount:,.2f})")
    log.append(f"      Grand total: \u20b9{grand_total:,.2f}")
    log.append(f"      Web search queries: {len(web_search_queries)}")

    state["cost_estimation"] = {
        "unit_estimates": unit_estimates,
        "team_composition": team_composition,
        "role_estimates": role_estimates,
        "timeline_weeks": timeline_weeks,
        "phases": phases,
        "category_breakdown": category_breakdown,
        "total_development_hours": total_development_hours,
        "total_development_cost": total_development_cost,
        "contingency_percentage": contingency_percentage,
        "contingency_rationale": final_contingency_rationale,
        "contingency_amount": contingency_amount,
        "infrastructure_cost_monthly": 0,
        "third_party_licenses_monthly": 0,
        "grand_total": grand_total,
        "estimation_assumptions": estimation_assumptions,
        "web_search_queries": web_search_queries,
    }

    state["log"] = log
    state["current_stage"] = "estimation_complete"
    return state
