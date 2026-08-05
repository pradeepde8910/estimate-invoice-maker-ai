"""
Web Search Agent — Uses Gemini API with Google Search grounding
to verify technology costs, infrastructure pricing, and market rates.
"""

from __future__ import annotations

import asyncio
import json

from google import genai
from google.genai import types

import config
from agents.state import PipelineState
from utils.key_manager import KeyManager

_gemini_keys = KeyManager(config.GEMINI_API_KEYS)

SEARCH_SYSTEM_PROMPT = """You are a cost research analyst. For each query, search the web and provide:
1. The current market rate/pricing in Indian Rupees (INR)
2. A brief explanation
3. An estimated monthly or one-time cost (as a number in INR)

Respond with ONLY valid JSON (no markdown, no explanations):
{
  "results": [
    {
      "query": "the original search query",
      "answer": "detailed answer with current pricing found",
      "estimated_cost": number or null,
      "cost_type": "monthly|one_time|per_unit|annual",
      "sources": ["list of source URLs or descriptions"]
    }
  ],
  "total_infrastructure_monthly": number,
  "total_licenses_monthly": number,
  "summary": "brief summary of all findings"
}
"""


async def _search_gemini(queries: list[dict], max_retries: int = 3) -> dict:
    """Call Gemini with Google Search grounding."""
    last_error = None

    for attempt in range(max_retries):
        api_key = await _gemini_keys.get_key()
        try:
            client = genai.Client(api_key=api_key)

            # Format queries into a single prompt
            query_text = "Research the following technology costs and provide current market rates:\n\n"
            for i, q in enumerate(queries, 1):
                query_text += f"{i}. {q.get('query', '')} (Context: {q.get('context', '')})\n"

            google_search_tool = types.Tool(
                google_search=types.GoogleSearch()
            )

            try:
                response = await client.aio.models.generate_content(
                    model=config.GEMINI_MODEL,
                    contents=SEARCH_SYSTEM_PROMPT + "\n\nQUERIES:\n" + query_text,
                    config=types.GenerateContentConfig(
                        tools=[google_search_tool],
                        temperature=0.2,
                    ),
                )
            except Exception as search_err:
                # Fallback: Call Gemini without the google_search tool if search grounding quota is exceeded
                response = await client.aio.models.generate_content(
                    model=config.GEMINI_MODEL,
                    contents=SEARCH_SYSTEM_PROMPT + "\n\nQUERIES:\n" + query_text,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                    ),
                )

            return _parse_json(response.text)

        except Exception as e:
            last_error = e
            await _gemini_keys.mark_failed(api_key)
            if attempt < max_retries - 1:
                await asyncio.sleep(config.RETRY_DELAY_SECONDS * (attempt + 1))

    raise Exception(f"All Gemini attempts failed. Last error: {last_error}")


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON from mixed text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        return {"results": [], "total_infrastructure_monthly": 0, "total_licenses_monthly": 0, "summary": "Failed to parse response"}


async def web_search_node(state: PipelineState) -> dict:
    """
    Use Gemini with Google Search to find current market rates
    for infrastructure, licenses, and third-party services.
    Runs batched queries concurrently.
    """
    log = ["🌐 Web Search: Researching market rates with Gemini"]

    cost_estimation = state.get("cost_estimation", {})
    queries = cost_estimation.get("web_search_queries", [])

    if not queries:
        log.append("   ⏭️  No web search queries generated, skipping")
        return {
            "web_search_results": {
                "items": [],
                "infrastructure_estimates": [],
                "technology_cost_estimates": [],
            },
            "log": log,
            "current_stage": "search_complete",
        }

    log.append(f"   Searching for {len(queries)} cost items concurrently")

    try:
        batch_size = 5
        batches = [queries[i:i + batch_size] for i in range(0, len(queries), batch_size)]
        
        async def process_batch(idx, batch):
            log.append(f"   Batch {idx + 1}: processing {len(batch)} queries")
            return await _search_gemini(batch)

        # Run all batches sequentially with a small delay to avoid rate limits
        results = []
        for i, batch in enumerate(batches):
            if i > 0:
                await asyncio.sleep(2.0)
            res = await process_batch(i, batch)
            results.append(res)

        all_results = []
        total_infra = 0
        total_licenses = 0

        for result in results:
            batch_results = result.get("results", [])
            all_results.extend(batch_results)
            total_infra += result.get("total_infrastructure_monthly", 0)
            total_licenses += result.get("total_licenses_monthly", 0)

        # Categorize results
        infra_results = [r for r in all_results if "infrastructure" in r.get("query", "").lower() or "hosting" in r.get("query", "").lower() or "cloud" in r.get("query", "").lower()]
        tech_results = [r for r in all_results if r not in infra_results]

        web_search_results = {
            "items": all_results,
            "infrastructure_estimates": infra_results,
            "technology_cost_estimates": tech_results,
        }

        # Update cost estimation with web search findings
        updated_estimation = dict(cost_estimation)
        updated_estimation["infrastructure_cost_monthly"] = total_infra
        updated_estimation["third_party_licenses_monthly"] = total_licenses

        # Recalculate grand total
        dev_cost = updated_estimation.get("total_development_cost", 0)
        contingency = updated_estimation.get("contingency_amount", 0)
        # Add 6 months of infra + licenses to project cost
        infra_project = total_infra * 6
        license_project = total_licenses * 6
        updated_estimation["grand_total"] = dev_cost + contingency + infra_project + license_project

        log.append(f"   ✅ Web search complete:")
        log.append(f"      Results found: {len(all_results)}")
        log.append(f"      Monthly infra cost: ₹{total_infra:,.2f}")
        log.append(f"      Monthly license cost: ₹{total_licenses:,.2f}")

        return {
            "web_search_results": web_search_results,
            "cost_estimation": updated_estimation,
            "log": log,
            "current_stage": "search_complete",
        }

    except Exception as e:
        log.append(f"   ⚠️  Web search failed (non-critical): {str(e)}")
        return {
            "web_search_results": {
                "items": [],
                "infrastructure_estimates": [],
                "technology_cost_estimates": [],
            },
            "errors": [f"Web search warning: {str(e)}"],
            "log": log,
            "current_stage": "search_complete",
        }
