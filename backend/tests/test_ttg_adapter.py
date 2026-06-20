"""
Unit tests for TTGAdapter.
All tests are fully isolated — no real filesystem or network calls.
"""

import json
import unittest
from unittest.mock import mock_open, patch

from app.adapters.ttg_adapter import TTGAdapter, TTGValidationError
from app.contracts.core_execution_request import CoreExecutionRequest
from app.contracts.core_execution_response import CoreExecutionResponse

# ── Shared fixtures ────────────────────────────────────────────────────────────

CONSTRAINTS = {
    "domains": {
        "vehicle": {
            "allowed_geometry_families": ["rotorcraft", "wheeled_vehicle", "marine_vessel", "aerospace_vehicle"],
            "forbidden_terms": ["room", "bedroom", "kitchen", "living_room"],
            "forbidden_domains": ["architecture", "gameplay"],
            "supported_generation_modes": ["mesh"],
        },
        "architecture": {
            "allowed_geometry_families": [
                "apartment_layout",
                "residential_compound",
                "commercial_floor_plan",
                "industrial_floor_plan",
            ],
            "forbidden_terms": ["rotor", "wing", "engine", "thruster"],
            "forbidden_domains": ["vehicle", "gameplay", "environment"],
            "supported_generation_modes": ["layout"],
        },
        "environment": {
            "allowed_geometry_families": [
                "vegetation_zone",
                "terrain_zone",
                "urban_zone",
                "industrial_zone",
                "aquatic_zone",
            ],
            "forbidden_terms": ["bedroom", "vehicle_engine"],
            "forbidden_domains": ["architecture", "vehicle", "gameplay"],
            "supported_generation_modes": ["grouped_geometry"],
        },
        "gameplay": {
            "allowed_geometry_families": ["logic_marker", "gameplay_prop"],
            "forbidden_terms": ["apartment_layout", "kitchen"],
            "forbidden_domains": ["architecture", "vehicle", "environment"],
            "supported_generation_modes": ["mesh", "trigger_volume"],
        },
        "object": {
            "allowed_geometry_families": ["primitive_prop", "structural_element"],
            "forbidden_terms": ["room", "bedroom", "rotor", "engine", "spawn_point", "tree", "wave"],
            "forbidden_domains": ["architecture", "vehicle", "gameplay", "environment"],
            "supported_generation_modes": ["mesh"],
        },
    }
}


def make_adapter() -> TTGAdapter:
    """Return a TTGAdapter with constraints loaded from the fixture dict (no filesystem)."""
    adapter = TTGAdapter.__new__(TTGAdapter)
    adapter._constraints = CONSTRAINTS
    return adapter


def make_response(status: str = "success", agent_output: dict = None) -> CoreExecutionResponse:
    return CoreExecutionResponse(
        task_id="task_test001",
        trace_id="trace_test001",
        status=status,
        agent_output=agent_output or {"spec": {"type": "mesh"}},
    )


# ── route_to_generator ─────────────────────────────────────────────────────────


class TestRouteToGenerator(unittest.TestCase):
    def setUp(self):
        self.adapter = make_adapter()

    def test_architecture_routes_to_layout_generator(self):
        self.assertEqual(self.adapter.route_to_generator("architecture"), "layout_generator")

    def test_vehicle_routes_to_mesh_generator(self):
        self.assertEqual(self.adapter.route_to_generator("vehicle"), "mesh_generator")

    def test_object_routes_to_mesh_generator(self):
        self.assertEqual(self.adapter.route_to_generator("object"), "mesh_generator")

    def test_gameplay_routes_to_mixed_generator(self):
        self.assertEqual(self.adapter.route_to_generator("gameplay"), "mixed_generator")

    def test_environment_routes_to_grouped_geometry_generator(self):
        self.assertEqual(self.adapter.route_to_generator("environment"), "grouped_geometry_generator")

    def test_unknown_domain_raises_ttg_validation_error(self):
        with self.assertRaises(TTGValidationError) as ctx:
            self.adapter.route_to_generator("unknown_domain")
        self.assertEqual(ctx.exception.error_code, "TTG_UNKNOWN_DOMAIN")

    def test_empty_domain_raises_ttg_validation_error(self):
        with self.assertRaises(TTGValidationError):
            self.adapter.route_to_generator("")


# ── prepare_request ────────────────────────────────────────────────────────────


class TestPrepareRequest(unittest.TestCase):
    def setUp(self):
        self.adapter = make_adapter()
        self.vehicle_semantic = {
            "domain": "vehicle",
            "entity": "drone",
            "generation_mode": "mesh",
            "geometry_family": "rotorcraft",
        }
        self.arch_semantic = {
            "domain": "architecture",
            "entity": "2bhk",
            "generation_mode": "layout",
            "geometry_family": "apartment_layout",
        }

    def test_returns_core_execution_request(self):
        req = self.adapter.prepare_request(self.vehicle_semantic, "Build a drone", "trace_001")
        self.assertIsInstance(req, CoreExecutionRequest)

    def test_agent_set_to_correct_generator(self):
        req = self.adapter.prepare_request(self.vehicle_semantic, "Build a drone", "trace_001")
        self.assertEqual(req.agent, "mesh_generator")

    def test_architecture_agent_is_layout_generator(self):
        req = self.adapter.prepare_request(self.arch_semantic, "Design a flat", "trace_002")
        self.assertEqual(req.agent, "layout_generator")

    def test_prompt_stored_as_input(self):
        req = self.adapter.prepare_request(self.vehicle_semantic, "My prompt", "trace_003")
        self.assertEqual(req.input, "My prompt")

    def test_trace_id_propagated(self):
        req = self.adapter.prepare_request(self.vehicle_semantic, "prompt", "trace_xyz")
        self.assertEqual(req.trace_id, "trace_xyz")

    def test_custom_task_id_used_when_provided(self):
        req = self.adapter.prepare_request(self.vehicle_semantic, "prompt", "trace_001", task_id="task_custom")
        self.assertEqual(req.task_id, "task_custom")

    def test_task_id_auto_generated_when_none(self):
        req = self.adapter.prepare_request(self.vehicle_semantic, "prompt", "trace_001")
        self.assertIsNotNone(req.task_id)
        self.assertTrue(req.task_id.startswith("task_"))

    def test_tags_contain_domain_entity_mode(self):
        req = self.adapter.prepare_request(self.vehicle_semantic, "prompt", "trace_001")
        self.assertIn("vehicle", req.tags)
        self.assertIn("drone", req.tags)
        self.assertIn("mesh", req.tags)

    def test_custom_tags_override_defaults(self):
        req = self.adapter.prepare_request(self.vehicle_semantic, "prompt", "trace_001", tags=["custom_tag"])
        self.assertEqual(req.tags, ["custom_tag"])

    def test_retries_set_to_3(self):
        req = self.adapter.prepare_request(self.vehicle_semantic, "prompt", "trace_001")
        self.assertEqual(req.retries, 3)

    def test_contaminated_geometry_family_raises(self):
        bad_semantic = {
            "domain": "vehicle",
            "entity": "drone",
            "generation_mode": "mesh",
            "geometry_family": "apartment_layout",  # architecture family in vehicle domain
        }
        with self.assertRaises(TTGValidationError) as ctx:
            self.adapter.prepare_request(bad_semantic, "prompt", "trace_001")
        self.assertEqual(ctx.exception.error_code, "DOMAIN_CONTAMINATION")

    def test_contaminated_generation_mode_raises(self):
        bad_semantic = {
            "domain": "vehicle",
            "entity": "drone",
            "generation_mode": "layout",  # architecture mode in vehicle domain
            "geometry_family": "rotorcraft",
        }
        with self.assertRaises(TTGValidationError) as ctx:
            self.adapter.prepare_request(bad_semantic, "prompt", "trace_001")
        self.assertEqual(ctx.exception.error_code, "DOMAIN_CONTAMINATION")


# ── validate_output ────────────────────────────────────────────────────────────


class TestValidateOutput(unittest.TestCase):
    def setUp(self):
        self.adapter = make_adapter()

    def test_success_response_passes(self):
        response = make_response("success", {"spec": {"type": "mesh", "vertices": 1200}})
        self.adapter.validate_output(response, expected_domain="vehicle")  # no raise

    def test_pending_response_passes(self):
        response = make_response("pending", {"queue_position": 3})
        self.adapter.validate_output(response, expected_domain="environment")  # no raise

    def test_failed_response_raises(self):
        response = make_response("failed", {"error": "out of memory"})
        with self.assertRaises(TTGValidationError) as ctx:
            self.adapter.validate_output(response, expected_domain="vehicle")
        self.assertEqual(ctx.exception.error_code, "TTG_GENERATION_FAILED")

    def test_rejected_response_raises(self):
        response = make_response("rejected", {"error": "quota exceeded"})
        with self.assertRaises(TTGValidationError) as ctx:
            self.adapter.validate_output(response, expected_domain="vehicle")
        self.assertEqual(ctx.exception.error_code, "TTG_GENERATION_FAILED")

    def test_output_with_forbidden_term_raises(self):
        # vehicle domain output contains "bedroom" (forbidden)
        response = make_response("success", {"geometry": "bedroom_mesh"})
        with self.assertRaises(TTGValidationError) as ctx:
            self.adapter.validate_output(response, expected_domain="vehicle")
        self.assertEqual(ctx.exception.error_code, "DOMAIN_CONTAMINATION")

    def test_output_without_forbidden_term_passes(self):
        response = make_response("success", {"geometry": "rotor_hub", "vertices": 800})
        self.adapter.validate_output(response, expected_domain="vehicle")  # no raise

    def test_architecture_output_with_forbidden_term_raises(self):
        # architecture domain output contains "engine" (forbidden)
        response = make_response("success", {"notes": "engine_room_layout"})
        with self.assertRaises(TTGValidationError) as ctx:
            self.adapter.validate_output(response, expected_domain="architecture")
        self.assertEqual(ctx.exception.error_code, "DOMAIN_CONTAMINATION")

    def test_unknown_domain_in_output_check_passes_gracefully(self):
        response = make_response("success", {"data": "some_output"})
        self.adapter.validate_output(response, expected_domain="unknown_domain")  # no raise


# ── Constraint loading ─────────────────────────────────────────────────────────


class TestConstraintLoading(unittest.TestCase):
    def test_missing_constraints_file_results_in_empty_domains(self):
        adapter = TTGAdapter(constraints_path="/nonexistent/path/constraints.json")
        self.assertEqual(adapter._constraints, {"domains": {}})

    def test_constraints_loaded_from_file(self):
        constraints_str = json.dumps(CONSTRAINTS)
        m = mock_open(read_data=constraints_str)
        with patch("builtins.open", m):
            adapter = TTGAdapter(constraints_path="/fake/path.json")
        self.assertIn("vehicle", adapter._constraints["domains"])

    def test_no_constraints_means_no_contamination_raised(self):
        adapter = TTGAdapter.__new__(TTGAdapter)
        adapter._constraints = {"domains": {}}
        # Should not raise even with "bad" geometry family
        req = adapter.prepare_request(
            {"domain": "vehicle", "entity": "drone", "generation_mode": "mesh", "geometry_family": "apartment_layout"},
            "prompt",
            "trace_001",
        )
        self.assertIsInstance(req, CoreExecutionRequest)


# ── Integration: prepare → validate ───────────────────────────────────────────


class TestPrepareAndValidateIntegration(unittest.TestCase):
    def setUp(self):
        self.adapter = make_adapter()

    def test_vehicle_drone_full_flow(self):
        semantic = {"domain": "vehicle", "entity": "drone", "generation_mode": "mesh", "geometry_family": "rotorcraft"}
        req = self.adapter.prepare_request(semantic, "Build a combat drone", "trace_int_001")
        self.assertEqual(req.agent, "mesh_generator")

        response = CoreExecutionResponse.success(
            task_id=req.task_id,
            trace_id=req.trace_id,
            agent_output={"type": "rotorcraft", "vertices": 2400},
        )
        self.adapter.validate_output(response, expected_domain="vehicle")  # no raise

    def test_architecture_2bhk_full_flow(self):
        semantic = {
            "domain": "architecture",
            "entity": "2bhk",
            "generation_mode": "layout",
            "geometry_family": "apartment_layout",
        }
        req = self.adapter.prepare_request(semantic, "Design a 2BHK flat", "trace_int_002")
        self.assertEqual(req.agent, "layout_generator")

        response = CoreExecutionResponse.success(
            task_id=req.task_id,
            trace_id=req.trace_id,
            agent_output={"rooms": ["bedroom", "living_room", "kitchen"]},
        )
        # architecture domain: "bedroom" is NOT a forbidden term — only "rotor/wing/engine/thruster" are
        self.adapter.validate_output(response, expected_domain="architecture")  # no raise


if __name__ == "__main__":
    unittest.main()
