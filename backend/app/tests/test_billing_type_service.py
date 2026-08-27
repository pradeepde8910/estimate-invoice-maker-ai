"""
Unit tests for app/services/billing_type_service.py — the pure decision
logic behind "why is every converted project billed as MILESTONE" (see
app/api/projects.py's convert_estimation_to_project). No DB session needed.
"""

from app.services.billing_type_service import (
    BILLING_TYPE_DESCRIPTIONS,
    decide_billing_type,
    infer_delivery_unit_label,
)


def test_milestone_units_take_priority():
    code, label = decide_billing_type(billing_units=[{"label": "Phase 1"}], has_components=True)
    assert code == "MILESTONE"
    assert label == "Milestone"


def test_component_only_when_no_billing_units():
    code, label = decide_billing_type(billing_units=[], has_components=True)
    assert code == "COMPONENT"
    assert label == "Component"


def test_custom_when_neither_units_nor_components():
    code, label = decide_billing_type(billing_units=[], has_components=False)
    assert code == "CUSTOM"
    assert label == "Item"


def test_all_codes_have_descriptions():
    for code in ("MILESTONE", "COMPONENT", "CUSTOM"):
        assert code in BILLING_TYPE_DESCRIPTIONS
        assert BILLING_TYPE_DESCRIPTIONS[code]


def test_delivery_label_inferred_when_units_share_first_word():
    units = [{"label": "Phase 1 - Discovery"}, {"label": "Phase 2 - Build"}]
    label = infer_delivery_unit_label("MILESTONE", units, "Milestone")
    assert label == "Phase"


def test_delivery_label_falls_back_when_units_disagree():
    units = [{"label": "Phase 1 - Discovery"}, {"label": "Cover 2 - Build"}]
    label = infer_delivery_unit_label("MILESTONE", units, "Milestone")
    assert label == "Milestone"


def test_delivery_label_falls_back_for_short_first_word():
    # "M1" etc: first word len <= 2 is too short to be a meaningful label.
    units = [{"label": "A1 - Discovery"}]
    label = infer_delivery_unit_label("MILESTONE", units, "Milestone")
    assert label == "Milestone"


def test_delivery_label_untouched_for_non_milestone_types():
    # Even if billing_units were (incorrectly) passed for a COMPONENT/CUSTOM
    # decision, the label inference only applies to MILESTONE.
    units = [{"label": "Phase 1"}]
    assert infer_delivery_unit_label("COMPONENT", units, "Component") == "Component"
    assert infer_delivery_unit_label("CUSTOM", units, "Item") == "Item"


def test_delivery_label_default_when_no_units():
    assert infer_delivery_unit_label("MILESTONE", [], "Milestone") == "Milestone"
