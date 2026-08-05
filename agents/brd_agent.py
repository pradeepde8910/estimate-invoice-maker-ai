"""
BRD Agent — Generates a detailed and professional Business Requirements Document (BRD).
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from groq import AsyncGroq
from google import genai

import config
from agents.state import PipelineState
from utils.key_manager import KeyManager

# Initialize key manager for Groq key rotation
_groq_keys = KeyManager(config.GROQ_API_KEYS)
_gemini_keys = KeyManager(config.GEMINI_API_KEYS)

BRD_SYSTEM_PROMPT = """You are a Principal Business Analyst. Your task is to generate a comprehensive, highly detailed, and professional Business Requirements Document (BRD) in Markdown format based on the project analysis, cost estimates, and raw user input.

The BRD must focus on the business vision, goals, stakeholders, scope, and high-level requirements.

Make the document extremely professional, exhaustive, and realistic. Use proper Markdown formatting with headers, lists, tables, and bold text. Do not use placeholders or write "to be determined"; instead, provide realistic defaults based on the project context.

The BRD must follow this exact structure:

# 💼 Business Requirements Document (BRD)

## 1. Document Control & Metadata
Provide a metadata table showing Document Title, Version, Author, Date, and Status (Draft/Ready for Review).

## 2. Executive Summary & Project Purpose
- **Context & Opportunity**: Explain the background, the problem being solved, and why this project is important.
- **Project Vision**: Describe the vision statement of the final product.
- **Scope Statement**: High-level summary of what the system will achieve.

## 3. Business Goals & Strategic Objectives
- Detail the business goals (e.g., reduce manual efforts by 40%, increase sales, improve customer retention).
- Create a Markdown table linking Objectives to their respective Measurable Target (KPI) and Timeline.

## 4. Stakeholders & User Personas
Identify the key stakeholders and define 2-3 detailed user personas:
- **Personas**: For each persona, specify Role, Goals, Pain Points, and how they will interact with the system.

## 5. Functional Business Requirements (High-Level)
Group requirements into logical business domains/modules and list them. Include:
- Requirement ID (e.g., BREQ-001)
- Requirement Name
- Business Description
- Business Value/Priority (High/Medium/Low)
- Stakeholder Owner

## 6. Business Constraints, Assumptions & Dependencies
- **Constraints**: Cost/budget constraints, timeline constraints, compliance/regulatory constraints, technology constraints.
- **Assumptions**: Assumptions made about inputs, user knowledge, third-party availabilities, etc.
- **Dependencies**: Internal or external systems/vendors this project depends on.

## 7. Business Risks & Mitigation Strategies
Create a detailed Markdown table with columns: Risk ID, Risk Description, Impact Level (High/Medium/Low), Probability (High/Medium/Low), and Mitigation Strategy.

## 8. Critical Success Factors (CSFs) & Key Performance Indicators (KPIs)
- Detail how the success of the project will be evaluated post-launch.
- List specific KPIs (e.g., system availability, user adoption rate, transaction processing time).
"""

async def _call_groq(text: str, system_prompt: str, max_retries: int = 3) -> str:
    """Call Groq LLM with key rotation and retry logic."""
    last_error = None

    for attempt in range(max_retries):
        api_key = await _groq_keys.get_key()
        try:
            client = AsyncGroq(api_key=api_key)
            response = await client.chat.completions.create(
                model=config.GROQ_LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.2,
                max_tokens=3500,
            )
            return response.choices[0].message.content

        except Exception as e:
            last_error = e
            await _groq_keys.mark_failed(api_key)
            if attempt < max_retries - 1:
                await asyncio.sleep(config.RETRY_DELAY_SECONDS * (attempt + 1))

    raise Exception(f"All Groq API attempts failed for BRD Agent. Last error: {last_error}")

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

async def brd_node(state: PipelineState) -> dict:
    """
    Agent node to generate a detailed Business Requirements Document (BRD).
    """
    if not state.get("generate_brd", False):
        return {
            "log": ["💼 BRD: Skipping generation (flag not set)"]
        }

    log = ["💼 BRD: Generating Business Requirements Document"]
    
    project_analysis = state.get("project_analysis", {})
    cost_estimation = state.get("cost_estimation", {})
    
    # Simplify project analysis to save tokens and prevent rate limits
    simplified_requirements = [
        {
            "id": r.get("id"),
            "title": r.get("title"),
            "description": r.get("description"),
            "category": r.get("category"),
            "priority": r.get("priority"),
        }
        for r in project_analysis.get("requirements", [])
    ]
    simplified_analysis = {
        "project_name": project_analysis.get("project_name"),
        "project_description": project_analysis.get("project_description"),
        "project_type": project_analysis.get("project_type"),
        "target_audience": project_analysis.get("target_audience"),
        "tech_stack_suggested": project_analysis.get("tech_stack_suggested"),
        "requirements": simplified_requirements,
        "assumptions": project_analysis.get("assumptions"),
        "risks": project_analysis.get("risks"),
        "out_of_scope": project_analysis.get("out_of_scope"),
    }

    # Simplify estimation to avoid duplicate requirements list in category_breakdown items
    simplified_estimation = {
        "timeline_weeks": cost_estimation.get("timeline_weeks"),
        "phases": cost_estimation.get("phases"),
        "team_composition": cost_estimation.get("team_composition"),
        "grand_total": cost_estimation.get("grand_total"),
    }
    
    # Package context into a prompt
    context = f"""
    --- PROJECT ANALYSIS DATA ---
    {simplified_analysis}
    
    --- ESTIMATION & TIMELINE DATA ---
    {simplified_estimation}
    """
    
    try:
        brd_text = await _call_groq(context, BRD_SYSTEM_PROMPT)
        log.append("   ✅ BRD generation complete (via Groq)")
        return {
            "brd_markdown": brd_text,
            "log": log,
            "current_stage": "brd_complete"
        }
    except Exception as e:
        log.append(f"   ⚠️ Groq BRD generation failed ({e}), attempting Gemini fallback...")
        try:
            brd_text = await _call_gemini_fallback(context, BRD_SYSTEM_PROMPT)
            log.append("   ✅ BRD generation complete (via Gemini Fallback)")
            return {
                "brd_markdown": brd_text,
                "log": log,
                "current_stage": "brd_complete"
            }
        except Exception as gemini_err:
            log.append(f"   ❌ BRD generation failed: {gemini_err}")
            return {
                "errors": [f"BRD generation error: {str(gemini_err)}"],
                "log": log,
                "current_stage": "brd_failed"
            }
