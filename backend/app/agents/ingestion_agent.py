"""
Ingestion Agent — Detects input type and prepares the document for processing.
Handles: file paths (PDF, DOCX, TXT), URLs, and raw pasted text.
"""

from __future__ import annotations

from app.agents.state import PipelineState
from app.utils.file_handler import detect_input_type, read_file, download_url


async def ingestion_node(state: PipelineState) -> dict:
    """
    Detect input type and extract/prepare content.
    Routes to OCR if PDF, otherwise passes text directly.
    """
    raw_input = state.get("raw_input", "").strip()
    log = [f"📥 Ingestion: Processing input ({len(raw_input)} chars)"]

    if not raw_input:
        return {
            "errors": ["No input provided."],
            "log": log,
            "current_stage": "ingestion_failed",
        }

    input_type = detect_input_type(raw_input)
    log.append(f"   Detected input type: {input_type}")

    try:
        if input_type == "url":
            content, file_type = download_url(raw_input)
            if file_type == "pdf":
                return {
                    "input_type": "url",
                    "file_path": content,  # temp file path
                    "file_type": "pdf",
                    "needs_ocr": True,
                    "log": log + [f"   Downloaded PDF from URL → {content}"],
                    "current_stage": "ingested",
                }
            else:
                return {
                    "input_type": "url",
                    "file_type": file_type,
                    "ingested_text": content,
                    "document_text": content,
                    "needs_ocr": False,
                    "log": log + [f"   Downloaded {file_type} content ({len(content)} chars)"],
                    "current_stage": "ingested",
                }

        elif input_type == "file":
            content, file_type = read_file(raw_input)
            if file_type == "pdf":
                return {
                    "input_type": "file",
                    "file_path": content,  # absolute path
                    "file_type": "pdf",
                    "needs_ocr": True,
                    "log": log + [f"   Local PDF file → {content}"],
                    "current_stage": "ingested",
                }
            else:
                return {
                    "input_type": "file",
                    "file_type": file_type,
                    "ingested_text": content,
                    "document_text": content,
                    "needs_ocr": False,
                    "log": log + [f"   Extracted {file_type} text ({len(content)} chars)"],
                    "current_stage": "ingested",
                }

        else:
            # Raw text input
            return {
                "input_type": "text",
                "file_type": "text",
                "ingested_text": raw_input,
                "document_text": raw_input,
                "needs_ocr": False,
                "log": log + [f"   Raw text input ({len(raw_input)} chars)"],
                "current_stage": "ingested",
            }

    except Exception as e:
        return {
            "errors": [f"Ingestion error: {str(e)}"],
            "log": log + [f"   ❌ Error: {str(e)}"],
            "current_stage": "ingestion_failed",
        }
