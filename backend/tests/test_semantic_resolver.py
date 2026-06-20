"""
Unit tests for SemanticResolver
================================
Run with: pytest backend/tests/test_semantic_resolver.py -v
"""

import pytest
from app.design_semantics.semantic_resolver import SemanticResolutionError, SemanticResolver

# ── Fixture ───────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def resolver():
    return SemanticResolver()


# ── Helper ────────────────────────────────────────────────────────────────────


def r(module, topic, intent="", tasks=None):
    return {
        "module": module,
        "topic": topic,
        "intent": intent,
        "tasks": tasks or [],
    }


# ── Architecture domain ───────────────────────────────────────────────────────


class TestArchitecture:
    def test_2bhk_apartment(self, resolver):
        result = resolver.resolve(r("architecture", "2BHK_apartment"))
        assert result == {
            "domain": "architecture",
            "entity": "2bhk",
            "generation_mode": "layout",
            "geometry_family": "apartment_layout",
        }

    def test_1bhk(self, resolver):
        result = resolver.resolve(r("architecture", "1BHK"))
        assert result["domain"] == "architecture"
        assert result["entity"] == "1bhk"
        assert result["generation_mode"] == "layout"

    def test_villa(self, resolver):
        result = resolver.resolve(r("architecture", "villa"))
        assert result["entity"] == "villa"
        assert result["geometry_family"] == "residential_compound"

    def test_bungalow_maps_to_villa(self, resolver):
        result = resolver.resolve(r("architecture", "bungalow"))
        assert result["entity"] == "villa"

    def test_office(self, resolver):
        result = resolver.resolve(r("architecture", "office_building"))
        assert result["entity"] == "office"
        assert result["geometry_family"] == "commercial_floor_plan"

    def test_warehouse(self, resolver):
        result = resolver.resolve(r("architecture", "warehouse"))
        assert result["entity"] == "warehouse"
        assert result["geometry_family"] == "industrial_floor_plan"

    def test_flat_maps_to_2bhk(self, resolver):
        result = resolver.resolve(r("architecture", "flat"))
        assert result["entity"] == "2bhk"

    def test_godown_maps_to_warehouse(self, resolver):
        result = resolver.resolve(r("architecture", "godown"))
        assert result["entity"] == "warehouse"

    def test_module_arch_alias(self, resolver):
        result = resolver.resolve(r("arch", "2bhk"))
        assert result["domain"] == "architecture"


# ── Vehicle domain ────────────────────────────────────────────────────────────


class TestVehicle:
    def test_combat_drone(self, resolver):
        result = resolver.resolve(r("vehicle", "combat_drone"))
        assert result == {
            "domain": "vehicle",
            "entity": "drone",
            "generation_mode": "mesh",
            "geometry_family": "rotorcraft",
        }

    def test_drone(self, resolver):
        result = resolver.resolve(r("vehicle", "drone"))
        assert result["entity"] == "drone"
        assert result["geometry_family"] == "rotorcraft"

    def test_uav_maps_to_drone(self, resolver):
        result = resolver.resolve(r("vehicle", "uav"))
        assert result["entity"] == "drone"

    def test_quadcopter_maps_to_drone(self, resolver):
        result = resolver.resolve(r("vehicles", "quadcopter"))
        assert result["domain"] == "vehicle"
        assert result["entity"] == "drone"

    def test_rover(self, resolver):
        result = resolver.resolve(r("vehicle", "rover"))
        assert result["entity"] == "rover"
        assert result["geometry_family"] == "wheeled_vehicle"

    def test_truck(self, resolver):
        result = resolver.resolve(r("vehicle", "truck"))
        assert result["entity"] == "truck"
        assert result["geometry_family"] == "wheeled_vehicle"

    def test_lorry_maps_to_truck(self, resolver):
        result = resolver.resolve(r("vehicle", "lorry"))
        assert result["entity"] == "truck"

    def test_ship(self, resolver):
        result = resolver.resolve(r("vehicle", "ship"))
        assert result["entity"] == "ship"
        assert result["geometry_family"] == "marine_vessel"

    def test_spacecraft(self, resolver):
        result = resolver.resolve(r("vehicle", "spacecraft"))
        assert result["entity"] == "spacecraft"
        assert result["geometry_family"] == "aerospace_vehicle"

    def test_rocket_maps_to_spacecraft(self, resolver):
        result = resolver.resolve(r("vehicle", "rocket"))
        assert result["entity"] == "spacecraft"


# ── Object domain ─────────────────────────────────────────────────────────────


class TestObject:
    def test_box(self, resolver):
        result = resolver.resolve(r("object", "box"))
        assert result["entity"] == "box"
        assert result["geometry_family"] == "primitive_prop"
        assert result["generation_mode"] == "mesh"

    def test_crate(self, resolver):
        result = resolver.resolve(r("objects", "crate"))
        assert result["domain"] == "object"
        assert result["entity"] == "crate"

    def test_barrel(self, resolver):
        result = resolver.resolve(r("object", "barrel"))
        assert result["entity"] == "barrel"

    def test_wall(self, resolver):
        result = resolver.resolve(r("object", "wall"))
        assert result["entity"] == "wall"
        assert result["geometry_family"] == "structural_element"

    def test_door(self, resolver):
        result = resolver.resolve(r("object", "door"))
        assert result["entity"] == "door"

    def test_staircase(self, resolver):
        result = resolver.resolve(r("object", "staircase"))
        assert result["entity"] == "staircase"

    def test_stairs_alias(self, resolver):
        result = resolver.resolve(r("object", "stairs"))
        assert result["entity"] == "staircase"


# ── Gameplay domain ───────────────────────────────────────────────────────────


class TestGameplay:
    def test_spawn_point(self, resolver):
        result = resolver.resolve(r("gameplay", "spawn_point"))
        assert result["entity"] == "spawn_point"
        assert result["generation_mode"] == "trigger_volume"
        assert result["geometry_family"] == "logic_marker"

    def test_spawn_alias(self, resolver):
        result = resolver.resolve(r("gameplay", "spawn"))
        assert result["entity"] == "spawn_point"

    def test_checkpoint(self, resolver):
        result = resolver.resolve(r("gameplay", "checkpoint"))
        assert result["entity"] == "checkpoint"
        assert result["geometry_family"] == "logic_marker"

    def test_waypoint_maps_to_checkpoint(self, resolver):
        result = resolver.resolve(r("gameplay", "waypoint"))
        assert result["entity"] == "checkpoint"

    def test_obstacle(self, resolver):
        result = resolver.resolve(r("gameplay", "obstacle"))
        assert result["entity"] == "obstacle"
        assert result["geometry_family"] == "gameplay_prop"

    def test_collectible(self, resolver):
        result = resolver.resolve(r("gameplay", "collectible"))
        assert result["entity"] == "collectible"

    def test_coin_maps_to_collectible(self, resolver):
        result = resolver.resolve(r("gameplay", "coin"))
        assert result["entity"] == "collectible"

    def test_interactable(self, resolver):
        result = resolver.resolve(r("gameplay", "interactable"))
        assert result["entity"] == "interactable"

    def test_lever_maps_to_interactable(self, resolver):
        result = resolver.resolve(r("game", "lever"))
        assert result["entity"] == "interactable"


# ── Environment domain ────────────────────────────────────────────────────────


class TestEnvironment:
    def test_forest(self, resolver):
        result = resolver.resolve(r("environment", "forest"))
        assert result["entity"] == "forest"
        assert result["generation_mode"] == "grouped_geometry"
        assert result["geometry_family"] == "vegetation_zone"

    def test_jungle_maps_to_forest(self, resolver):
        result = resolver.resolve(r("environment", "jungle"))
        assert result["entity"] == "forest"

    def test_desert(self, resolver):
        result = resolver.resolve(r("environment", "desert"))
        assert result["entity"] == "desert"
        assert result["geometry_family"] == "terrain_zone"

    def test_city_block(self, resolver):
        result = resolver.resolve(r("environment", "city_block"))
        assert result["entity"] == "city_block"
        assert result["geometry_family"] == "urban_zone"

    def test_urban_maps_to_city_block(self, resolver):
        result = resolver.resolve(r("environment", "urban_scene"))
        assert result["entity"] == "city_block"

    def test_industrial_zone(self, resolver):
        result = resolver.resolve(r("environment", "industrial_zone"))
        assert result["entity"] == "industrial_zone"

    def test_factory_maps_to_industrial_zone(self, resolver):
        result = resolver.resolve(r("environment", "factory_area"))
        assert result["entity"] == "industrial_zone"

    def test_ocean_zone(self, resolver):
        result = resolver.resolve(r("environment", "ocean_zone"))
        assert result["entity"] == "ocean_zone"
        assert result["geometry_family"] == "aquatic_zone"

    def test_sea_maps_to_ocean_zone(self, resolver):
        result = resolver.resolve(r("terrain", "sea_floor"))
        assert result["entity"] == "ocean_zone"


# ── Output schema ─────────────────────────────────────────────────────────────


class TestOutputSchema:
    def test_all_required_keys_present(self, resolver):
        result = resolver.resolve(r("vehicle", "drone"))
        assert set(result.keys()) == {"domain", "entity", "generation_mode", "geometry_family"}

    def test_all_values_are_strings(self, resolver):
        result = resolver.resolve(r("architecture", "villa"))
        for k, v in result.items():
            assert isinstance(v, str), f"Key {k!r} should be str, got {type(v)}"

    def test_domain_matches_template(self, resolver):
        result = resolver.resolve(r("vehicle", "truck"))
        assert result["domain"] == "vehicle"


# ── Error cases ───────────────────────────────────────────────────────────────


class TestErrors:
    def test_unknown_module_and_topic_raises(self, resolver):
        with pytest.raises(SemanticResolutionError):
            resolver.resolve(r("xyzzy", "nonexistent_thing_xyz"))

    def test_empty_module_and_topic_raises(self, resolver):
        with pytest.raises(SemanticResolutionError):
            resolver.resolve(r("", ""))
