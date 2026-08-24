"""
Analysis Agent — Uses Groq LLM to analyze the requirement document
and extract structured project data.
"""

from __future__ import annotations

import asyncio
import json

from google import genai

import config
from agents.state import PipelineState
from utils.key_manager import KeyManager

# Initialize key manager
_gemini_keys = KeyManager(config.GEMINI_API_KEYS)

ANALYSIS_SYSTEM_PROMPT = """You are an expert business analyst and software architect. 
Your task is to analyze a requirement document and extract structured project information.

You MUST respond with ONLY valid JSON (no markdown fences, no explanations before/after).

The JSON must have this exact structure:
{
  "client": {
    "company_name": "string or null — The name of the client organization/company. Look for a company name, letterhead, 'prepared for', client signature, or organization mentioned as the requester. DO NOT use a person's name here. If no organization name is explicitly mentioned, return null.",
    "contact_person": "string or null — The name of the specific person requesting the project, if mentioned. If none is mentioned, return null.",
    "email": "string or null — Contact email, if found in the document.",
    "phone": "string or null — Contact phone number, if found in the document.",
    "billing_address": "string or null — Billing or company address, if found.",
    "gstin": "string or null — GSTIN or tax ID, if found.",
    "confidence": "float — between 0 and 1 indicating how confident you are in the client identification"
  },
  "project_name": "string — name of the project",
  "project_description": "string — 2-3 sentence summary",
  "project_type": "string — e.g., Web App, Mobile App, API, SaaS Platform, etc.",
  "target_audience": "string — who will use this",
  "tech_stack_suggested": ["list of recommended technologies"],
  "project_structure": {
    "detected": "boolean — true if the document has explicit sections like Phases, Milestones, Covers, Stages, etc.",
    "structure_type": "string — e.g., 'cover_based', 'milestone_based', 'phase_based', 'flat'",
    "source_term": "string — the actual term used in the document, e.g., 'Cover', 'Milestone', 'Phase', or null if flat",
    "confidence": "float — between 0 and 1"
  },
  "project_units": [
    {
      "id": "U001",
      "parent_id": "string or null — if this unit belongs to another unit, provide its ID",
      "label": "string — e.g., 'Cover A - Civil Works' or 'Phase 1'",
      "source_term": "string — e.g., 'cover', 'phase', 'milestone', 'stage', or null if inferred",
      "semantic_type": "string — MUST BE ONE OF: phase, milestone, stage, work_package, deliverable_group, lot, module, section, other",
      "sequence": "integer — the order in which this unit appears or is executed",
      "classification": {
        "method": "string — MUST BE 'explicit' (clearly stated in document) or 'inferred' (guessed by you)",
        "confidence": "float — between 0 and 1"
      },
      "relevance": {
        "estimation": "boolean — true if this unit has estimable work/costs",
        "reporting": "boolean — true if this unit is useful for progress reporting"
      },
      "confidence": "float — 0.0 to 1.0 based on how clearly this unit is defined and whether its full context is visible",
      "billing": {
        "is_billing_unit": "boolean — MUST be true ONLY for top-level units that represent distinct billing milestones (e.g., Phases, Lots, Covers). Must be false for child modules to prevent double-counting of costs."
      },
      "source": {
        "evidence": "string — quote or exact heading from the document proving this unit exists"
      },
      "requirements": [
        {
          "id": "REQ-001",
          "title": "short title",
          "description": "detailed description of the requirement",
          "scope_status": "MUST BE 'IN_SCOPE' or 'OUT_OF_SCOPE'. Use OUT_OF_SCOPE for items explicitly excluded or clearly beyond the project boundary.",
          "category": "one of: Frontend, Backend, Database, DevOps, Integration, Security, UI/UX, Testing, Documentation, Infrastructure",
          "priority": "High/Medium/Low",
          "complexity": "High/Medium/Low",
          "technologies": ["specific technologies needed for this requirement"],
          "dependencies": ["IDs of other requirements this depends on"],
          "confidence": "float — 0.0 to 1.0 based on how complete/clear the requirement is. If the requirement seems truncated or missing context, assign a low score (e.g. 0.3)."
        }
      ]
    }
  ],
  "assumptions": ["list of assumptions you are making"],
  "risks": ["list of identified project risks"],
  "out_of_scope": ["items explicitly or implicitly out of scope"]
}

Guidelines:
- Normalize arbitrary document structures into a generic `ProjectUnit` while preserving original terminology.
- If the document is flat (no Covers/Milestones/Phases), create a single root ProjectUnit with semantic_type="other" and place all requirements inside it.
- Use `parent_id` to establish hierarchical trees (e.g., Phase -> Cover -> Requirement).
- Make sure `semantic_type` strictly uses the provided vocabulary.
- Break down requirements into granular, estimable tasks (10-50 items typically).
- Be thorough — don't miss requirements that are implied but not explicitly stated.
- scope_status rules: Set IN_SCOPE for all implementable requirements. Set OUT_OF_SCOPE ONLY for items the document explicitly excludes or that are clearly beyond the project boundary.
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

    raise Exception(f"All Gemini API attempts failed. Last error: {last_error}")


import re
import json_repair

def _parse_json_response(response_text: str) -> dict:
    """Extract and parse JSON from LLM response, handling markdown fences, preambles, and malformed structures."""
    text = response_text.strip()

    # Try to find JSON block using regex if there's preamble text
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if match:
        text = match.group(1).strip()
    else:
        # Fallback to finding the first { and last }
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            text = text[start_idx:end_idx + 1]

    # Use json_repair to parse and automatically fix missing commas, unclosed brackets, etc.
    result = json_repair.repair_json(text, return_objects=True)
    
    if not isinstance(result, dict):
        snippet = text[:200] + ("..." if len(text) > 200 else "")
        raise ValueError(f"Parsed result is not a dictionary: type={type(result)}\nRaw text snippet: {snippet}")
        
    return result


async def analysis_node(state: PipelineState) -> dict:
    """
    Analyze the document text and extract structured requirements.
    Uses async Map-Reduce to process large documents in parallel chunks.
    """
    log = ["📊 Analysis: Starting requirement analysis with Groq LLM"]

    document_text = state.get("document_text", "")
    if not document_text:
        return {
            "errors": ["Analysis: No document text available."],
            "log": log + ["   ❌ No document text found"],
            "current_stage": "analysis_failed",
        }

    log.append(f"   Document length: {len(document_text)} chars")
    log.append(f"   Model: {config.GEMINI_LLM_MODEL}")

    try:
        # Retrieve OCR pages for sliding window chunking
        ocr_result = state.get("ocr_result", {})
        pages = ocr_result.get("pages", [])
        
        chunks = []
        if pages and len(pages) > 1:
            log.append(f"   Using page-based sliding window chunking ({len(pages)} pages)...")
            window_size = 3
            step = 2
            for i in range(0, len(pages), step):
                window_pages = pages[i:i + window_size]
                chunk_text = "\n\n---PAGE BREAK---\n\n".join(p.get("text", "") for p in window_pages)
                chunks.append(chunk_text)
                if i + window_size >= len(pages):
                    break
        else:
            log.append("   Using character-based sliding window chunking...")
            chunk_size = config.MAX_CHUNK_CHARS
            overlap = 1000
            for i in range(0, max(1, len(document_text)), chunk_size - overlap):
                chunks.append(document_text[i:i + chunk_size])
        
        merged_analysis = {
            "client_name": "Unspecified Client",
            "project_name": "Unknown",
            "project_description": "",
            "project_type": "Unknown",
            "target_audience": "",
            "tech_stack_suggested": [],
            "project_units": [],
            "assumptions": [],
            "risks": [],
            "out_of_scope": []
        }
        
        log.append(f"   Splitting into {len(chunks)} chunks and processing in parallel...")

        # Create tasks for all chunks to run concurrently
        async def process_chunk(idx, chunk_text):
            prompt = f"""Analyze the following requirement document part ({idx+1} of {len(chunks)}) and extract all project requirements:

--- DOCUMENT START ---
{chunk_text}
--- DOCUMENT END ---

Extract the complete project analysis as structured JSON."""
            try:
                resp_text = await _call_gemini(prompt, ANALYSIS_SYSTEM_PROMPT)
            except Exception as e:
                log.append(f"   ⚠️ Gemini chunk {idx+1} analysis failed ({e})")
                raise e
            return idx, _parse_json_response(resp_text)

        tasks = [process_chunk(i, c) for i, c in enumerate(chunks)]
        results = await asyncio.gather(*tasks)

        # Merge results sequentially
        merged_units_map = {} # label -> unit
        
        for i, analysis in sorted(results, key=lambda x: x[0]):
            if i == 0:
                merged_analysis["client_name"] = analysis.get("client_name", merged_analysis["client_name"]) or merged_analysis["client_name"]
                merged_analysis["project_name"] = analysis.get("project_name", merged_analysis["project_name"])
                merged_analysis["project_description"] = analysis.get("project_description", "")
                merged_analysis["project_type"] = analysis.get("project_type", merged_analysis["project_type"])
                merged_analysis["target_audience"] = analysis.get("target_audience", "")
                
            # Append simple lists safely
            if isinstance(analysis.get("tech_stack_suggested"), list):
                merged_analysis["tech_stack_suggested"].extend(analysis.get("tech_stack_suggested", []))
            if isinstance(analysis.get("assumptions"), list):
                merged_analysis["assumptions"].extend(analysis.get("assumptions", []))
            if isinstance(analysis.get("risks"), list):
                merged_analysis["risks"].extend(analysis.get("risks", []))
            if isinstance(analysis.get("out_of_scope"), list):
                merged_analysis["out_of_scope"].extend(analysis.get("out_of_scope", []))
                
            # Merge Project Units with Confidence Deduplication
            for unit in analysis.get("project_units", []):
                if not isinstance(unit, dict):
                    continue
                unit_label = str(unit.get("label", "General Requirements")).strip()
                unit_confidence = float(unit.get("confidence", 0.5))
                
                if unit_label not in merged_units_map:
                    merged_units_map[unit_label] = unit
                    merged_units_map[unit_label]["_req_map"] = {}
                else:
                    if unit_confidence > float(merged_units_map[unit_label].get("confidence", 0)):
                        req_map = merged_units_map[unit_label].get("_req_map", {})
                        merged_units_map[unit_label] = unit
                        merged_units_map[unit_label]["_req_map"] = req_map
                
                # Merge Requirements within the unit
                req_map = merged_units_map[unit_label]["_req_map"]
                for req in unit.get("requirements", []):
                    if not isinstance(req, dict):
                        continue
                    req_title = str(req.get("title", "")).strip().lower()
                    if not req_title:
                        continue
                    
                    req_confidence = float(req.get("confidence", 0.5))
                    
                    if req_title not in req_map:
                        req_map[req_title] = req
                    else:
                        if req_confidence > float(req_map[req_title].get("confidence", 0)):
                            req_map[req_title] = req

        # Flatten units and requirements, and re-index IDs
        final_units = []
        unit_count = 0
        req_count = 0
        for label, unit in merged_units_map.items():
            unit["id"] = f"UNIT-{(unit_count+1):03d}"
            
            unit_reqs = list(unit.pop("_req_map", {}).values())
            for r_idx, req in enumerate(unit_reqs):
                req["id"] = f"{unit['id']}-REQ-{(r_idx+1):03d}"
                req_count += 1
                
            unit["requirements"] = unit_reqs
            final_units.append(unit)
            unit_count += 1
            
        merged_analysis["project_units"] = final_units

        # Deduplicate simple lists
        merged_analysis["tech_stack_suggested"] = list(set(merged_analysis["tech_stack_suggested"]))
        merged_analysis["assumptions"] = list(set(merged_analysis["assumptions"]))
        merged_analysis["risks"] = list(set(merged_analysis["risks"]))
        merged_analysis["out_of_scope"] = list(set(merged_analysis["out_of_scope"]))
        
        # Re-index units and requirements to ensure unique IDs across chunks
        unit_count = len(merged_analysis["project_units"])
        req_count = 0
        for u_idx, unit in enumerate(merged_analysis["project_units"]):
            if not unit.get("id"):
                unit["id"] = f"UNIT-{(u_idx+1):03d}"
            for r_idx, req in enumerate(unit.get("requirements", [])):
                req["id"] = f"{unit['id']}-REQ-{(r_idx+1):03d}"
                req_count += 1

        log.append(f"   ✅ Analysis complete: {req_count} requirements extracted across {unit_count} units from {len(chunks)} chunks")
        log.append(f"   Client: {merged_analysis.get('client_name', 'Unspecified Client')}")
        log.append(f"   Project: {merged_analysis.get('project_name', 'Unknown')}")
        log.append(f"   Type: {merged_analysis.get('project_type', 'Unknown')}")

        return {
            "project_analysis": merged_analysis,
            "log": log,
            "current_stage": "analysis_complete",
        }

    except json.JSONDecodeError as e:
        return {
            "errors": [f"Analysis JSON parse error: {str(e)}"],
            "log": log + [f"   ❌ Failed to parse LLM response as JSON: {str(e)}"],
            "current_stage": "analysis_failed",
        }
    except Exception as e:
        return {
            "errors": [f"Analysis error: {str(e)}"],
            "log": log + [f"   ❌ Analysis failed: {str(e)}"],
            "current_stage": "analysis_failed",
        }
