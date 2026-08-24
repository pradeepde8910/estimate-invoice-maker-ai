"""
Matches a free-text billing description (e.g. an invoice line-item
description, or eventually an AI-generated one from the estimation
pipeline) against the approved billing_classifications catalog.

Deterministic keyword scoring on purpose — no LLM call here. The catalog is
the single approved source of truth for which HSN/SAC codes this business
uses; an LLM call in this path would just be a way to eventually generate an
HSN/SAC code that isn't in the catalog, undermining the entire point of
having an approved list.
"""
from __future__ import annotations

import re
from app.models.master import BillingClassification


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _score(query: str, query_tokens: set[str], classification: BillingClassification) -> int:
    score = 0

    description_tokens = _tokenize(classification.description)
    score += 2 * len(query_tokens & description_tokens)

    category_tokens = _tokenize(classification.category)
    score += len(query_tokens & category_tokens)

    if classification.keywords:
        for phrase in classification.keywords.split(","):
            phrase = phrase.strip().lower()
            if phrase and phrase in query:
                # Whole-phrase substring hit (e.g. "rest api" inside the query)
                # is a stronger signal than single-token overlap, so it's
                # weighted higher below.
                score += 3 if " " in phrase else 1

    return score


def match_billing_classifications(
    description: str,
    classifications: list[BillingClassification],
    limit: int = 5,
) -> list[dict]:
    """
    Returns the top `limit` classifications ranked by keyword overlap with
    `description`, each annotated with its match `score` (0 = no keyword
    overlap at all — callers should treat a 0 score as "no confident match,
    ask the user to pick manually" rather than silently using the top result).
    """
    query = description.lower()
    query_tokens = _tokenize(description)
    scored = [
        {**_as_dict(c), "score": _score(query, query_tokens, c)}
        for c in classifications
    ]
    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored[:limit]


def _as_dict(c: BillingClassification) -> dict:
    return {
        "id": c.id,
        "category": c.category,
        "description": c.description,
        "item_type": c.item_type,
        "hsn_sac_code": c.hsn_sac_code,
        "hsn_sac_type": c.hsn_sac_type,
        "gst_rate": c.gst_rate,
        "keywords": c.keywords,
        "active": c.active,
    }
