"""
Unit tests for ExecutionSchemaFactory.
Pure unit tests — no HTTP, no real filesystem needed for most tests
(entity_config uses real semantic_templates.json where available).
"""

import json
from unittest.mock import mock_open, patch

import pytest
from app.factories.execution_schema_factory import (
    _DOMAIN_GENERATOR,
    _DOMAIN_SCHEMA_TYPE,
    SCHEMA_VERSION,
    ExecutionSchemaError,
    ExecutionSchemaFactory,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


def sem(domain: str, entity: str, generation_mode: str, geometry_family: str) -> dict:
    return {
        "domain": domain,
        "entity": entity,
        "generation_mode": generation_mode,
        "geometry_family": geometry_family,
    }


VEHICLE_SEM = sem("vehicle", "drone", "mesh", "rotorcraft")
ARCH_SEM = sem("architecture", "2bhk", "layout", "apartment_layout")
OBJECT_SEM = sem("object", "crate", "mesh", "primitive_prop")
ENV_SEM = sem("environment", "forest", "grouped_geometry", "vegetation_zone")
GAMEPLAY_SEM = sem("gameplay", "obstacle", "mesh", "gameplay_prop")
TRIGGER_SEM = sem("gameplay", "spawn_point", "trigger_volume", "logic_marker")

ALL_DOMAINS = [
    ("vehicle", VEHICLE_SEM),
    ("architecture", ARCH_SEM),
    ("object", OBJECT_SEM),
    ("environment", ENV_SEM),
    ("gameplay", GAMEPLAY_SEM),
]


@pytest.fixture
def factory():
    return ExecutionSchemaFactory()


# ══════════════════════════════════════════════════════════════════════════════
# 1. build_vehicle_schema
# ══════════════════════════════════════════════════════════════════════════════


class TestBuildVehicleSchema:
    def test_schema_type_is_mesh(self, factory):
        assert factory.build_vehicle_schema(VEHICLE_SEM)["schema_type"] == "mesh"

    def test_domain_is_vehicle(self, factory):
        assert factory.build_vehicle_schema(VEHICLE_SEM)["domain"] == "vehicle"

    def test_entity_propagated(self, factory):
        assert factory.build_vehicle_schema(VEHICLE_SEM)["entity"] == "drone"

    def test_generation_mode_propagated(self, factory):
        assert factory.build_vehicle_schema(VEHICLE_SEM)["generation_mode"] == "mesh"

    def test_geometry_family_propagated(self, factory):
        assert factory.build_vehicle_schema(VEHICLE_SEM)["geometry_family"] == "rotorcraft"

    def test_generator_is_mesh_generator(self, factory):
        assert factory.build_vehicle_schema(VEHICLE_SEM)["generator"] == "mesh_generator"

    def test_schema_version_correct(self, factory):
        assert factory.build_vehicle_schema(VEHICLE_SEM)["schema_version"] == SCHEMA_VERSION

    def test_mesh_config_present(self, factory):
        assert "mesh_config" in factory.build_vehicle_schema(VEHICLE_SEM)

    def test_mesh_config_coordinate_system(self, factory):
        cfg = factory.build_vehicle_schema(VEHICLE_SEM)["mesh_config"]
        assert cfg["coordinate_system"] == "right_handed"

    def test_mesh_config_units_meters(self, factory):
        cfg = factory.build_vehicle_schema(VEHICLE_SEM)["mesh_config"]
        assert cfg["units"] == "meters"

    def test_mesh_config_lod_levels(self, factory):
        cfg = factory.build_vehicle_schema(VEHICLE_SEM)["mesh_config"]
        assert cfg["lod_levels"] == 1

    def test_output_formats_present(self, factory):
        formats = factory.build_vehicle_schema(VEHICLE_SEM)["output_formats"]
        assert "glb" in formats
        assert "stl" in formats
        assert "step" in formats

    def test_entity_config_present(self, factory):
        assert "entity_config" in factory.build_vehicle_schema(VEHICLE_SEM)

    def test_all_vehicle_geometry_families(self, factory):
        for gf in ("rotorcraft", "wheeled_vehicle", "marine_vessel", "aerospace_vehicle"):
            s = sem("vehicle", "rover", "mesh", gf)
            schema = factory.build_vehicle_schema(s)
            assert schema["geometry_family"] == gf


# ══════════════════════════════════════════════════════════════════════════════
# 2. build_architecture_schema
# ══════════════════════════════════════════════════════════════════════════════


class TestBuildArchitectureSchema:
    def test_schema_type_is_scene_layout(self, factory):
        assert factory.build_architecture_schema(ARCH_SEM)["schema_type"] == "scene/layout"

    def test_domain_is_architecture(self, factory):
        assert factory.build_architecture_schema(ARCH_SEM)["domain"] == "architecture"

    def test_generator_is_layout_generator(self, factory):
        assert factory.build_architecture_schema(ARCH_SEM)["generator"] == "layout_generator"

    def test_generation_mode_is_layout(self, factory):
        assert factory.build_architecture_schema(ARCH_SEM)["generation_mode"] == "layout"

    def test_layout_config_present(self, factory):
        assert "layout_config" in factory.build_architecture_schema(ARCH_SEM)

    def test_enforce_wall_thickness(self, factory):
        assert factory.build_architecture_schema(ARCH_SEM)["layout_config"]["enforce_wall_thickness"] is True

    def test_room_separation(self, factory):
        assert factory.build_architecture_schema(ARCH_SEM)["layout_config"]["room_separation"] is True

    def test_door_gaps(self, factory):
        assert factory.build_architecture_schema(ARCH_SEM)["layout_config"]["door_gaps"] is True

    def test_units_meters(self, factory):
        assert factory.build_architecture_schema(ARCH_SEM)["layout_config"]["units"] == "meters"

    def test_all_architecture_geometry_families(self, factory):
        for gf in ("apartment_layout", "residential_compound", "commercial_floor_plan", "industrial_floor_plan"):
            s = sem("architecture", "office", "layout", gf)
            schema = factory.build_architecture_schema(s)
            assert schema["geometry_family"] == gf


# ══════════════════════════════════════════════════════════════════════════════
# 3. build_object_schema
# ══════════════════════════════════════════════════════════════════════════════


class TestBuildObjectSchema:
    def test_schema_type_is_reusable_asset(self, factory):
        assert factory.build_object_schema(OBJECT_SEM)["schema_type"] == "reusable_asset"

    def test_domain_is_object(self, factory):
        assert factory.build_object_schema(OBJECT_SEM)["domain"] == "object"

    def test_generator_is_mesh_generator(self, factory):
        assert factory.build_object_schema(OBJECT_SEM)["generator"] == "mesh_generator"

    def test_asset_config_present(self, factory):
        assert "asset_config" in factory.build_object_schema(OBJECT_SEM)

    def test_asset_config_reusable_true(self, factory):
        assert factory.build_object_schema(OBJECT_SEM)["asset_config"]["reusable"] is True

    def test_asset_config_origin_centered(self, factory):
        assert factory.build_object_schema(OBJECT_SEM)["asset_config"]["origin_centered"] is True

    def test_asset_config_units(self, factory):
        assert factory.build_object_schema(OBJECT_SEM)["asset_config"]["units"] == "meters"

    def test_all_object_geometry_families(self, factory):
        for gf in ("primitive_prop", "structural_element"):
            s = sem("object", "box", "mesh", gf)
            schema = factory.build_object_schema(s)
            assert schema["geometry_family"] == gf


# ══════════════════════════════════════════════════════════════════════════════
# 4. build_environment_schema
# ══════════════════════════════════════════════════════════════════════════════


class TestBuildEnvironmentSchema:
    def test_schema_type_is_zone(self, factory):
        assert factory.build_environment_schema(ENV_SEM)["schema_type"] == "zone"

    def test_domain_is_environment(self, factory):
        assert factory.build_environment_schema(ENV_SEM)["domain"] == "environment"

    def test_generator_is_grouped_geometry(self, factory):
        assert factory.build_environment_schema(ENV_SEM)["generator"] == "grouped_geometry_generator"

    def test_generation_mode_is_grouped_geometry(self, factory):
        assert factory.build_environment_schema(ENV_SEM)["generation_mode"] == "grouped_geometry"

    def test_zone_config_present(self, factory):
        assert "zone_config" in factory.build_environment_schema(ENV_SEM)

    def test_instancing_enabled(self, factory):
        assert factory.build_environment_schema(ENV_SEM)["zone_config"]["instancing_enabled"] is True

    def test_lod_levels(self, factory):
        assert factory.build_environment_schema(ENV_SEM)["zone_config"]["lod_levels"] == 2

    def test_all_environment_geometry_families(self, factory):
        for gf in ("vegetation_zone", "terrain_zone", "urban_zone", "industrial_zone", "aquatic_zone"):
            s = sem("environment", "desert", "grouped_geometry", gf)
            schema = factory.build_environment_schema(s)
            assert schema["geometry_family"] == gf


# ══════════════════════════════════════════════════════════════════════════════
# 5. build_gameplay_schema
# ══════════════════════════════════════════════════════════════════════════════


class TestBuildGameplaySchema:
    def test_schema_type_is_gameplay(self, factory):
        assert factory.build_gameplay_schema(GAMEPLAY_SEM)["schema_type"] == "gameplay"

    def test_domain_is_gameplay(self, factory):
        assert factory.build_gameplay_schema(GAMEPLAY_SEM)["domain"] == "gameplay"

    def test_generator_is_mixed_generator(self, factory):
        assert factory.build_gameplay_schema(GAMEPLAY_SEM)["generator"] == "mixed_generator"

    def test_gameplay_config_present(self, factory):
        assert "gameplay_config" in factory.build_gameplay_schema(GAMEPLAY_SEM)

    def test_collision_enabled(self, factory):
        assert factory.build_gameplay_schema(GAMEPLAY_SEM)["gameplay_config"]["collision_enabled"] is True

    def test_trigger_zones_false_for_mesh_mode(self, factory):
        assert factory.build_gameplay_schema(GAMEPLAY_SEM)["gameplay_config"]["trigger_zones"] is False

    def test_trigger_zones_true_for_trigger_volume(self, factory):
        schema = factory.build_gameplay_schema(TRIGGER_SEM)
        assert schema["gameplay_config"]["trigger_zones"] is True

    def test_units_game_units(self, factory):
        assert factory.build_gameplay_schema(GAMEPLAY_SEM)["gameplay_config"]["units"] == "game_units"

    def test_intent_compile_bypassed_true(self, factory):
        # CRITICAL invariant: /api/intent/compile must never be called
        assert factory.build_gameplay_schema(GAMEPLAY_SEM)["intent_compile_bypassed"] is True

    def test_intent_compile_bypassed_also_true_for_trigger_volume(self, factory):
        assert factory.build_gameplay_schema(TRIGGER_SEM)["intent_compile_bypassed"] is True


# ══════════════════════════════════════════════════════════════════════════════
# 6. build() dispatch method
# ══════════════════════════════════════════════════════════════════════════════


class TestBuildDispatch:
    @pytest.mark.parametrize("domain,semantic", ALL_DOMAINS)
    def test_dispatch_returns_correct_schema_type(self, factory, domain, semantic):
        schema = factory.build(semantic)
        assert schema["schema_type"] == _DOMAIN_SCHEMA_TYPE[domain]

    @pytest.mark.parametrize("domain,semantic", ALL_DOMAINS)
    def test_dispatch_returns_correct_generator(self, factory, domain, semantic):
        schema = factory.build(semantic)
        assert schema["generator"] == _DOMAIN_GENERATOR[domain]

    @pytest.mark.parametrize("domain,semantic", ALL_DOMAINS)
    def test_dispatch_domain_field_correct(self, factory, domain, semantic):
        schema = factory.build(semantic)
        assert schema["domain"] == domain

    def test_build_unknown_domain_raises(self, factory):
        with pytest.raises(ExecutionSchemaError) as exc_info:
            factory.build(sem("spaceship", "rocket", "mesh", "rotorcraft"))
        assert exc_info.value.error_code == "SCHEMA_UNKNOWN_DOMAIN"


# ══════════════════════════════════════════════════════════════════════════════
# 7. from_domain() method
# ══════════════════════════════════════════════════════════════════════════════


class TestFromDomain:
    def test_architecture_returns_callable(self, factory):
        assert callable(factory.from_domain("architecture"))

    def test_vehicle_returns_build_vehicle_schema(self, factory):
        assert factory.from_domain("vehicle") == factory.build_vehicle_schema

    def test_architecture_returns_build_architecture_schema(self, factory):
        assert factory.from_domain("architecture") == factory.build_architecture_schema

    def test_object_returns_build_object_schema(self, factory):
        assert factory.from_domain("object") == factory.build_object_schema

    def test_environment_returns_build_environment_schema(self, factory):
        assert factory.from_domain("environment") == factory.build_environment_schema

    def test_gameplay_returns_build_gameplay_schema(self, factory):
        assert factory.from_domain("gameplay") == factory.build_gameplay_schema

    def test_unknown_domain_raises(self, factory):
        with pytest.raises(ExecutionSchemaError) as exc_info:
            factory.from_domain("unknown_xyz")
        assert exc_info.value.error_code == "SCHEMA_UNKNOWN_DOMAIN"

    def test_returned_callable_produces_valid_schema(self, factory):
        method = factory.from_domain("vehicle")
        schema = method(VEHICLE_SEM)
        assert schema["domain"] == "vehicle"
        assert schema["schema_type"] == "mesh"


# ══════════════════════════════════════════════════════════════════════════════
# 8. Validation — fail-closed
# ══════════════════════════════════════════════════════════════════════════════


class TestValidationFailClosed:
    @pytest.mark.parametrize("missing_key", ["domain", "entity", "generation_mode", "geometry_family"])
    def test_missing_key_raises(self, factory, missing_key):
        bad = {k: v for k, v in VEHICLE_SEM.items() if k != missing_key}
        with pytest.raises(ExecutionSchemaError) as exc_info:
            factory.build(bad)
        assert exc_info.value.error_code == "SCHEMA_MISSING_KEY"

    @pytest.mark.parametrize("missing_key", ["domain", "entity", "generation_mode", "geometry_family"])
    def test_empty_value_raises(self, factory, missing_key):
        bad = {**VEHICLE_SEM, missing_key: ""}
        with pytest.raises(ExecutionSchemaError) as exc_info:
            factory.build(bad)
        assert exc_info.value.error_code in ("SCHEMA_MISSING_KEY", "SCHEMA_UNKNOWN_DOMAIN")

    def test_unknown_domain_raises_on_direct_method(self, factory):
        bad = {**VEHICLE_SEM, "domain": "fantasy"}
        with pytest.raises(ExecutionSchemaError) as exc_info:
            factory.build_vehicle_schema(bad)
        assert exc_info.value.error_code == "SCHEMA_UNKNOWN_DOMAIN"


# ══════════════════════════════════════════════════════════════════════════════
# 9. Entity config enrichment
# ══════════════════════════════════════════════════════════════════════════════


class TestEntityConfigEnrichment:
    def test_entity_config_block_present_for_known_entity(self, factory):
        schema = factory.build_vehicle_schema(VEHICLE_SEM)
        # entity_config should be a dict (may be empty if templates not loaded)
        assert isinstance(schema["entity_config"], dict)

    def test_entity_config_empty_for_unknown_entity(self, factory):
        s = sem("vehicle", "unknown_entity_xyz", "mesh", "rotorcraft")
        schema = factory.build_vehicle_schema(s)
        assert schema["entity_config"] == {}

    def test_entity_config_does_not_override_schema_type(self, factory):
        # entity_config is injected as a separate key, not merged into root
        schema = factory.build_vehicle_schema(VEHICLE_SEM)
        assert schema["schema_type"] == "mesh"
        assert "schema_type" not in schema.get("entity_config", {})

    def test_no_templates_file_still_builds_schema(self):
        # Factory with no templates file should still work
        factory = ExecutionSchemaFactory.__new__(ExecutionSchemaFactory)
        factory._templates = {}
        schema = factory.build_vehicle_schema(VEHICLE_SEM)
        assert schema["schema_type"] == "mesh"
        assert schema["entity_config"] == {}


# ══════════════════════════════════════════════════════════════════════════════
# 10. Schema version and serialisability
# ══════════════════════════════════════════════════════════════════════════════


class TestSchemaVersionAndSerialisation:
    @pytest.mark.parametrize("domain,semantic", ALL_DOMAINS)
    def test_schema_version_is_present(self, factory, domain, semantic):
        schema = factory.build(semantic)
        assert schema["schema_version"] == SCHEMA_VERSION

    @pytest.mark.parametrize("domain,semantic", ALL_DOMAINS)
    def test_schema_is_json_serialisable(self, factory, domain, semantic):
        schema = factory.build(semantic)
        dumped = json.dumps(schema)
        assert isinstance(dumped, str)

    @pytest.mark.parametrize("domain,semantic", ALL_DOMAINS)
    def test_entity_config_in_every_schema(self, factory, domain, semantic):
        schema = factory.build(semantic)
        assert "entity_config" in schema


# ══════════════════════════════════════════════════════════════════════════════
# 11. Exception hierarchy
# ══════════════════════════════════════════════════════════════════════════════


class TestExceptionHierarchy:
    def test_execution_schema_error_is_exception(self):
        assert issubclass(ExecutionSchemaError, Exception)

    def test_error_stores_code(self):
        err = ExecutionSchemaError("test", error_code="SCHEMA_TEST")
        assert err.error_code == "SCHEMA_TEST"

    def test_default_error_code(self):
        err = ExecutionSchemaError("test")
        assert err.error_code == "SCHEMA_ERROR"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
