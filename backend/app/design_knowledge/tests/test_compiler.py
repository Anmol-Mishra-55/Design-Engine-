"""
Tests for DesignSpecCompiler — Task 6
"""
import pytest
from app.design_knowledge.design_spec.compiler import DesignSpecCompiler, DesignSpecCompilerError
from app.design_knowledge.design_spec.models import DesignSpecification
from app.design_knowledge.knowledge.body_models import (
    AreaRange,
    BaseKnowledgeBody,
    CirculationRule,
    EngineeringConstraint,
    OccupancyProfile,
    ResidentialKnowledgeBody,
    SpaceDefinition,
    SpaceRelationship,
    ValidationRule,
)
from app.design_knowledge.knowledge.models import KnowledgeEntry, KnowledgeMetadata

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_metadata(entry_id: str = "3bhk", type_: str = "residential") -> KnowledgeMetadata:
    return KnowledgeMetadata(
        id=entry_id,
        version="v1.0.0",
        type=type_,
        title="Test Entry",
        description="Test",
        owner="test",
    )


def _minimal_residential_body() -> ResidentialKnowledgeBody:
    return ResidentialKnowledgeBody(
        purpose="Test purpose",
        planning_philosophy="Test philosophy",
        occupancy=OccupancyProfile(typical_occupants=4, occupant_profile="nuclear family"),
        required_spaces=[
            SpaceDefinition(name="living_room", area=AreaRange(min_sqft=150, max_sqft=250)),
            SpaceDefinition(name="master_bedroom", area=AreaRange(min_sqft=120, max_sqft=180)),
        ],
        optional_spaces=[
            SpaceDefinition(name="study", area=AreaRange(min_sqft=80, max_sqft=120)),
        ],
        space_relationships=[
            SpaceRelationship(from_space="living_room", to_space="master_bedroom", relationship="adjacent"),
        ],
        circulation=[
            CirculationRule(rule="No bedroom visible from entrance", rationale="Privacy"),
        ],
        engineering=[
            EngineeringConstraint(category="structural", constraint="Min slab thickness 150mm"),
        ],
        validation_rules=[
            ValidationRule(rule_id="3BHK-001", condition="All required spaces present"),
            ValidationRule(rule_id="3BHK-002", condition="Master bedroom >= 120 sqft", severity="warning"),
        ],
        supported_styles=["modern", "contemporary"],
    )


def _make_entry(
    entry_id: str = "3bhk",
    type_: str = "residential",
    body: ResidentialKnowledgeBody = None,
    source_path: str = None,
) -> KnowledgeEntry:
    return KnowledgeEntry(
        metadata=_make_metadata(entry_id, type_),
        body=body or _minimal_residential_body(),
        source_path=source_path,
    )


# ── Compiler instantiation ────────────────────────────────────────────────────


def test_compiler_instantiates():
    compiler = DesignSpecCompiler()
    assert compiler is not None


# ── compile() returns DesignSpecification ─────────────────────────────────────


def test_compile_returns_design_specification():
    spec = DesignSpecCompiler().compile(_make_entry())
    assert isinstance(spec, DesignSpecification)


def test_spec_id_is_unique():
    compiler = DesignSpecCompiler()
    entry = _make_entry()
    spec1 = compiler.compile(entry)
    spec2 = compiler.compile(entry)
    assert spec1.spec_id != spec2.spec_id


def test_spec_id_contains_entry_id():
    spec = DesignSpecCompiler().compile(_make_entry("villa"))
    assert "villa" in spec.spec_id


# ── project_type and design_type ──────────────────────────────────────────────


def test_project_type_matches_metadata_type():
    spec = DesignSpecCompiler().compile(_make_entry(type_="residential"))
    assert spec.project_type == "residential"


def test_design_type_matches_metadata_id():
    spec = DesignSpecCompiler().compile(_make_entry("duplex"))
    assert spec.design_type == "duplex"


# ── spaces ────────────────────────────────────────────────────────────────────


def test_required_spaces_are_included():
    spec = DesignSpecCompiler().compile(_make_entry())
    required = [s for s in spec.spaces if s.required]
    assert len(required) == 2
    names = {s.name for s in required}
    assert "living_room" in names
    assert "master_bedroom" in names


def test_optional_spaces_are_included():
    spec = DesignSpecCompiler().compile(_make_entry())
    optional = [s for s in spec.spaces if not s.required]
    assert len(optional) == 1
    assert optional[0].name == "study"


def test_space_area_bounds_preserved():
    spec = DesignSpecCompiler().compile(_make_entry())
    living = next(s for s in spec.spaces if s.name == "living_room")
    assert living.area_min_sqft == 150
    assert living.area_max_sqft == 250


def test_total_space_count():
    spec = DesignSpecCompiler().compile(_make_entry())
    assert len(spec.spaces) == 3  # 2 required + 1 optional


# ── adjacency_graph ───────────────────────────────────────────────────────────


def test_adjacency_graph_populated():
    spec = DesignSpecCompiler().compile(_make_entry())
    assert len(spec.adjacency_graph) == 1
    edge = spec.adjacency_graph[0]
    assert edge.from_space == "living_room"
    assert edge.to_space == "master_bedroom"
    assert edge.relationship == "adjacent"


# ── circulation_rules ─────────────────────────────────────────────────────────


def test_circulation_rules_are_strings():
    spec = DesignSpecCompiler().compile(_make_entry())
    assert len(spec.circulation_rules) == 1
    assert spec.circulation_rules[0] == "No bedroom visible from entrance"


# ── engineering constraints ───────────────────────────────────────────────────


def test_engineering_constraints_populated():
    spec = DesignSpecCompiler().compile(_make_entry())
    assert len(spec.engineering) == 1
    c = spec.engineering[0]
    assert c.category == "structural"
    assert c.mandatory is True


# ── validation_rules ──────────────────────────────────────────────────────────


def test_validation_rules_populated():
    spec = DesignSpecCompiler().compile(_make_entry())
    assert len(spec.validation_rules) == 2


def test_validation_rule_ids_preserved():
    spec = DesignSpecCompiler().compile(_make_entry())
    ids = {r.rule_id for r in spec.validation_rules}
    assert "3BHK-001" in ids
    assert "3BHK-002" in ids


def test_validation_rule_severity_preserved():
    spec = DesignSpecCompiler().compile(_make_entry())
    warning_rules = [r for r in spec.validation_rules if r.severity == "warning"]
    assert len(warning_rules) == 1
    assert warning_rules[0].rule_id == "3BHK-002"


# ── supported_styles ──────────────────────────────────────────────────────────


def test_supported_styles_preserved():
    spec = DesignSpecCompiler().compile(_make_entry())
    assert "modern" in spec.supported_styles
    assert "contemporary" in spec.supported_styles


# ── generation_metadata ───────────────────────────────────────────────────────


def test_generation_metadata_knowledge_id():
    spec = DesignSpecCompiler().compile(_make_entry("penthouse"))
    assert spec.generation_metadata.knowledge_id == "penthouse"


def test_generation_metadata_version():
    spec = DesignSpecCompiler().compile(_make_entry())
    assert spec.generation_metadata.knowledge_version == "v1.0.0"


def test_generation_metadata_source_path_none_when_not_set():
    spec = DesignSpecCompiler().compile(_make_entry(source_path=None))
    assert spec.generation_metadata.knowledge_source_path is None


def test_generation_metadata_source_path_preserved():
    spec = DesignSpecCompiler().compile(_make_entry(source_path="/data/3bhk.v1.json"))
    assert spec.generation_metadata.knowledge_source_path == "/data/3bhk.v1.json"


def test_generation_metadata_compiled_at_is_datetime():
    from datetime import datetime

    spec = DesignSpecCompiler().compile(_make_entry())
    assert isinstance(spec.generation_metadata.compiled_at, datetime)


# ── raw_body ──────────────────────────────────────────────────────────────────


def test_raw_body_is_dict():
    spec = DesignSpecCompiler().compile(_make_entry())
    assert isinstance(spec.raw_body, dict)


def test_raw_body_contains_purpose():
    spec = DesignSpecCompiler().compile(_make_entry())
    assert spec.raw_body["purpose"] == "Test purpose"


# ── unknown body type raises ──────────────────────────────────────────────────


def test_unknown_body_type_raises():
    class UnknownBody(BaseKnowledgeBody):
        pass

    entry = KnowledgeEntry(
        metadata=_make_metadata(type_="unknown"),
        body=UnknownBody(purpose="x", planning_philosophy="y"),
    )
    with pytest.raises(DesignSpecCompilerError, match="No compiler registered"):
        DesignSpecCompiler().compile(entry)


# ── compile real DKB entries ──────────────────────────────────────────────────


def test_compile_all_residential_entries():
    """Load all 9 residential DKB files and compile each one."""
    from pathlib import Path

    from app.design_knowledge.knowledge.loader import KnowledgeLoader
    from app.design_knowledge.knowledge.registry import KnowledgeRegistry

    data_dir = Path("app/design_knowledge/data/residential")
    registry = KnowledgeRegistry()
    loader = KnowledgeLoader(root_directory=data_dir, registry=registry)
    loader.load_directory(data_dir)

    compiler = DesignSpecCompiler()
    for entry in registry.list():
        spec = compiler.compile(entry)
        assert isinstance(spec, DesignSpecification)
        assert spec.design_type == entry.metadata.id
        assert len(spec.spaces) > 0
        assert len(spec.validation_rules) > 0


def test_compile_villa_has_outdoor_spaces():
    """Villa must include garden or outdoor terrace in its spaces."""
    from pathlib import Path

    from app.design_knowledge.knowledge.loader import KnowledgeLoader
    from app.design_knowledge.knowledge.registry import KnowledgeRegistry

    data_dir = Path("app/design_knowledge/data/residential")
    registry = KnowledgeRegistry()
    loader = KnowledgeLoader(root_directory=data_dir, registry=registry)
    loader.load_directory(data_dir)

    entry = registry.get("villa")
    spec = DesignSpecCompiler().compile(entry)
    space_names = {s.name for s in spec.spaces}
    outdoor = {"garden", "outdoor_terrace", "terrace", "lawn"}
    assert space_names & outdoor, f"Villa spec has no outdoor spaces. Got: {space_names}"


def test_compile_penthouse_has_terrace():
    from pathlib import Path

    from app.design_knowledge.knowledge.loader import KnowledgeLoader
    from app.design_knowledge.knowledge.registry import KnowledgeRegistry

    data_dir = Path("app/design_knowledge/data/residential")
    registry = KnowledgeRegistry()
    loader = KnowledgeLoader(root_directory=data_dir, registry=registry)
    loader.load_directory(data_dir)

    entry = registry.get("penthouse")
    spec = DesignSpecCompiler().compile(entry)
    space_names = {s.name for s in spec.spaces}
    assert any("terrace" in n for n in space_names), f"Penthouse has no terrace. Got: {space_names}"
