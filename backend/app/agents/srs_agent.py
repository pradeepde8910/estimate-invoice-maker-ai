"""
SRS Agent — Generates a detailed and professional Software Requirements Specification (SRS) document.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from google import genai

from app import config
from app.agents.state import PipelineState
from app.core.key_manager import KeyManager

# Initialize key manager for Gemini key rotation
_gemini_keys = KeyManager(config.GEMINI_API_KEYS)

SRS_SYSTEM_PROMPT = """You are a Principal Software Architect. Your task is to generate a comprehensive, highly detailed, and professional Software Requirements Specification (SRS) document in Markdown format based on the project analysis, cost estimates, and raw user input.

The SRS must focus on the technical details, architecture, data schemas, API endpoints, functional flows, and non-functional requirements.

Make the document extremely professional, technical, exhaustive, and realistic. Use proper Markdown formatting with headers, lists, tables, and code blocks. Do not use placeholders; instead, provide realistic defaults based on the project context. Include code blocks for database schemas (SQL or NoSQL) and API structures.

Include a visual entity-relationship (ER) diagram in Mermaid syntax under the Database Schema section.

The SRS must follow this exact structure:

# 📝 Software Requirements Specification (SRS)

## 1. Document Control & Metadata
Provide a metadata table showing Document Title, Version, Author, Date, and Status (Draft/Ready for Review).

## 2. Introduction
- **Purpose**: Explain what this document defines and its target audience.
- **Product Scope**: Outline the scope of the software application being specified.
- **Definitions, Acronyms, and Abbreviations**: Define any technical terms or acronyms.

## 3. Overall Description
- **Product Perspective**: How the product fits into larger ecosystems (e.g., cloud environment, mobile platforms).
- **Product Functions**: Summary of the main functions of the software.
- **User Classes & Characteristics**: Describe the users of the system (e.g., admin, standard user, guest) and their needs.
- **Operating Environment**: Operating systems, browsers, servers, and hardware constraints.
- **Design & Implementation Constraints**: Constraints on coding languages, databases, security standards, etc.

## 4. System Features & Functional Requirements
Break down the main system features. For each major feature/module:
- **Feature Name**
- **Description & Priority**
- **Detailed Functional Requirements (IPO Flow)**:
  - **Input**: What data does the user or system provide?
  - **Processing**: What logic/rules does the system execute?
  - **Output**: What is the result or return data?
Provide a detailed table of requirements containing ID, Feature, Description, Priority, and Complexity.

## 5. External Interface Requirements
- **User Interfaces**: Design standards, responsive layout principles, and structural layout concepts.
- **Software Interfaces**: Integrations with external software, databases, or operating systems.
- **API Specifications**: Define 2-3 key API endpoints (e.g., REST endpoints, GraphQL queries) with HTTP method, URL path, request body JSON format, and response body JSON format.

## 6. System Data Models & Database Schema Designs
- **Database Architecture**: Specify database type (e.g., PostgreSQL, MongoDB) with justification.
- **Database Schema**: Provide raw SQL `CREATE TABLE` scripts or MongoDB schema structures.
- **Entity Relationship (ER) Diagram**: Include a valid Mermaid code block showing the database structure, like:
```mermaid
erDiagram
    USERS ||--o{ POSTS : writes
    USERS {
        int id
        string email
    }
    POSTS {
        int id
        int user_id
        string content
    }
```

## 7. Non-Functional Requirements (NFRs)
- **Performance**: Response time, throughput, concurrent user capacity.
- **Reliability & Availability**: Uptime percentage, failure recovery, backup schedules.
- **Security**: Authentication, encryption at rest/in transit, role-based access control, GDPR/HIPAA compliance.
- **Scalability & Maintainability**: Vertical/horizontal scaling plans, containerization (Docker).
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

async def srs_node(state: PipelineState) -> dict:
    """
    Agent node to generate a detailed Software Requirements Specification (SRS).
    """
    if not state.get("generate_srs", False):
        return {
            "log": ["📝 SRS: Skipping generation (flag not set)"]
        }

    log = ["📝 SRS: Generating Software Requirements Specification"]
    
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
            "complexity": r.get("complexity"),
            "technologies": r.get("technologies"),
            "dependencies": r.get("dependencies"),
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

    # Simplify estimation to only timeline (exclude pricing and cost items)
    simplified_estimation = {
        "timeline_weeks": cost_estimation.get("timeline_weeks"),
        "phases": cost_estimation.get("phases"),
    }
    
    # Package context into a prompt
    context = f"""
    --- PROJECT ANALYSIS DATA ---
    {simplified_analysis}
    
    --- ESTIMATION & TIMELINE DATA ---
    {simplified_estimation}
    """
    
    try:
        srs_text = await _call_gemini(context, SRS_SYSTEM_PROMPT)
        log.append(f"   ✅ SRS successfully generated ({len(srs_text)} chars)")
        return {
            "srs_markdown": srs_text,
            "log": log,
            "current_stage": "srs_complete"
        }
    except Exception as e:
        log.append(f"   ❌ SRS generation failed: {e}")
        return {
            "errors": [f"SRS generation error: {str(e)}"],
            "log": log,
            "current_stage": "srs_failed"
        }
