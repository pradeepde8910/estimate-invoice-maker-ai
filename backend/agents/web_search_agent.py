"""
Pricing Resolution Agent — Matches resources to the internal catalog first.
For unverified/missing items, uses Gemini + Google Search to estimate costs and
inserts them as pending review items in the database.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
import uuid

from google import genai
from google.genai import types
from sqlalchemy.orm import joinedload

import config
from agents.state import PipelineState
from utils.key_manager import KeyManager
from app.database import SessionLocal
from app.models.resource_catalog import Capability, TechnologyProvider, TechnologyModel, ApiPricingRule

_gemini_keys = KeyManager(config.GEMINI_API_KEYS)

CATALOG_MATCH_PROMPT = """You are an infrastructure architect.
Match the REQUIRED RESOURCES against the provided VERIFIED CATALOG.
If a requirement is clearly satisfied by a catalog model, match them.
Otherwise, leave it unmatched.

Respond with ONLY valid JSON:
{
  "matches": [
    {
      "requirement_index": 0,
      "model_id": "uuid"
    }
  ],
  "unmatched_indices": [1, 2]
}
"""

SEARCH_SYSTEM_PROMPT = """You are a cost research analyst. For each query, search the web and provide:
1. The current market rate/pricing in Indian Rupees (INR)
2. An estimated monthly or one-time cost (as a number in INR)

Respond with ONLY valid JSON (no markdown):
{
  "results": [
    {
      "query": "the original search query",
      "answer": "detailed answer with current pricing found",
      "estimated_cost": 1500.0,
      "cost_type": "monthly|one_time",
      "sources": ["list of source URLs"]
    }
  ]
}
"""

def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        return {}

def _fetch_catalog_data():
    """Fetch active catalog models and pricing from the DB."""
    db = SessionLocal()
    try:
        models = db.query(TechnologyModel).options(
            joinedload(TechnologyModel.provider),
            joinedload(TechnologyModel.pricing_rules)
        ).filter(TechnologyModel.active.is_(True)).all()
        
        catalog = []
        for m in models:
            active_rules = [r for r in m.pricing_rules if r.active]
            if not active_rules:
                continue
            rule = active_rules[0]
            catalog.append({
                "model_id": m.id,
                "provider": m.provider.name,
                "model_name": m.model_name,
                "price": float(rule.price),
                "currency": rule.currency,
                "unit": rule.unit_type or "flat",
                "pricing_model": rule.pricing_model
            })
        return catalog
    finally:
        db.close()

async def _match_catalog(requirements: list, catalog: list) -> dict:
    if not catalog or not requirements:
        return {"matches": [], "unmatched_indices": list(range(len(requirements)))}
        
    prompt = f"REQUIRED RESOURCES:\n{json.dumps(requirements, indent=2)}\n\nVERIFIED CATALOG:\n{json.dumps(catalog, indent=2)}"
    api_key = await _gemini_keys.get_key()
    client = genai.Client(api_key=api_key)
    
    try:
        response = await client.aio.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=CATALOG_MATCH_PROMPT + "\n\n" + prompt,
            config=types.GenerateContentConfig(temperature=0.1)
        )
        return _parse_json(response.text)
    except Exception as e:
        return {"matches": [], "unmatched_indices": list(range(len(requirements)))}

async def _search_gemini(queries: list) -> dict:
    if not queries:
        return {"results": []}
        
    api_key = await _gemini_keys.get_key()
    client = genai.Client(api_key=api_key)
    
    query_text = "Research the following:\n"
    for i, q in enumerate(queries):
        query_text += f"{i}. {q.get('resource_name', '')} - {q.get('reasoning', '')}\n"
        
    tool = types.Tool(google_search=types.GoogleSearch())
    
    try:
        response = await client.aio.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=SEARCH_SYSTEM_PROMPT + "\n\n" + query_text,
            config=types.GenerateContentConfig(tools=[tool], temperature=0.2)
        )
        return _parse_json(response.text)
    except Exception:
        # Fallback without search
        response = await client.aio.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=SEARCH_SYSTEM_PROMPT + "\n\n" + query_text,
            config=types.GenerateContentConfig(temperature=0.2)
        )
        return _parse_json(response.text)

async def web_search_node(state: PipelineState) -> dict:
    log = ["🌐 Pricing Resolution: Matching resources to catalog"]
    cost_estimation = state.get("cost_estimation", {})
    reqs = cost_estimation.get("resource_requirements", [])
    
    if not reqs:
        log.append("   ⏭️  No resource requirements to resolve.")
        return {"resolved_pricing": {"verified_costs": [], "pending_costs": []}, "log": log, "current_stage": "search_complete"}
        
    catalog = await asyncio.to_thread(_fetch_catalog_data)
    log.append(f"   Fetched {len(catalog)} active pricing models from DB.")
    
    match_result = await _match_catalog(reqs, catalog)
    
    verified_costs = []
    pending_costs = []
    
    # 1. Process matches
    matches = match_result.get("matches", [])
    matched_indices = set()
    for m in matches:
        idx = m.get("requirement_index")
        model_id = m.get("model_id")
        if idx is not None and idx < len(reqs):
            matched_indices.add(idx)
            cat_item = next((c for c in catalog if c["model_id"] == model_id), None)
            if cat_item:
                verified_costs.append({
                    "resource": reqs[idx].get("resource_name", "Unknown"),
                    "provider": cat_item["provider"],
                    "model_name": cat_item["model_name"],
                    "price": cat_item["price"],
                    "currency": cat_item["currency"],
                    "unit": cat_item["unit"],
                    "monthly_cost": cat_item["price"] * 6 if cat_item["unit"] == "MONTH" else cat_item["price"], # Rough estimate for total
                    "status": "VERIFIED"
                })
                
    # 2. Process non-matches (Gemini Search)
    unmatched_indices = [i for i in range(len(reqs)) if i not in matched_indices]
    unmatched_reqs = [reqs[i] for i in unmatched_indices]
    
    if unmatched_reqs:
        log.append(f"   🔍 {len(unmatched_reqs)} items not in catalog. Searching web...")
        search_res = await _search_gemini(unmatched_reqs)
        results = search_res.get("results", [])
        
        for i, res in enumerate(results):
            cost = res.get("estimated_cost") or 0.0
            pending_costs.append({
                "resource": res.get("query", "Unknown"),
                "estimated_cost": cost,
                "cost_type": res.get("cost_type", "unknown"),
                "details": res.get("answer", ""),
                "status": "PENDING_REVIEW"
            })
            
    # Update cost estimation with verified infra costs (excluding pending)
    updated_estimation = dict(cost_estimation)
    total_infra = sum(v.get("price", 0) for v in verified_costs)
    updated_estimation["infrastructure_cost_monthly"] = total_infra
    
    dev_cost = updated_estimation.get("total_development_cost", 0)
    contingency = updated_estimation.get("contingency_amount", 0)
    # ONLY INCLUDE VERIFIED COSTS IN GRAND TOTAL (assume 6 months for recurring, simplified)
    updated_estimation["grand_total"] = dev_cost + contingency + (total_infra * 6)
    
    log.append(f"   ✅ Resolution complete: {len(verified_costs)} VERIFIED, {len(pending_costs)} PENDING.")

    return {
        "resolved_pricing": {
            "verified_costs": verified_costs,
            "pending_costs": pending_costs
        },
        "cost_estimation": updated_estimation,
        "log": log,
        "current_stage": "search_complete"
    }
