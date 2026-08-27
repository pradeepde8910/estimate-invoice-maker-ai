"""
OCR Agent — Uses Mistral OCR to extract text from PDF documents.
"""

from __future__ import annotations

import time
from pathlib import Path

from mistralai.client import Mistral

from app import config
from app.agents.state import PipelineState


async def ocr_node(state: PipelineState) -> dict:
    """
    Process PDF documents through Mistral OCR.
    Skipped automatically if needs_ocr is False.
    """
    log = ["🔍 OCR: Starting Mistral OCR processing"]

    if not state.get("needs_ocr", False):
        log.append("   ⏭️  OCR not needed, skipping")
        return {"log": log, "current_stage": "ocr_complete"}

    file_path = state.get("file_path", "")
    if not file_path:
        return {
            "errors": ["OCR: No file path provided."],
            "log": log + ["   ❌ No file path found in state"],
            "current_stage": "ocr_failed",
        }

    try:
        client = Mistral(api_key=config.MISTRAL_API_KEY)

        log.append(f"   Uploading file: {Path(file_path).name}")

        # Upload the file to Mistral
        with open(file_path, "rb") as f:
            uploaded_file = client.files.upload(
                file={
                    "file_name": Path(file_path).name,
                    "content": f,
                },
                purpose="ocr",
            )

        log.append(f"   File uploaded (ID: {uploaded_file.id})")
        log.append(f"   Running OCR with model: {config.MISTRAL_OCR_MODEL}")

        # Process with OCR
        ocr_response = client.ocr.process(
            model=config.MISTRAL_OCR_MODEL,
            document={"type": "file", "file_id": uploaded_file.id},
            include_image_base64=False,
        )

        # Extract pages
        pages = []
        full_text_parts = []

        if hasattr(ocr_response, "pages") and ocr_response.pages:
            for i, page in enumerate(ocr_response.pages):
                page_text = page.markdown if hasattr(page, "markdown") else str(page)
                pages.append({
                    "page_number": i + 1,
                    "text": page_text,
                    "has_tables": "|" in page_text and "---" in page_text,
                    "has_images": "![" in page_text,
                })
                full_text_parts.append(page_text)
        else:
            # Fallback: try to get text directly
            raw_text = str(ocr_response)
            pages.append({
                "page_number": 1,
                "text": raw_text,
                "has_tables": False,
                "has_images": False,
            })
            full_text_parts.append(raw_text)

        full_text = "\n\n---PAGE BREAK---\n\n".join(full_text_parts)

        ocr_result = {
            "total_pages": len(pages),
            "pages": pages,
            "full_text": full_text,
            "source_file": file_path,
            "source_type": "pdf",
        }

        log.append(f"   ✅ OCR complete: {len(pages)} pages, {len(full_text)} chars")

        return {
            "ocr_result": ocr_result,
            "document_text": full_text,
            "log": log,
            "current_stage": "ocr_complete",
        }

    except Exception as e:
        return {
            "errors": [f"OCR error: {str(e)}"],
            "log": log + [f"   ❌ OCR failed: {str(e)}"],
            "current_stage": "ocr_failed",
        }
