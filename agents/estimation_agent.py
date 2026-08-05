"""
Estimation Agent — Uses Groq LLM + predefined rate card to calculate
development costs from the structured requirements.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict

from groq import AsyncGroq

import config
from agents.state import PipelineState
from utils.key_manager import KeyManager

_groq_keys = KeyManager(config.GROQ_API_KEYS)

ESTIMATION_SYSTEM_PROMPT = """You are an expert project estimator and cost analyst.
You are given a structured project analysis with requirements. Your job is to:

1. Review each requirement's estimated hours and adjust if needed based on your expertise
2. Assign appropriate team roles to each requirement  
3. Identify what technologies, infrastructure, and third-party services are needed
4. Create a list of queries for web search to find current market rates for:
   - Cloud infrastructure costs (hosting, databases, storage, CDN, etc.)
   - Third-party API/service costs (payment gateways, email services, etc.)
   - Software license costs
   - Any other technology-specific costs

You MUST respond with ONLY valid JSON:
{
  "adjusted_requirements": [
    {
      "id": "REQ-001",
      "title": "string",
      "category": "string",
      "estimated_hours": number,
      "required_role": "string (key from rate card)",
      "adjustment_reason": "string — why hours were changed, or 'no change'"
    }
  ],
  "web_search_queries": [
    {
      "query": "string — specific search query for finding current pricing",
      "category": "infrastructure|license|third_party|technology",
      "context": "string — what this cost is for in the project"
    }
  ],
  "team_composition": [
    {
      "role_key": "string — key from rate card",
      "count": number,
      "justification": "string"
    }
  ],
  "timeline_weeks": number,
  "phases": [
    {
      "name": "string",
      "duration_weeks": number,
      "description": "string"
    }
  ]
}

Available developer roles and their hourly rates (INR):
""" + json.dumps(config.DEVELOPER_RATES, indent=2)


async def _call_groq(text: str, system_prompt: str, max_retries: int = 3) -> str:
    """Call Groq LLM with key rotation and retry."""
    last_error = None
    for attempt in range(max_retries):
        api_key = await _groq_keys.get_key()
        try:
            client = AsyncGroq(api_key=api_key)
            if len(text) > config.MAX_CHUNK_CHARS:
                text = text[:config.MAX_CHUNK_CHARS] + "\n\n[... TRUNCATED ...]"

            response = await client.chat.completions.create(
                model=config.GROQ_LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.1,
                max_tokens=8000,
            )
            return response.choices[0].message.content
        except Exception as e:
            last_error = e
            await _groq_keys.mark_failed(api_key)
            if attempt < max_retries - 1:
                await asyncio.sleep(config.RETRY_DELAY_SECONDS * (attempt + 1))
    raise Exception(f"All Groq attempts failed. Last error: {last_error}")


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return json.loads(text)


async def estimation_node(state: PipelineState) -> dict:
    """
    Calculate cost estimation based on project analysis.
    Uses the predefined rate card for developer costs.
    Generates web search queries for infrastructure/license costs.
    """
    log = ["💰 Estimation: Calculating project costs"]

    analysis = state.get("project_analysis")
    if not analysis:
        return {
            "errors": ["Estimation: No project analysis available."],
            "log": log + ["   ❌ No analysis data found"],
            "current_stage": "estimation_failed",
        }

    try:
        prompt = f"""Review this project analysis and create a detailed cost estimation.

PROJECT ANALYSIS:
{json.dumps(analysis, indent=2)}

Instructions:
1. Adjust hour estimates if they seem unrealistic
2. Assign roles from the provided rate card
3. Generate web search queries for infrastructure and third-party costs
4. Suggest a realistic team composition and timeline
"""

        try:
            response_text = await _call_groq(prompt, ESTIMATION_SYSTEM_PROMPT)
            estimation_data = _parse_json(response_text)
        except Exception as e:
            log.append(f"   ⚠️  LLM estimation failed ({str(e)}), falling back to raw analysis data...")
            estimation_data = {
                "adjusted_requirements": analysis.get("requirements", []),
                "web_search_queries": [{"query": "cloud hosting costs", "category": "infrastructure", "context": "general hosting"}],
                "team_composition": [],
                "timeline_weeks": 12,
                "phases": []
            }

        # Calculate costs using the rate card
        rates = config.DEVELOPER_RATES
        role_hours = defaultdict(float)
        category_items = defaultdict(list)

        adjusted_reqs = estimation_data.get("adjusted_requirements", [])
        
        # Fallback: if the LLM failed to return adjusted requirements, use the original ones
        original_reqs = analysis.get("requirements", [])
        if not adjusted_reqs:
            adjusted_reqs = original_reqs
            for req in adjusted_reqs:
                if "required_role" not in req:
                    req["required_role"] = "mid_developer"

        for req in adjusted_reqs:
            role = req.get("required_role", "mid_developer")
            hours = req.get("estimated_hours", 0)
            category = req.get("category", "General")

            role_hours[role] += hours
            category_items[category].append({
                "id": req.get("id", ""),
                "title": req.get("title", ""),
                "hours": hours,
                "role": role,
            })

        # Build role estimates
        role_estimates = []
        total_hours = 0
        total_cost = 0

        for role_key, hours in role_hours.items():
            rate_info = rates.get(role_key, rates["mid_developer"])
            rate = rate_info["rate_per_hour"]
            cost = hours * rate
            total_hours += hours
            total_cost += cost
            role_estimates.append({
                "role_key": role_key,
                "role_label": rate_info["label"],
                "hours": hours,
                "rate_per_hour": rate,
                "total_cost": cost,
            })

        # Build category breakdown
        category_breakdown = []
        for cat, items in category_items.items():
            cat_hours = sum(i["hours"] for i in items)
            cat_cost = sum(
                i["hours"] * rates.get(i["role"], rates["mid_developer"])["rate_per_hour"]
                for i in items
            )
            category_breakdown.append({
                "category": cat,
                "requirements_count": len(items),
                "total_hours": cat_hours,
                "total_cost": cat_cost,
                "items": items,
            })

        # Contingency
        contingency_pct = 15.0
        contingency_amt = total_cost * (contingency_pct / 100)

        cost_estimation = {
            "role_estimates": role_estimates,
            "category_breakdown": category_breakdown,
            "total_development_hours": total_hours,
            "total_development_cost": total_cost,
            "infrastructure_cost_monthly": 0,  # filled by web search
            "third_party_licenses_monthly": 0,  # filled by web search
            "miscellaneous_costs": 0,
            "contingency_percentage": contingency_pct,
            "contingency_amount": contingency_amt,
            "grand_total": total_cost + contingency_amt,
            "web_search_queries": estimation_data.get("web_search_queries", []),
            "team_composition": estimation_data.get("team_composition", []),
            "timeline_weeks": estimation_data.get("timeline_weeks", 0),
            "phases": estimation_data.get("phases", []),
            "adjusted_requirements": adjusted_reqs,
        }

        log.append(f"   ✅ Estimation complete:")
        log.append(f"      Total hours: {total_hours:.0f}")
        log.append(f"      Total dev cost: ₹{total_cost:,.2f}")
        log.append(f"      Grand total (with contingency): ₹{total_cost + contingency_amt:,.2f}")
        log.append(f"      Web search queries: {len(estimation_data.get('web_search_queries', []))}")

        return {
            "cost_estimation": cost_estimation,
            "log": log,
            "current_stage": "estimation_complete",
        }

    except json.JSONDecodeError as e:
        return {
            "errors": [f"Estimation JSON parse error: {str(e)}"],
            "log": log + [f"   ❌ JSON parse error: {str(e)}"],
            "current_stage": "estimation_failed",
        }
    except Exception as e:
        return {
            "errors": [f"Estimation error: {str(e)}"],
            "log": log + [f"   ❌ Estimation failed: {str(e)}"],
            "current_stage": "estimation_failed",
        }
