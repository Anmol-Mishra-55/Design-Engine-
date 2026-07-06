"""
Tests for Validation Engine — Task 7
"""
from datetime import datetime

import pytest
from app.design_knowledge.design_spec.compiler import DesignSpecCompiler
from app.design_knowledge.design_spec.models import (
    AdjacencyEdge,
    DesignSpecification,
    EngineeringConstraintSpec,
    GenerationMetadata,
    SpaceSpec,
    ValidationRuleSpec,
)
from app.design_knowledge.knowledge.body_models import (
    AreaRange,
    CirculationRule,
    EngineeringConstraint,
    OccupancyProfile,
    ResidentialKnowledgeBody,
    SpaceDefinition,
    SpaceRelationship,
    ValidationRule,
)
from app.design_knowledge.knowledge.models import KnowledgeEntry, KnowledgeMetadata
from app.design_knowledge.validation.engine import VALIDATOR_REGISTRY, ValidationEngine, ValidationEngineError
from app.design_knowledge.validation.models import ValidationFinding, ValidationReport
from app.design_knowledge.validation.validators.engineering import EngineeringValidator
from app.design_knowledge.validation.validators.relationships import RelationshipValidator
from app.design_knowledge.validation.validators.rules import RuleValidator
from app.design_knowledge.validation.validators.spaces import SpaceValidator

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _meta(gid: str = "gen_meta") -> GenerationMetadata:
    return GenerationMetadata(
        knowledge_id=gid,
        knowledge_version="v1.0.0",
        knowledge_source_path=None,
    )


def _spec(
    design_type: str = "3bhk",
    project_type: str = "residential",
    spaces=None,
    adjacency=None,
    engineering=None,
    rules=None,
) -> DesignSpecification:
    _default_spaces = [
        SpaceSpec(name="master_bedroom", area_min_sqft=160, area_max_sqft=240, required=True),
        SpaceSpec(name="bedroom_2", area_min_sqft=120, area_max_sqft=190, required=True),
        SpaceSpec(name="bedroom_3", area_min_sqft=110, area_max_sqft=175, required=True),
        SpaceSpec(name="hall_living", area_min_sqft=180, area_max_sqft=280, required=True),
        SpaceSpec(name="dining_area", area_min_sqft=80, area_max_sqft=130, required=True),
        SpaceSpec(name="kitchen", area_min_sqft=80, area_max_sqft=130, required=True),
        SpaceSpec(name="master_bathroom", area_min_sqft=45, area_max_sqft=70, required=True),
        SpaceSpec(name="common_bathroom", area_min_sqft=40, area_max_sqft=60, required=True),
        SpaceSpec(name="bedroom_wing_passage", area_min_sqft=35, area_max_sqft=65, required=True),
        SpaceSpec(name="entry_foyer", area_min_sqft=25, area_max_sqft=50, required=True),
    ]
    _default_adjacency = [
        AdjacencyEdge(from_space="master_bedroom", to_space="master_bathroom", relationship="direct_access"),
        AdjacencyEdge(from_space="dining_area", to_space="kitchen", relationship="adjacent"),
        AdjacencyEdge(from_space="bedroom_2", to_space="bedroom_3", relationship="separated"),
        AdjacencyEdge(from_space="entry_foyer", to_space="hall_living", relationship="adjacent"),
        AdjacencyEdge(from_space="common_bathroom", to_space="bedroom_wing_passage", relationship="adjacent"),
    ]
    _default_engineering = [
        EngineeringConstraintSpec(category="structural", constraint="Min slab 150mm", mandatory=True),
        EngineeringConstraintSpec(category="plumbing", constraint="Wet core grouping", mandatory=True),
        EngineeringConstraintSpec(category="fire", constraint="Smoke detectors in all bedrooms", mandatory=True),
    ]
    _default_rules = [
        ValidationRuleSpec(rule_id="3BHK-001", condition="master_bedroom is present", severity="error"),
        ValidationRuleSpec(rule_id="3BHK-002", condition="bedroom_2 and bedroom_3 are present", severity="error"),
        ValidationRuleSpec(rule_id="3BHK-009", condition="master_bedroom area >= 160 sqft", severity="error"),
        ValidationRuleSpec(rule_id="3BHK-010", condition="bedroom_2 area >= 120 sqft", severity="error"),
    ]
    return DesignSpecification(
        spec_id=f"spec_{design_type}_test",
        project_type=project_type,
        design_type=design_type,
        spaces=_default_spaces if spaces is None else spaces,
        adjacency_graph=_default_adjacency if adjacency is None else adjacency,
        engineering=_default_engineering if engineering is None else engineering,
        validation_rules=_default_rules if rules is None else rules,
        generation_metadata=_meta(),
    )


# ── ValidationReport model ────────────────────────────────────────────────────


def test_report_valid_when_no_error_failures():
    report = ValidationReport(
        spec_id="s1",
        findings=[
            ValidationFinding(rule_id="R1", severity="error", message="ok", validator="V", passed=True),
        ],
    )
    assert report.valid is True


def test_report_invalid_when_error_failure():
    report = ValidationReport(
        spec_id="s1",
        findings=[
            ValidationFinding(rule_id="R1", severity="error", message="fail", validator="V", passed=False),
        ],
    )
    assert report.valid is False


def test_report_valid_with_only_warning_failures():
    report = ValidationReport(
        spec_id="s1",
        findings=[
            ValidationFinding(rule_id="W1", severity="warning", message="warn", validator="V", passed=False),
        ],
    )
    assert report.valid is True


def test_report_score_all_pass():
    report = ValidationReport(
        spec_id="s1",
        findings=[
            ValidationFinding(rule_id="R1", severity="error", message="ok", validator="V", passed=True),
            ValidationFinding(rule_id="R2", severity="error", message="ok", validator="V", passed=True),
        ],
    )
    assert report.score == 1.0


def test_report_score_half_pass():
    report = ValidationReport(
        spec_id="s1",
        findings=[
            ValidationFinding(rule_id="R1", severity="error", message="ok", validator="V", passed=True),
            ValidationFinding(rule_id="R2", severity="error", message="fail", validator="V", passed=False),
        ],
    )
    assert report.score == 0.5


def test_report_score_empty_findings():
    report = ValidationReport(spec_id="s1", findings=[])
    assert report.score == 1.0


def test_report_errors_list():
    report = ValidationReport(
        spec_id="s1",
        findings=[
            ValidationFinding(rule_id="R1", severity="error", message="bad thing", validator="V", passed=False),
            ValidationFinding(rule_id="R2", severity="warning", message="warn thing", validator="V", passed=False),
        ],
    )
    assert "bad thing" in report.errors
    assert "warn thing" not in report.errors


def test_report_warnings_list():
    report = ValidationReport(
        spec_id="s1",
        findings=[
            ValidationFinding(rule_id="W1", severity="warning", message="warn thing", validator="V", passed=False),
        ],
    )
    assert "warn thing" in report.warnings


def test_report_passed_and_failed_rules():
    report = ValidationReport(
        spec_id="s1",
        findings=[
            ValidationFinding(rule_id="R1", severity="error", message="ok", validator="V", passed=True),
            ValidationFinding(rule_id="R2", severity="error", message="fail", validator="V", passed=False),
        ],
    )
    assert "R1" in report.passed_rules
    assert "R2" in report.failed_rules


def test_report_validated_at_is_datetime():
    report = ValidationReport(spec_id="s1", findings=[])
    assert isinstance(report.validated_at, datetime)


# ── SpaceValidator ────────────────────────────────────────────────────────────


def test_space_validator_passes_valid_spec():
    findings = SpaceValidator().validate(_spec())
    failures = [f for f in findings if not f.passed and f.severity == "error"]
    assert failures == []


def test_space_validator_detects_invalid_area_range():
    spaces = [SpaceSpec(name="bad_room", area_min_sqft=300, area_max_sqft=100, required=True)]
    spec = _spec(spaces=spaces)
    findings = SpaceValidator().validate(spec)
    failures = [f for f in findings if not f.passed]
    assert any("invalid area range" in f.message for f in failures)


def test_space_validator_nonempty_check_fails_on_empty():
    spec = _spec(spaces=[])
    findings = SpaceValidator().validate(spec)
    assert any(not f.passed for f in findings)


def test_space_validator_name():
    assert SpaceValidator().name == "SpaceValidator"


# ── RelationshipValidator ─────────────────────────────────────────────────────


def test_relationship_validator_passes_valid_spec():
    findings = RelationshipValidator().validate(_spec())
    errors = [f for f in findings if not f.passed and f.severity == "error"]
    assert errors == []


def test_relationship_validator_detects_dangling_from_space():
    adj = [AdjacencyEdge(from_space="ghost_room", to_space="kitchen", relationship="adjacent")]
    spec = _spec(adjacency=adj)
    findings = RelationshipValidator().validate(spec)
    assert any("ghost_room" in f.message for f in findings if not f.passed)


def test_relationship_validator_detects_dangling_to_space():
    adj = [AdjacencyEdge(from_space="kitchen", to_space="ghost_room", relationship="adjacent")]
    spec = _spec(adjacency=adj)
    findings = RelationshipValidator().validate(spec)
    assert any("ghost_room" in f.message for f in findings if not f.passed)


def test_relationship_validator_detects_self_reference():
    adj = [AdjacencyEdge(from_space="kitchen", to_space="kitchen", relationship="adjacent")]
    spec = _spec(adjacency=adj)
    findings = RelationshipValidator().validate(spec)
    assert any("same from and to" in f.message for f in findings if not f.passed)


def test_relationship_validator_detects_contradiction():
    adj = [
        AdjacencyEdge(from_space="bedroom_2", to_space="bedroom_3", relationship="separated"),
        AdjacencyEdge(from_space="bedroom_2", to_space="bedroom_3", relationship="direct_access"),
    ]
    spec = _spec(adjacency=adj)
    findings = RelationshipValidator().validate(spec)
    assert any("contradiction" in f.message.lower() for f in findings if not f.passed)


def test_relationship_validator_warns_empty_graph():
    spec = _spec(adjacency=[])
    findings = RelationshipValidator().validate(spec)
    assert any(not f.passed for f in findings)


# ── EngineeringValidator ──────────────────────────────────────────────────────


def test_engineering_validator_passes_valid_spec():
    findings = EngineeringValidator().validate(_spec())
    errors = [f for f in findings if not f.passed and f.severity == "error"]
    assert errors == []


def test_engineering_validator_detects_missing_structural():
    eng = [
        EngineeringConstraintSpec(category="plumbing", constraint="wet core", mandatory=True),
        EngineeringConstraintSpec(category="fire", constraint="smoke detectors", mandatory=True),
    ]
    spec = _spec(engineering=eng)
    findings = EngineeringValidator().validate(spec)
    assert any("structural" in f.message and not f.passed for f in findings)


def test_engineering_validator_detects_missing_fire():
    eng = [
        EngineeringConstraintSpec(category="structural", constraint="slab", mandatory=True),
        EngineeringConstraintSpec(category="plumbing", constraint="wet core", mandatory=True),
    ]
    spec = _spec(engineering=eng)
    findings = EngineeringValidator().validate(spec)
    assert any("fire" in f.message and not f.passed for f in findings)


def test_engineering_validator_detects_empty_constraint_text():
    eng = [
        EngineeringConstraintSpec(category="structural", constraint="  ", mandatory=True),
        EngineeringConstraintSpec(category="plumbing", constraint="wet core", mandatory=True),
        EngineeringConstraintSpec(category="fire", constraint="smoke", mandatory=True),
    ]
    spec = _spec(engineering=eng)
    findings = EngineeringValidator().validate(spec)
    assert any("empty text" in f.message and not f.passed for f in findings)


def test_engineering_validator_warns_duplicate():
    eng = [
        EngineeringConstraintSpec(category="structural", constraint="Min slab 150mm", mandatory=True),
        EngineeringConstraintSpec(category="structural", constraint="Min slab 150mm", mandatory=True),
        EngineeringConstraintSpec(category="plumbing", constraint="wet core", mandatory=True),
        EngineeringConstraintSpec(category="fire", constraint="smoke", mandatory=True),
    ]
    spec = _spec(engineering=eng)
    findings = EngineeringValidator().validate(spec)
    assert any("duplicate" in f.message.lower() and f.severity == "warning" for f in findings)


# ── RuleValidator ─────────────────────────────────────────────────────────────


def test_rule_validator_passes_present_space():
    rules = [ValidationRuleSpec(rule_id="R1", condition="master_bedroom is present", severity="error")]
    spec = _spec(rules=rules)
    findings = RuleValidator().validate(spec)
    r1 = next(f for f in findings if f.rule_id == "R1")
    assert r1.passed is True


def test_rule_validator_fails_missing_space():
    rules = [ValidationRuleSpec(rule_id="R1", condition="servant_quarter is present", severity="error")]
    spec = _spec(rules=rules)
    findings = RuleValidator().validate(spec)
    r1 = next(f for f in findings if f.rule_id == "R1")
    assert r1.passed is False


def test_rule_validator_area_gte_passes():
    rules = [ValidationRuleSpec(rule_id="R1", condition="master_bedroom area >= 160 sqft", severity="error")]
    spec = _spec(rules=rules)
    findings = RuleValidator().validate(spec)
    r1 = next(f for f in findings if f.rule_id == "R1")
    assert r1.passed is True


def test_rule_validator_area_gte_fails():
    rules = [ValidationRuleSpec(rule_id="R1", condition="master_bedroom area >= 999 sqft", severity="error")]
    spec = _spec(rules=rules)
    findings = RuleValidator().validate(spec)
    r1 = next(f for f in findings if f.rule_id == "R1")
    assert r1.passed is False


def test_rule_validator_two_spaces_present():
    rules = [ValidationRuleSpec(rule_id="R1", condition="bedroom_2 and bedroom_3 are present", severity="error")]
    spec = _spec(rules=rules)
    findings = RuleValidator().validate(spec)
    r1 = next(f for f in findings if f.rule_id == "R1")
    assert r1.passed is True


def test_rule_validator_two_spaces_one_missing():
    rules = [ValidationRuleSpec(rule_id="R1", condition="bedroom_2 and ghost_room are present", severity="error")]
    spec = _spec(rules=rules)
    findings = RuleValidator().validate(spec)
    r1 = next(f for f in findings if f.rule_id == "R1")
    assert r1.passed is False


def test_rule_validator_relationship_adjacent_passes():
    rules = [ValidationRuleSpec(rule_id="R1", condition="dining_area is adjacent to kitchen", severity="error")]
    spec = _spec(rules=rules)
    findings = RuleValidator().validate(spec)
    r1 = next(f for f in findings if f.rule_id == "R1")
    assert r1.passed is True


def test_rule_validator_relationship_missing_fails():
    rules = [ValidationRuleSpec(rule_id="R1", condition="master_bedroom is adjacent to kitchen", severity="error")]
    spec = _spec(rules=rules)
    findings = RuleValidator().validate(spec)
    r1 = next(f for f in findings if f.rule_id == "R1")
    assert r1.passed is False


def test_rule_validator_no_direct_access_passes():
    rules = [
        ValidationRuleSpec(
            rule_id="R1", condition="no bedroom_2 is directly accessible from hall_living", severity="error"
        )
    ]
    spec = _spec(rules=rules)
    findings = RuleValidator().validate(spec)
    r1 = next(f for f in findings if f.rule_id == "R1")
    assert r1.passed is True


def test_rule_validator_unrecognised_condition_does_not_fail():
    rules = [ValidationRuleSpec(rule_id="R1", condition="some future condition we cannot parse yet", severity="error")]
    spec = _spec(rules=rules)
    findings = RuleValidator().validate(spec)
    r1 = next(f for f in findings if f.rule_id == "R1")
    assert r1.passed is True  # unrecognised = skip, not fail
    assert r1.severity == "warning"


def test_rule_validator_warns_empty_rules():
    spec = _spec(rules=[])
    findings = RuleValidator().validate(spec)
    assert any(not f.passed for f in findings)


# ── ValidationEngine ──────────────────────────────────────────────────────────


def test_engine_instantiates():
    assert ValidationEngine() is not None


def test_engine_returns_report():
    report = ValidationEngine().validate(_spec())
    assert isinstance(report, ValidationReport)


def test_engine_report_spec_id_matches():
    spec = _spec()
    report = ValidationEngine().validate(spec)
    assert report.spec_id == spec.spec_id


def test_engine_valid_spec_has_no_errors():
    report = ValidationEngine().validate(_spec())
    assert report.errors == []


def test_engine_score_is_float_between_0_and_1():
    report = ValidationEngine().validate(_spec())
    assert 0.0 <= report.score <= 1.0


def test_engine_unknown_project_type_raises():
    spec = _spec(project_type="commercial")
    with pytest.raises(ValidationEngineError, match="No validator registered"):
        ValidationEngine().validate(spec)


def test_validator_registry_contains_residential():
    assert "residential" in VALIDATOR_REGISTRY


# ── End-to-end: all 9 real DKB entries ───────────────────────────────────────


def _load_all_residential():
    from pathlib import Path

    from app.design_knowledge.knowledge.loader import KnowledgeLoader
    from app.design_knowledge.knowledge.registry import KnowledgeRegistry

    data_dir = Path("app/design_knowledge/data/residential")
    registry = KnowledgeRegistry()
    loader = KnowledgeLoader(root_directory=data_dir, registry=registry)
    loader.load_directory(data_dir)
    return registry


def test_all_residential_entries_produce_valid_reports():
    """Every real DKB entry must compile and validate without engine errors."""
    registry = _load_all_residential()
    compiler = DesignSpecCompiler()
    engine = ValidationEngine()

    for entry in registry.list():
        spec = compiler.compile(entry)
        report = engine.validate(spec)
        assert isinstance(report, ValidationReport), f"{entry.metadata.id}: not a ValidationReport"
        assert report.spec_id == spec.spec_id


def test_all_residential_entries_have_findings():
    """Every compiled spec must produce at least some findings."""
    registry = _load_all_residential()
    compiler = DesignSpecCompiler()
    engine = ValidationEngine()

    for entry in registry.list():
        spec = compiler.compile(entry)
        report = engine.validate(spec)
        assert len(report.findings) > 0, f"{entry.metadata.id}: no findings produced"


def test_all_residential_entries_score_above_zero():
    """Every real DKB entry should score > 0 (at least some rules pass)."""
    registry = _load_all_residential()
    compiler = DesignSpecCompiler()
    engine = ValidationEngine()

    for entry in registry.list():
        spec = compiler.compile(entry)
        report = engine.validate(spec)
        assert report.score > 0.0, f"{entry.metadata.id}: score is 0"


def test_3bhk_validation_passes_core_rules():
    """3BHK must pass its core space and area rules."""
    registry = _load_all_residential()
    entry = registry.get("3bhk")
    spec = DesignSpecCompiler().compile(entry)
    report = ValidationEngine().validate(spec)

    # master_bedroom must be present
    assert any(f.rule_id == "3BHK-001" and f.passed for f in report.findings)
    # bedroom_2 and bedroom_3 must be present
    assert any(f.rule_id == "3BHK-002" and f.passed for f in report.findings)


def test_studio_validation_passes_core_rules():
    """Studio must pass its core space rules."""
    registry = _load_all_residential()
    entry = registry.get("studio")
    spec = DesignSpecCompiler().compile(entry)
    report = ValidationEngine().validate(spec)

    assert any(f.rule_id == "STU-001" and f.passed for f in report.findings)
    assert any(f.rule_id == "STU-002" and f.passed for f in report.findings)
    assert any(f.rule_id == "STU-003" and f.passed for f in report.findings)


def test_report_has_passed_and_failed_rule_lists():
    report = ValidationEngine().validate(_spec())
    assert isinstance(report.passed_rules, list)
    assert isinstance(report.failed_rules, list)
    assert len(report.passed_rules) + len(report.failed_rules) == len(report.findings)
