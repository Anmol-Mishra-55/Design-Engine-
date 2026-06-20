"""
Sprint QA Matrix — Task 14
===========================
Covers all 5 mandatory sprint scenarios end-to-end through the pipeline:

    SemanticResolver → ExecutionSchemaFactory → TTGPayloadBuilder

Scenarios:
    1. Generate 1BHK Mumbai apartment   → domain=architecture
    2. Generate delivery drone          → domain=vehicle
    3. Generate checkpoint barrier      → domain=gameplay
    4. Generate industrial zone         → domain=environment
    5. Generate combat arena            → domain=gameplay

Verified per scenario:
    ✓ domain
    ✓ entity
    ✓ geometry_family
    ✓ executionSchema generation  (via ExecutionSchemaFactory)
    ✓ TTG payload generation      (via TTGPayloadBuilder)
    ✓ trace preservation
    ✓ No contamination

Contamination guards (fail if present):
    ✗ vehicle contains apartment geometry
    ✗ architecture contains rotor geometry
    ✗ environment contains bedroom geometry
"""

import json
import json as _json
from pathlib import Path as _Path

import pytest
from app.adapters.ttg_payload_builder import TTGPayloadBuilder
from app.design_semantics.semantic_resolver import SemanticResolver
from app.factories.execution_schema_factory import ExecutionSchemaFactory

_CONSTRAINTS = _json.loads(
    (_Path(__file__).resolve().parent.parent / "app" / "design_semantics" / "generation_constraints.json").read_text(
        encoding="utf-8"
    )
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_resolver = SemanticResolver()
_factory = ExecutionSchemaFactory()
_builder = TTGPayloadBuilder()

_BUCKET_URL = "https://bhiv-bucket.onrender.com/bucket/artifact/qa-test-001"
_SPEC_JSON = {"type": "qa_spec", "version": "1.0", "qa": True}


def _resolve(module: str, topic: str) -> dict:
    return _resolver.resolve({"module": module, "topic": topic, "intent": "", "tasks": []})


def _build_payload(semantic: dict, trace_id: str) -> dict:
    payload = _builder.build(
        semantic_resolution=semantic,
        spec_json=_SPEC_JSON,
        bucket_urls=[_BUCKET_URL],
        trace_id=trace_id,
        execution_id=f"exec_{trace_id}",
    )
    return payload.to_dict()


def _schema_text(payload_dict: dict) -> str:
    """Serialise executionSchema to string for contamination scanning."""
    return json.dumps(payload_dict["executionSchema"]).lower()


# ---------------------------------------------------------------------------
# Scenario 1 — Generate 1BHK Mumbai apartment → architecture
# ---------------------------------------------------------------------------


class TestScenario1_1BHKMumbai:
    """Generate 1BHK Mumbai apartment → expected domain=architecture"""

    TRACE = "qa-trace-scenario-1"

    @pytest.fixture(scope="class")
    def semantic(self):
        return _resolve("architecture", "1BHK_apartment")

    @pytest.fixture(scope="class")
    def schema(self, semantic):
        return _factory.build(semantic)

    @pytest.fixture(scope="class")
    def payload(self, semantic):
        return _build_payload(semantic, self.TRACE)

    # --- domain ---
    def test_domain_is_architecture(self, semantic):
        assert semantic["domain"] == "architecture"

    # --- entity ---
    def test_entity_is_1bhk(self, semantic):
        assert semantic["entity"] == "1bhk"

    # --- geometry_family ---
    def test_geometry_family_is_apartment_layout(self, semantic):
        assert semantic["geometry_family"] == "apartment_layout"

    # --- executionSchema ---
    def test_schema_type_is_scene_layout(self, schema):
        assert schema["schema_type"] == "scene/layout"

    def test_schema_domain_is_architecture(self, schema):
        assert schema["domain"] == "architecture"

    def test_schema_generator_is_layout_generator(self, schema):
        assert schema["generator"] == "layout_generator"

    def test_schema_generation_mode_is_layout(self, schema):
        assert schema["generation_mode"] == "layout"

    def test_schema_has_layout_config(self, schema):
        assert "layout_config" in schema

    def test_schema_version_present(self, schema):
        assert schema.get("schema_version") == "1.0"

    # --- TTG payload ---
    def test_payload_has_execution_id(self, payload):
        assert payload["execution_id"] == f"exec_{self.TRACE}"

    def test_payload_trace_preserved(self, payload):
        assert payload["trace_id"] == self.TRACE

    def test_payload_has_execution_schema(self, payload):
        assert isinstance(payload["executionSchema"], dict)
        assert payload["executionSchema"]

    def test_payload_has_spec_json(self, payload):
        assert payload["spec_json"] == _SPEC_JSON

    def test_payload_bucket_urls_preserved(self, payload):
        assert _BUCKET_URL in payload["bucket_urls"]

    # --- contamination guards ---
    def test_no_rotor_in_architecture_schema(self, payload):
        assert "rotor" not in _schema_text(
            payload
        ), "CONTAMINATION: architecture schema contains 'rotor' (vehicle term)"

    def test_no_wing_in_architecture_schema(self, payload):
        assert "wing" not in _schema_text(payload), "CONTAMINATION: architecture schema contains 'wing' (vehicle term)"

    def test_no_engine_in_architecture_schema(self, payload):
        text = _schema_text(payload)
        # 'engine' may appear in generator name — check only as standalone vehicle term
        assert "vehicle_engine" not in text, "CONTAMINATION: architecture schema contains 'vehicle_engine'"
        assert "thruster" not in text, "CONTAMINATION: architecture schema contains 'thruster' (vehicle term)"

    def test_no_vehicle_domain_in_architecture_schema(self, payload):
        schema = payload["executionSchema"]
        assert schema.get("domain") != "vehicle"


# ---------------------------------------------------------------------------
# Scenario 2 — Generate delivery drone → vehicle
# ---------------------------------------------------------------------------


class TestScenario2_DeliveryDrone:
    """Generate delivery drone → expected domain=vehicle, entity=drone"""

    TRACE = "qa-trace-scenario-2"

    @pytest.fixture(scope="class")
    def semantic(self):
        return _resolve("vehicle", "delivery_drone")

    @pytest.fixture(scope="class")
    def schema(self, semantic):
        return _factory.build(semantic)

    @pytest.fixture(scope="class")
    def payload(self, semantic):
        return _build_payload(semantic, self.TRACE)

    # --- domain ---
    def test_domain_is_vehicle(self, semantic):
        assert semantic["domain"] == "vehicle"

    # --- entity ---
    def test_entity_is_drone(self, semantic):
        assert semantic["entity"] == "drone"

    # --- geometry_family ---
    def test_geometry_family_is_rotorcraft(self, semantic):
        assert semantic["geometry_family"] == "rotorcraft"

    # --- executionSchema ---
    def test_schema_type_is_mesh(self, schema):
        assert schema["schema_type"] == "mesh"

    def test_schema_domain_is_vehicle(self, schema):
        assert schema["domain"] == "vehicle"

    def test_schema_generator_is_mesh_generator(self, schema):
        assert schema["generator"] == "mesh_generator"

    def test_schema_generation_mode_is_mesh(self, schema):
        assert schema["generation_mode"] == "mesh"

    def test_schema_has_mesh_config(self, schema):
        assert "mesh_config" in schema

    def test_schema_version_present(self, schema):
        assert schema.get("schema_version") == "1.0"

    # --- TTG payload ---
    def test_payload_trace_preserved(self, payload):
        assert payload["trace_id"] == self.TRACE

    def test_payload_execution_id_set(self, payload):
        assert payload["execution_id"] == f"exec_{self.TRACE}"

    def test_payload_bucket_urls_preserved(self, payload):
        assert _BUCKET_URL in payload["bucket_urls"]

    # --- contamination guards ---
    def test_no_apartment_layout_in_vehicle_schema(self, payload):
        assert "apartment_layout" not in _schema_text(
            payload
        ), "CONTAMINATION: vehicle schema contains 'apartment_layout' (architecture term)"

    def test_no_room_in_vehicle_schema(self, payload):
        assert '"room"' not in _schema_text(
            payload
        ), "CONTAMINATION: vehicle schema contains 'room' (architecture term)"

    def test_no_bedroom_in_vehicle_schema(self, payload):
        assert "bedroom" not in _schema_text(
            payload
        ), "CONTAMINATION: vehicle schema contains 'bedroom' (architecture term)"

    def test_no_kitchen_in_vehicle_schema(self, payload):
        assert "kitchen" not in _schema_text(
            payload
        ), "CONTAMINATION: vehicle schema contains 'kitchen' (architecture term)"

    def test_no_layout_generator_in_vehicle_schema(self, payload):
        schema = payload["executionSchema"]
        assert (
            schema.get("generator") != "layout_generator"
        ), "CONTAMINATION: vehicle schema uses layout_generator (architecture generator)"


# ---------------------------------------------------------------------------
# Scenario 3 — Generate checkpoint barrier → gameplay
# ---------------------------------------------------------------------------


class TestScenario3_CheckpointBarrier:
    """Generate checkpoint barrier → expected domain=gameplay"""

    TRACE = "qa-trace-scenario-3"

    @pytest.fixture(scope="class")
    def semantic(self):
        return _resolve("gameplay", "checkpoint_barrier")

    @pytest.fixture(scope="class")
    def schema(self, semantic):
        return _factory.build(semantic)

    @pytest.fixture(scope="class")
    def payload(self, semantic):
        return _build_payload(semantic, self.TRACE)

    # --- domain ---
    def test_domain_is_gameplay(self, semantic):
        assert semantic["domain"] == "gameplay"

    # --- entity ---
    def test_entity_is_checkpoint_or_obstacle(self, semantic):
        # "barrier" maps to obstacle; "checkpoint" maps to checkpoint
        assert semantic["entity"] in ("checkpoint", "obstacle")

    # --- geometry_family ---
    def test_geometry_family_is_gameplay_family(self, semantic):
        assert semantic["geometry_family"] in ("logic_marker", "gameplay_prop")

    # --- executionSchema ---
    def test_schema_type_is_gameplay(self, schema):
        assert schema["schema_type"] == "gameplay"

    def test_schema_domain_is_gameplay(self, schema):
        assert schema["domain"] == "gameplay"

    def test_schema_generator_is_mixed_generator(self, schema):
        assert schema["generator"] == "mixed_generator"

    def test_schema_has_gameplay_config(self, schema):
        assert "gameplay_config" in schema

    def test_schema_intent_compile_bypassed(self, schema):
        assert (
            schema.get("intent_compile_bypassed") is True
        ), "/api/intent/compile must never be called — intent_compile_bypassed must be True"

    def test_schema_version_present(self, schema):
        assert schema.get("schema_version") == "1.0"

    # --- TTG payload ---
    def test_payload_trace_preserved(self, payload):
        assert payload["trace_id"] == self.TRACE

    def test_payload_bucket_urls_preserved(self, payload):
        assert _BUCKET_URL in payload["bucket_urls"]

    # --- contamination guards ---
    def test_no_apartment_layout_in_gameplay_schema(self, payload):
        assert "apartment_layout" not in _schema_text(
            payload
        ), "CONTAMINATION: gameplay schema contains 'apartment_layout'"

    def test_no_kitchen_in_gameplay_schema(self, payload):
        assert "kitchen" not in _schema_text(payload), "CONTAMINATION: gameplay schema contains 'kitchen'"

    def test_no_vehicle_domain_in_gameplay_schema(self, payload):
        schema = payload["executionSchema"]
        assert schema.get("domain") != "vehicle"

    def test_no_layout_generator_in_gameplay_schema(self, payload):
        schema = payload["executionSchema"]
        assert schema.get("generator") != "layout_generator"


# ---------------------------------------------------------------------------
# Scenario 4 — Generate industrial zone → environment
# ---------------------------------------------------------------------------


class TestScenario4_IndustrialZone:
    """Generate industrial zone → expected domain=environment"""

    TRACE = "qa-trace-scenario-4"

    @pytest.fixture(scope="class")
    def semantic(self):
        return _resolve("environment", "industrial_zone")

    @pytest.fixture(scope="class")
    def schema(self, semantic):
        return _factory.build(semantic)

    @pytest.fixture(scope="class")
    def payload(self, semantic):
        return _build_payload(semantic, self.TRACE)

    # --- domain ---
    def test_domain_is_environment(self, semantic):
        assert semantic["domain"] == "environment"

    # --- entity ---
    def test_entity_is_industrial_zone(self, semantic):
        assert semantic["entity"] == "industrial_zone"

    # --- geometry_family ---
    def test_geometry_family_is_industrial_zone(self, semantic):
        assert semantic["geometry_family"] == "industrial_zone"

    # --- executionSchema ---
    def test_schema_type_is_zone(self, schema):
        assert schema["schema_type"] == "zone"

    def test_schema_domain_is_environment(self, schema):
        assert schema["domain"] == "environment"

    def test_schema_generator_is_grouped_geometry(self, schema):
        assert schema["generator"] == "grouped_geometry_generator"

    def test_schema_generation_mode_is_grouped_geometry(self, schema):
        assert schema["generation_mode"] == "grouped_geometry"

    def test_schema_has_zone_config(self, schema):
        assert "zone_config" in schema

    def test_schema_version_present(self, schema):
        assert schema.get("schema_version") == "1.0"

    # --- TTG payload ---
    def test_payload_trace_preserved(self, payload):
        assert payload["trace_id"] == self.TRACE

    def test_payload_bucket_urls_preserved(self, payload):
        assert _BUCKET_URL in payload["bucket_urls"]

    # --- contamination guards ---
    def test_no_bedroom_in_environment_schema(self, payload):
        assert "bedroom" not in _schema_text(
            payload
        ), "CONTAMINATION: environment schema contains 'bedroom' (architecture term)"

    def test_no_vehicle_engine_in_environment_schema(self, payload):
        assert "vehicle_engine" not in _schema_text(
            payload
        ), "CONTAMINATION: environment schema contains 'vehicle_engine'"

    def test_no_layout_generator_in_environment_schema(self, payload):
        schema = payload["executionSchema"]
        assert schema.get("generator") != "layout_generator"

    def test_no_architecture_domain_in_environment_schema(self, payload):
        schema = payload["executionSchema"]
        assert schema.get("domain") != "architecture"


# ---------------------------------------------------------------------------
# Scenario 5 — Generate combat arena → gameplay
# ---------------------------------------------------------------------------


class TestScenario5_CombatArena:
    """Generate combat arena → expected domain=gameplay"""

    TRACE = "qa-trace-scenario-5"

    @pytest.fixture(scope="class")
    def semantic(self):
        return _resolve("gameplay", "combat_arena")

    @pytest.fixture(scope="class")
    def schema(self, semantic):
        return _factory.build(semantic)

    @pytest.fixture(scope="class")
    def payload(self, semantic):
        return _build_payload(semantic, self.TRACE)

    # --- domain ---
    def test_domain_is_gameplay(self, semantic):
        assert semantic["domain"] == "gameplay"

    # --- entity ---
    def test_entity_is_gameplay_entity(self, semantic):
        valid = {"spawn_point", "obstacle", "checkpoint", "collectible", "interactable"}
        assert semantic["entity"] in valid

    # --- geometry_family ---
    def test_geometry_family_is_gameplay_family(self, semantic):
        assert semantic["geometry_family"] in ("logic_marker", "gameplay_prop")

    # --- executionSchema ---
    def test_schema_type_is_gameplay(self, schema):
        assert schema["schema_type"] == "gameplay"

    def test_schema_domain_is_gameplay(self, schema):
        assert schema["domain"] == "gameplay"

    def test_schema_generator_is_mixed_generator(self, schema):
        assert schema["generator"] == "mixed_generator"

    def test_schema_intent_compile_bypassed(self, schema):
        assert schema.get("intent_compile_bypassed") is True

    def test_schema_has_gameplay_config(self, schema):
        assert "gameplay_config" in schema

    def test_schema_version_present(self, schema):
        assert schema.get("schema_version") == "1.0"

    # --- TTG payload ---
    def test_payload_trace_preserved(self, payload):
        assert payload["trace_id"] == self.TRACE

    def test_payload_execution_schema_present(self, payload):
        assert payload["executionSchema"]

    def test_payload_bucket_urls_preserved(self, payload):
        assert _BUCKET_URL in payload["bucket_urls"]

    # --- contamination guards ---
    def test_no_apartment_layout_in_combat_arena_schema(self, payload):
        assert "apartment_layout" not in _schema_text(
            payload
        ), "CONTAMINATION: gameplay/combat_arena schema contains 'apartment_layout'"

    def test_no_bedroom_in_combat_arena_schema(self, payload):
        assert "bedroom" not in _schema_text(payload), "CONTAMINATION: gameplay/combat_arena schema contains 'bedroom'"

    def test_no_rotor_in_combat_arena_schema(self, payload):
        assert "rotor" not in _schema_text(payload), "CONTAMINATION: gameplay/combat_arena schema contains 'rotor'"

    def test_no_architecture_domain_in_gameplay(self, payload):
        schema = payload["executionSchema"]
        assert schema.get("domain") != "architecture"


# ---------------------------------------------------------------------------
# Cross-scenario contamination matrix
# ---------------------------------------------------------------------------


class TestCrossScenarioContamination:
    """
    Explicit cross-domain contamination checks required by the sprint.

    Rule 1: vehicle domain CANNOT contain apartment geometry
    Rule 2: architecture domain CANNOT contain rotor geometry
    Rule 3: environment domain CANNOT contain bedroom geometry
    """

    def test_vehicle_schema_has_no_apartment_geometry(self):
        semantic = _resolve("vehicle", "drone")
        schema = _factory.build(semantic)
        text = json.dumps(schema).lower()
        assert "apartment" not in text, "FAIL Rule 1: vehicle schema contains apartment geometry"
        assert "apartment_layout" not in text, "FAIL Rule 1: vehicle schema contains apartment_layout"

    def test_vehicle_schema_has_no_layout_generator(self):
        semantic = _resolve("vehicle", "truck")
        schema = _factory.build(semantic)
        assert (
            schema["generator"] != "layout_generator"
        ), "FAIL Rule 1: vehicle schema uses layout_generator (architecture generator)"

    def test_vehicle_schema_geometry_family_is_vehicle_family(self):
        vehicle_families = {
            "rotorcraft",
            "wheeled_vehicle",
            "marine_vessel",
            "aerospace_vehicle",
            "tracked_vehicle",
        }
        for topic in ("drone", "truck", "rover", "ship", "spacecraft"):
            semantic = _resolve("vehicle", topic)
            assert (
                semantic["geometry_family"] in vehicle_families
            ), f"FAIL Rule 1: vehicle/{topic} geometry_family={semantic['geometry_family']} not in vehicle families"

    def test_architecture_schema_has_no_rotor_geometry(self):
        semantic = _resolve("architecture", "2bhk_apartment")
        schema = _factory.build(semantic)
        text = json.dumps(schema).lower()
        assert "rotor" not in text, "FAIL Rule 2: architecture schema contains 'rotor'"
        assert "rotorcraft" not in text, "FAIL Rule 2: architecture schema contains 'rotorcraft'"

    def test_architecture_schema_has_no_vehicle_terms(self):
        semantic = _resolve("architecture", "villa")
        schema = _factory.build(semantic)
        text = json.dumps(schema).lower()
        for term in ("thruster", "wing", "vehicle_engine", "mesh_generator"):
            assert term not in text, f"FAIL Rule 2: architecture schema contains vehicle term '{term}'"

    def test_architecture_schema_geometry_family_is_architecture_family(self):
        arch_families = {
            "apartment_layout",
            "residential_compound",
            "commercial_floor_plan",
            "industrial_floor_plan",
        }
        for topic in ("1bhk", "2bhk", "villa", "office", "warehouse"):
            semantic = _resolve("architecture", topic)
            assert (
                semantic["geometry_family"] in arch_families
            ), f"FAIL Rule 2: architecture/{topic} geometry_family={semantic['geometry_family']} not in arch families"

    def test_environment_schema_has_no_bedroom_geometry(self):
        semantic = _resolve("environment", "industrial_zone")
        schema = _factory.build(semantic)
        text = json.dumps(schema).lower()
        assert "bedroom" not in text, "FAIL Rule 3: environment schema contains 'bedroom'"

    def test_environment_schema_has_no_architecture_terms(self):
        semantic = _resolve("environment", "forest")
        schema = _factory.build(semantic)
        text = json.dumps(schema).lower()
        for term in ("apartment_layout", "floor_plan", "layout_generator", "bedroom"):
            assert term not in text, f"FAIL Rule 3: environment schema contains architecture term '{term}'"

    def test_environment_schema_geometry_family_is_environment_family(self):
        env_families = {
            "vegetation_zone",
            "terrain_zone",
            "urban_zone",
            "industrial_zone",
            "aquatic_zone",
        }
        for topic in ("forest", "desert", "city_block", "industrial_zone", "ocean_zone"):
            semantic = _resolve("environment", topic)
            assert (
                semantic["geometry_family"] in env_families
            ), f"FAIL Rule 3: environment/{topic} geometry_family={semantic['geometry_family']} not in env families"


# ---------------------------------------------------------------------------
# Trace preservation across all 5 scenarios
# ---------------------------------------------------------------------------


class TestTracePreservation:
    """Verify trace_id flows through SemanticResolver → payload unchanged."""

    @pytest.mark.parametrize(
        "module,topic,trace_id",
        [
            ("architecture", "1BHK_apartment", "trace-scenario-1"),
            ("vehicle", "delivery_drone", "trace-scenario-2"),
            ("gameplay", "checkpoint_barrier", "trace-scenario-3"),
            ("environment", "industrial_zone", "trace-scenario-4"),
            ("gameplay", "combat_arena", "trace-scenario-5"),
        ],
    )
    def test_trace_id_preserved_in_payload(self, module, topic, trace_id):
        semantic = _resolve(module, topic)
        payload = _build_payload(semantic, trace_id)
        assert (
            payload["trace_id"] == trace_id
        ), f"Trace lost for {module}/{topic}: expected {trace_id}, got {payload['trace_id']}"

    @pytest.mark.parametrize(
        "module,topic,trace_id",
        [
            ("architecture", "1BHK_apartment", "trace-scenario-1"),
            ("vehicle", "delivery_drone", "trace-scenario-2"),
            ("gameplay", "checkpoint_barrier", "trace-scenario-3"),
            ("environment", "industrial_zone", "trace-scenario-4"),
            ("gameplay", "combat_arena", "trace-scenario-5"),
        ],
    )
    def test_execution_id_present_in_payload(self, module, topic, trace_id):
        semantic = _resolve(module, topic)
        payload = _build_payload(semantic, trace_id)
        assert payload["execution_id"], f"execution_id missing in payload for {module}/{topic}"

    @pytest.mark.parametrize(
        "module,topic,trace_id",
        [
            ("architecture", "1BHK_apartment", "trace-scenario-1"),
            ("vehicle", "delivery_drone", "trace-scenario-2"),
            ("gameplay", "checkpoint_barrier", "trace-scenario-3"),
            ("environment", "industrial_zone", "trace-scenario-4"),
            ("gameplay", "combat_arena", "trace-scenario-5"),
        ],
    )
    def test_execution_schema_domain_matches_resolved_domain(self, module, topic, trace_id):
        semantic = _resolve(module, topic)
        payload = _build_payload(semantic, trace_id)
        assert (
            payload["executionSchema"]["domain"] == semantic["domain"]
        ), f"Domain mismatch in executionSchema for {module}/{topic}"
