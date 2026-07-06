"""
Tests for DKB engineering knowledge body models.

Validates the schema contract that the Compiler depends on.
All tests are offline — no files, no loader, no registry.
"""
import pytest
from app.design_knowledge.knowledge.body_models import (
    AreaRange,
    BaseKnowledgeBody,
    CirculationRule,
    ConstructionGuideline,
    DimensionRule,
    EngineeringConstraint,
    LightingRule,
    OccupancyProfile,
    ResidentialKnowledgeBody,
    SpaceDefinition,
    SpaceRelationship,
    ValidationRule,
    VentilationRule,
)
from pydantic import ValidationError

# ── helpers ───────────────────────────────────────────────────────────────────


def _space(name: str = "living_room", min_sqft: float = 150, max_sqft: float = 300):
    return SpaceDefinition(name=name, area=AreaRange(min_sqft=min_sqft, max_sqft=max_sqft))


def _occupancy(**overrides):
    defaults = dict(typical_occupants=4, occupant_profile="nuclear family")
    defaults.update(overrides)
    return OccupancyProfile(**defaults)


def _minimal_residential(**overrides) -> dict:
    base = dict(
        purpose="Comfortable family living",
        planning_philosophy="Privacy and natural light for all rooms",
        occupancy=_occupancy(),
        required_spaces=[_space()],
    )
    base.update(overrides)
    return base


# ── AreaRange ─────────────────────────────────────────────────────────────────


def test_area_range_valid():
    a = AreaRange(min_sqft=100, max_sqft=200)
    assert a.min_sqft == 100
    assert a.max_sqft == 200


def test_area_range_zero_rejected():
    with pytest.raises(ValidationError):
        AreaRange(min_sqft=0, max_sqft=200)
    with pytest.raises(ValidationError):
        AreaRange(min_sqft=100, max_sqft=0)


# ── DimensionRule ─────────────────────────────────────────────────────────────


def test_dimension_rule_valid():
    d = DimensionRule(dimension="width", min_value=10.0)
    assert d.unit == "ft"


def test_dimension_rule_zero_rejected():
    with pytest.raises(ValidationError):
        DimensionRule(dimension="width", min_value=0)


# ── SpaceDefinition ───────────────────────────────────────────────────────────


def test_space_definition_minimal():
    s = _space()
    assert s.name == "living_room"
    assert s.dimensions == []
    assert s.notes is None


def test_space_definition_with_dimensions():
    s = SpaceDefinition(
        name="master_bedroom",
        area=AreaRange(min_sqft=120, max_sqft=200),
        dimensions=[DimensionRule(dimension="width", min_value=10)],
        notes="Must face east",
    )
    assert len(s.dimensions) == 1
    assert s.notes == "Must face east"


# ── SpaceRelationship ─────────────────────────────────────────────────────────


def test_space_relationship_valid_literals():
    for rel in ["direct_access", "adjacent", "visual_connect", "separated", "near"]:
        r = SpaceRelationship(from_space="kitchen", to_space="dining", relationship=rel)
        assert r.relationship == rel


def test_space_relationship_invalid_literal():
    with pytest.raises(ValidationError):
        SpaceRelationship(from_space="a", to_space="b", relationship="connected")


# ── CirculationRule ───────────────────────────────────────────────────────────


def test_circulation_rule():
    r = CirculationRule(rule="No bedroom visible from entrance", rationale="Privacy")
    assert r.rule.startswith("No")
    assert r.rationale == "Privacy"


# ── VentilationRule ───────────────────────────────────────────────────────────


def test_ventilation_rule_valid():
    for req in ["natural", "mechanical", "either"]:
        v = VentilationRule(space="kitchen", requirement=req)
        assert v.requirement == req


def test_ventilation_rule_invalid():
    with pytest.raises(ValidationError):
        VentilationRule(space="kitchen", requirement="passive")


# ── LightingRule ──────────────────────────────────────────────────────────────


def test_lighting_rule_with_ratio():
    l = LightingRule(space="living_room", requirement="natural", min_window_to_floor_ratio=0.10)
    assert l.min_window_to_floor_ratio == pytest.approx(0.10)


# ── EngineeringConstraint ─────────────────────────────────────────────────────


def test_engineering_constraint_mandatory_default():
    c = EngineeringConstraint(category="structural", constraint="Min slab thickness 150mm")
    assert c.mandatory is True


def test_engineering_constraint_categories():
    for cat in ["structural", "electrical", "plumbing", "hvac", "fire", "code"]:
        c = EngineeringConstraint(category=cat, constraint="test")
        assert c.category == cat


def test_engineering_constraint_invalid_category():
    with pytest.raises(ValidationError):
        EngineeringConstraint(category="aesthetic", constraint="test")


# ── ValidationRule ────────────────────────────────────────────────────────────


def test_validation_rule_defaults():
    r = ValidationRule(rule_id="R001", condition="All required spaces present")
    assert r.severity == "error"


def test_validation_rule_warning_severity():
    r = ValidationRule(rule_id="W001", condition="Balcony recommended", severity="warning")
    assert r.severity == "warning"


# ── BaseKnowledgeBody ─────────────────────────────────────────────────────────


def test_base_body_minimal():
    b = BaseKnowledgeBody(purpose="Test", planning_philosophy="Test philosophy")
    assert b.supported_styles == []
    assert b.constraints == []
    assert b.validation_rules == []


def test_base_body_missing_required():
    with pytest.raises(ValidationError):
        BaseKnowledgeBody(purpose="Test")  # missing planning_philosophy


# ── ResidentialKnowledgeBody ──────────────────────────────────────────────────


def test_residential_minimal_valid():
    body = ResidentialKnowledgeBody(**_minimal_residential())
    assert len(body.required_spaces) == 1
    assert body.optional_spaces == []
    assert body.space_relationships == []
    assert body.circulation == []
    assert body.ventilation == []
    assert body.lighting == []
    assert body.engineering == []
    assert body.construction == []


def test_residential_required_spaces_cannot_be_empty():
    data = _minimal_residential()
    data["required_spaces"] = []
    with pytest.raises(ValidationError):
        ResidentialKnowledgeBody(**data)


def test_residential_missing_occupancy():
    data = _minimal_residential()
    del data["occupancy"]
    with pytest.raises(ValidationError):
        ResidentialKnowledgeBody(**data)


def test_residential_full_structure():
    body = ResidentialKnowledgeBody(
        purpose="Spacious family villa",
        planning_philosophy="Each zone has acoustic and visual privacy",
        occupancy=OccupancyProfile(
            typical_occupants=5,
            occupant_profile="joint family",
            lifestyle_notes="Frequent guests",
        ),
        required_spaces=[
            _space("living_room", 200, 400),
            _space("master_bedroom", 150, 250),
            _space("kitchen", 80, 150),
        ],
        optional_spaces=[_space("study", 60, 100)],
        space_relationships=[
            SpaceRelationship(
                from_space="master_bedroom",
                to_space="master_bathroom",
                relationship="direct_access",
            )
        ],
        circulation=[
            CirculationRule(
                rule="No bedroom directly visible from entrance",
                rationale="Privacy",
            )
        ],
        ventilation=[VentilationRule(space="kitchen", requirement="natural")],
        lighting=[LightingRule(space="living_room", requirement="natural")],
        engineering=[EngineeringConstraint(category="structural", constraint="Min slab 150mm")],
        construction=[ConstructionGuideline(category="finishing", guideline="Use anti-skid tiles in wet areas")],
        supported_styles=["modern", "contemporary"],
        constraints=["Max FAR 1.5", "Max height 15m"],
        validation_rules=[ValidationRule(rule_id="R001", condition="All required spaces present")],
    )
    assert body.occupancy.typical_occupants == 5
    assert len(body.required_spaces) == 3
    assert len(body.optional_spaces) == 1
    assert body.space_relationships[0].relationship == "direct_access"
    assert body.circulation[0].rule.startswith("No")
    assert body.ventilation[0].requirement == "natural"
    assert body.lighting[0].requirement == "natural"
    assert body.engineering[0].category == "structural"
    assert body.construction[0].category == "finishing"
    assert "modern" in body.supported_styles
    assert body.validation_rules[0].rule_id == "R001"


def test_residential_is_subclass_of_base():
    body = ResidentialKnowledgeBody(**_minimal_residential())
    assert isinstance(body, BaseKnowledgeBody)
