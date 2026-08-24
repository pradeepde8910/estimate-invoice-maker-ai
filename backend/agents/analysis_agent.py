"""
Analysis Agent — Uses Groq LLM to analyze the requirement document
and extract structured project data.
"""

from __future__ import annotations

import asyncio
import json

from groq import AsyncGroq
from google import genai

import config
from agents.state import PipelineState
from utils.key_manager import KeyManager

# Initialize key manager
_groq_keys = KeyManager(config.GROQ_API_KEYS)
_gemini_keys = KeyManager(config.GEMINI_API_KEYS)

ANALYSIS_SYSTEM_PROMPT = """You are an expert business analyst and software architect. 
Your task is to analyze a requirement document and extract structured project information.

You MUST respond with ONLY valid JSON (no markdown fences, no explanations before/after).

The JSON must have this exact structure:
{
  "client_name": "string — the name of the client, company, or organization that this project is being built FOR (the requesting party/customer). Look for a company name, letterhead, 'prepared for', client signature, or organization mentioned as the requester. If genuinely not stated anywhere in the document, use 'Unspecified Client' — do NOT invent a name.",
  "project_name": "string — name of the project",
  "project_description": "string — 2-3 sentence summary",
  "project_type": "string — e.g., Web App, Mobile App, API, SaaS Platform, etc.",
  "target_audience": "string — who will use this",
  "tech_stack_suggested": ["list of recommended technologies"],
  "requirements": [
    {
      "id": "REQ-001",
      "title": "short title",
      "description": "detailed description of the requirement",
      "category": "one of: Frontend, Backend, Database, DevOps, Integration, Security, UI/UX, Testing, Documentation, Infrastructure",
      "priority": "High/Medium/Low",
      "complexity": "High/Medium/Low",
      "estimated_hours": number (your best estimate of development hours),
      "required_role": "one of: junior_developer, mid_developer, senior_developer, lead_developer, ui_ux_designer, qa_engineer, devops_engineer, project_manager, business_analyst, data_engineer, ml_engineer, security_specialist",
      "technologies": ["specific technologies needed for this requirement"],
      "dependencies": ["IDs of other requirements this depends on"]
    }
  ],
  "assumptions": ["list of assumptions you are making"],
  "risks": ["list of identified project risks"],
  "out_of_scope": ["items explicitly or implicitly out of scope"]
}

Guidelines:
- Break down the requirements into granular, estimable tasks (10-50 items typically)
- Be thorough — don't miss requirements that are implied but not explicitly stated
- Estimate hours realistically (include design, development, testing, review)
- Assign the appropriate role based on the complexity of each task
- For complex features, create multiple sub-requirements
- Include deployment, testing, and documentation requirements
- Identify integration points and API requirements
"""


async def _call_groq(text: str, system_prompt: str, max_retries: int = 3) -> str:
    """Call Groq LLM with key rotation and retry logic."""
    last_error = None

    for attempt in range(max_retries):
        api_key = await _groq_keys.get_key()
        try:
            client = AsyncGroq(api_key=api_key)

            # We no longer truncate here, as chunking is handled by the caller.

            response = await client.chat.completions.create(
                model=config.GROQ_LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.1,
                max_tokens=4000,
            )
            return response.choices[0].message.content

        except Exception as e:
            last_error = e
            await _groq_keys.mark_failed(api_key)
            if attempt < max_retries - 1:
                await asyncio.sleep(config.RETRY_DELAY_SECONDS * (attempt + 1))

    raise Exception(f"All Groq API attempts failed. Last error: {last_error}")

async def _call_gemini_fallback(text: str, system_prompt: str, max_retries: int = 3) -> str:
    """Fallback to Gemini if Groq fails."""
    last_error = None

    for attempt in range(max_retries):
        api_key = await _gemini_keys.get_key()
        try:
            client = genai.Client(api_key=api_key)
            response = await client.aio.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=system_prompt + "\n\n" + text,
            )
            return response.text

        except Exception as e:
            last_error = e
            await _gemini_keys.mark_failed(api_key)
            if attempt < max_retries - 1:
                await asyncio.sleep(config.RETRY_DELAY_SECONDS * (attempt + 1))

    raise Exception(f"All Gemini API fallback attempts failed. Last error: {last_error}")


def _parse_json_response(response_text: str) -> dict:
    """Extract and parse JSON from LLM response, handling markdown fences."""
    text = response_text.strip()

    # Remove markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json) and last line (```)
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    return json.loads(text)


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
    log.append(f"   Model: {config.GROQ_LLM_MODEL}")

    try:
        # Split text into chunks to avoid Groq TPM limits
        chunk_size = config.MAX_CHUNK_CHARS
        chunks = [document_text[i:i + chunk_size] for i in range(0, len(document_text), chunk_size)]
        
        merged_analysis = {
            "client_name": "Unspecified Client",
            "project_name": "Unknown",
            "project_description": "",
            "project_type": "Unknown",
            "target_audience": "",
            "tech_stack_suggested": [],
            "requirements": [],
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
                resp_text = await _call_groq(prompt, ANALYSIS_SYSTEM_PROMPT)
            except Exception as e:
                log.append(f"   ⚠️ Groq chunk {idx+1} analysis failed ({e}), attempting Gemini fallback...")
                resp_text = await _call_gemini_fallback(prompt, ANALYSIS_SYSTEM_PROMPT)
            return idx, _parse_json_response(resp_text)

        tasks = [process_chunk(i, c) for i, c in enumerate(chunks)]
        results = await asyncio.gather(*tasks)

        # Merge results sequentially to ensure stable requirement ordering
        for i, analysis in sorted(results, key=lambda x: x[0]):
            if i == 0:
                merged_analysis["client_name"] = analysis.get("client_name", merged_analysis["client_name"]) or merged_analysis["client_name"]
                merged_analysis["project_name"] = analysis.get("project_name", merged_analysis["project_name"])
                merged_analysis["project_description"] = analysis.get("project_description", "")
                merged_analysis["project_type"] = analysis.get("project_type", merged_analysis["project_type"])
                merged_analysis["target_audience"] = analysis.get("target_audience", "")
                
            # Append lists safely
            if isinstance(analysis.get("tech_stack_suggested"), list):
                merged_analysis["tech_stack_suggested"].extend(analysis.get("tech_stack_suggested", []))
            if isinstance(analysis.get("requirements"), list):
                merged_analysis["requirements"].extend(analysis.get("requirements", []))
            if isinstance(analysis.get("assumptions"), list):
                merged_analysis["assumptions"].extend(analysis.get("assumptions", []))
            if isinstance(analysis.get("risks"), list):
                merged_analysis["risks"].extend(analysis.get("risks", []))
            if isinstance(analysis.get("out_of_scope"), list):
                merged_analysis["out_of_scope"].extend(analysis.get("out_of_scope", []))

        # Deduplicate simple lists
        merged_analysis["tech_stack_suggested"] = list(set(merged_analysis["tech_stack_suggested"]))
        merged_analysis["assumptions"] = list(set(merged_analysis["assumptions"]))
        merged_analysis["risks"] = list(set(merged_analysis["risks"]))
        merged_analysis["out_of_scope"] = list(set(merged_analysis["out_of_scope"]))
        
        # Re-index requirements to ensure unique IDs across chunks
        for idx, req in enumerate(merged_analysis["requirements"]):
            req["id"] = f"REQ-{(idx+1):03d}"

        req_count = len(merged_analysis.get("requirements", []))
        log.append(f"   ✅ Analysis complete: {req_count} requirements extracted from {len(chunks)} chunks")
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
