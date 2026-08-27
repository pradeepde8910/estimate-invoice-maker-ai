"""
Pure decision logic for inferring a converted project's billing type from
its estimation's actual structure — extracted out of
app.api.project.convert_estimation_to_project so it's unit-testable without
a database session.

See app/api/project.py's "3.5 Decide the project's billing type" comment
for the full rationale: MILESTONE when real AI billing units exist (the
dominant billing rhythm, even if incidental commercial components ride
alongside), COMPONENT when only commercial components exist, CUSTOM for a
flat-scope project with neither.
"""

from __future__ import annotations

BILLING_TYPE_DESCRIPTIONS = {
    "MILESTONE": "Milestone Billing",
    "COMPONENT": "Component-Based Billing",
    "CUSTOM": "Flat / Ad-hoc Billing",
}


def decide_billing_type(billing_units: list, has_components: bool) -> tuple[str, str]:
    """Returns (billing_type_code, default_delivery_unit_label)."""
    if billing_units:
        return "MILESTONE", "Milestone"
    if has_components:
        return "COMPONENT", "Component"
    return "CUSTOM", "Item"


def infer_delivery_unit_label(billing_type_code: str, billing_units: list, default_label: str) -> str:
    """Refines the generic default_label using the AI units' own wording —
    e.g. if every billing unit's label starts with "Phase", the config's
    delivery_unit_label becomes "Phase" instead of the generic "Milestone"."""
    if billing_type_code != "MILESTONE" or not billing_units:
        return default_label

    first_label = billing_units[0].get("label", "Milestone").strip()
    first_word = first_label.split(" ")[0]
    if len(first_word) <= 2:
        return default_label

    all_share = all(
        u.get("label", "").strip().split(" ")[0].lower() == first_word.lower()
        for u in billing_units
    )
    return first_word.capitalize() if all_share else default_label
