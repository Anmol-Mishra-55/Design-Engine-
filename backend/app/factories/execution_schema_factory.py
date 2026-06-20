"""
ExecutionSchemaFactory
======================
Generates TTG executionSchema objects accepted by POST /core/execute.

This is the dedicated schema authority for the Design Engine pipeline.
TTGPayloadBuilder delegates schema construction here.

Public methods (one per domain):
    build_architecture_schema(semantic_resolution) -> dict
    build_vehicle_schema(semantic_resolution)      -> dict
    build_object_schema(semantic_resolution)       -> dict
    build_environment_schema(semantic_resolution)  -> dict
    build_gameplay_schema(semantic_resolution)     -> dict

Plus:
    build(semantic_resolution)  -> dispatches to correct method by domain
    from_domain(domain)         -> returns the bound method for a given domain

Input:  semantic_resolution dict from SemanticResolver.resolve()
        { domain, entity, generation_mode, geometry_family }

Output: executionSchema dict accepted by TTG /core/execute

Fail-closed on unknown domain (raises ExecutionSchemaError).

Design notes:
  - Reads entity-level config from semantic_templates.json at construction
    time (one-time load, cached on self).
  - Uses pathlib.Path.resolve() — no os.path.join(__file__) (CWE-22 safe).
  - /api/intent/compile is NEVER called. SemanticResolver is the semantic
    authority for all 5 domains including gameplay.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ── Paths (CWE-22 safe) ───────────────────────────────────────────────────────

_TEMPLATES_PATH = Path(__file__).resolve().parent.parent / "design_semantics" / "semantic_templates.json"

# ── Constants ─────────────────────────────────────────────────────────────────

SCHEMA_VERSION = "1.0"

# Domain → schema_type (mirrors TTGPayloadBuilder — single source of truth here)
_DOMAIN_SCHEMA_TYPE: Dict[str, str] = {
    "architecture": "scene/layout",
    "vehicle": "mesh",
    "object": "reusable_asset",
    "environment": "zone",
    "gameplay": "gameplay",
}

_DOMAIN_GENERATOR: Dict[str, str] = {
    "architecture": "layout_generator",
    "vehicle": "mesh_generator",
    "object": "mesh_generator",
    "gameplay": "mixed_generator",
    "environment": "grouped_geometry_generator",
}

_DOMAIN_OUTPUT_FORMATS: Dict[str, List[str]] = {
    "architecture": ["glb", "stl", "step"],
    "vehicle": ["glb", "stl", "step"],
    "object": ["glb", "stl", "step"],
    "environment": ["glb", "stl", "step"],
    "gameplay": ["glb", "stl", "step"],
}

# Required keys in every semantic_resolution input
_REQUIRED_SEMANTIC_KEYS = ("domain", "entity", "generation_mode", "geometry_family")


# ── Exception ─────────────────────────────────────────────────────────────────


class ExecutionSchemaError(Exception):
    """Raised when schema construction fails — unknown domain or missing fields."""

    def __init__(self, message: str, error_code: str = "SCHEMA_ERROR") -> None:
        super().__init__(message)
        self.error_code = error_code


# ── Factory ───────────────────────────────────────────────────────────────────


class ExecutionSchemaFactory:
    """
    Generates TTG executionSchema dicts from SemanticResolver output.

    Stateless after construction (templates loaded once and cached).

    Usage::

        factory = ExecutionSchemaFactory()

        # Dispatch automatically by domain:
        schema = factory.build({
            "domain":          "vehicle",
            "entity":          "drone",
            "generation_mode": "mesh",
            "geometry_family": "rotorcraft",
        })

        # Or call the specific method directly:
        schema = factory.build_vehicle_schema({
            "domain":          "vehicle",
            "entity":          "drone",
            "generation_mode": "mesh",
            "geometry_family": "rotorcraft",
        })
    """

    def __init__(self, templates_path: Path = _TEMPLATES_PATH) -> None:
        self._templates: Dict[str, Dict[str, Any]] = self._load_templates(templates_path)

    # ── Dispatch ──────────────────────────────────────────────────────────────

    def build(self, semantic_resolution: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatch to the correct domain schema builder.

        Args:
            semantic_resolution: SemanticResolver output —
                                 {domain, entity, generation_mode, geometry_family}

        Returns:
            executionSchema dict for POST /core/execute

        Raises:
            ExecutionSchemaError: unknown domain or missing required keys.
        """
        self._validate(semantic_resolution)
        domain = semantic_resolution["domain"]
        return self.from_domain(domain)(semantic_resolution)

    def from_domain(self, domain: str) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
        """
        Return the bound build method for a given domain string.

        Raises:
            ExecutionSchemaError: if domain is unknown.
        """
        dispatch: Dict[str, Callable] = {
            "architecture": self.build_architecture_schema,
            "vehicle": self.build_vehicle_schema,
            "object": self.build_object_schema,
            "environment": self.build_environment_schema,
            "gameplay": self.build_gameplay_schema,
        }
        method = dispatch.get(domain)
        if method is None:
            raise ExecutionSchemaError(
                f"ExecutionSchemaFactory: unknown domain '{domain}'. "
                f"Valid domains: {sorted(dispatch)}. Failing closed.",
                error_code="SCHEMA_UNKNOWN_DOMAIN",
            )
        return method

    # ── Public schema builders ────────────────────────────────────────────────

    def build_architecture_schema(self, semantic_resolution: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a scene/layout executionSchema for architecture assets.

        Geometry families: apartment_layout | residential_compound |
                           commercial_floor_plan | industrial_floor_plan

        generation_mode: layout
        generator:       layout_generator
        """
        self._validate(semantic_resolution)
        s = semantic_resolution
        entity_cfg = self._entity_config(s["entity"])

        return {
            "schema_type": _DOMAIN_SCHEMA_TYPE["architecture"],  # "scene/layout"
            "schema_version": SCHEMA_VERSION,
            "domain": "architecture",
            "entity": s["entity"],
            "generation_mode": s["generation_mode"],
            "geometry_family": s["geometry_family"],
            "generator": _DOMAIN_GENERATOR["architecture"],
            "output_formats": entity_cfg.get("supported_outputs", _DOMAIN_OUTPUT_FORMATS["architecture"]),
            "layout_config": {
                "enforce_wall_thickness": True,
                "room_separation": True,
                "door_gaps": True,
                "units": "meters",
            },
            "entity_config": entity_cfg,
        }

    def build_vehicle_schema(self, semantic_resolution: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a mesh executionSchema for vehicle assets.

        Geometry families: rotorcraft | wheeled_vehicle | marine_vessel |
                           aerospace_vehicle | tracked_vehicle

        generation_mode: mesh
        generator:       mesh_generator
        """
        self._validate(semantic_resolution)
        s = semantic_resolution
        entity_cfg = self._entity_config(s["entity"])

        return {
            "schema_type": _DOMAIN_SCHEMA_TYPE["vehicle"],  # "mesh"
            "schema_version": SCHEMA_VERSION,
            "domain": "vehicle",
            "entity": s["entity"],
            "generation_mode": s["generation_mode"],
            "geometry_family": s["geometry_family"],
            "generator": _DOMAIN_GENERATOR["vehicle"],
            "output_formats": entity_cfg.get("supported_outputs", _DOMAIN_OUTPUT_FORMATS["vehicle"]),
            "mesh_config": {
                "coordinate_system": "right_handed",
                "units": "meters",
                "lod_levels": 1,
            },
            "entity_config": entity_cfg,
        }

    def build_object_schema(self, semantic_resolution: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a reusable_asset executionSchema for standalone object/prop assets.

        Geometry families: primitive_prop | structural_element

        generation_mode: mesh
        generator:       mesh_generator
        """
        self._validate(semantic_resolution)
        s = semantic_resolution
        entity_cfg = self._entity_config(s["entity"])

        return {
            "schema_type": _DOMAIN_SCHEMA_TYPE["object"],  # "reusable_asset"
            "schema_version": SCHEMA_VERSION,
            "domain": "object",
            "entity": s["entity"],
            "generation_mode": s["generation_mode"],
            "geometry_family": s["geometry_family"],
            "generator": _DOMAIN_GENERATOR["object"],
            "output_formats": entity_cfg.get("supported_outputs", _DOMAIN_OUTPUT_FORMATS["object"]),
            "asset_config": {
                "reusable": True,
                "origin_centered": True,
                "units": "meters",
            },
            "entity_config": entity_cfg,
        }

    def build_environment_schema(self, semantic_resolution: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a zone executionSchema for environment assets.

        Geometry families: vegetation_zone | terrain_zone | urban_zone |
                           industrial_zone | aquatic_zone

        generation_mode: grouped_geometry
        generator:       grouped_geometry_generator
        """
        self._validate(semantic_resolution)
        s = semantic_resolution
        entity_cfg = self._entity_config(s["entity"])

        return {
            "schema_type": _DOMAIN_SCHEMA_TYPE["environment"],  # "zone"
            "schema_version": SCHEMA_VERSION,
            "domain": "environment",
            "entity": s["entity"],
            "generation_mode": s["generation_mode"],
            "geometry_family": s["geometry_family"],
            "generator": _DOMAIN_GENERATOR["environment"],
            "output_formats": entity_cfg.get("supported_outputs", _DOMAIN_OUTPUT_FORMATS["environment"]),
            "zone_config": {
                "instancing_enabled": True,
                "lod_levels": 2,
                "units": "meters",
            },
            "entity_config": entity_cfg,
        }

    def build_gameplay_schema(self, semantic_resolution: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a gameplay executionSchema for gameplay assets.

        Geometry families: logic_marker | gameplay_prop

        generation_mode: mesh | trigger_volume
        generator:       mixed_generator

        IMPORTANT: /api/intent/compile is NOT called here.
        SemanticResolver is the semantic authority for all domains
        including gameplay. intent_compile_bypassed = True is set
        explicitly as a contract guarantee.
        """
        self._validate(semantic_resolution)
        s = semantic_resolution
        entity_cfg = self._entity_config(s["entity"])
        is_trigger = s["generation_mode"] == "trigger_volume"

        return {
            "schema_type": _DOMAIN_SCHEMA_TYPE["gameplay"],  # "gameplay"
            "schema_version": SCHEMA_VERSION,
            "domain": "gameplay",
            "entity": s["entity"],
            "generation_mode": s["generation_mode"],
            "geometry_family": s["geometry_family"],
            "generator": _DOMAIN_GENERATOR["gameplay"],
            "output_formats": entity_cfg.get("supported_outputs", _DOMAIN_OUTPUT_FORMATS["gameplay"]),
            "gameplay_config": {
                "collision_enabled": True,
                "trigger_zones": is_trigger,
                "units": "game_units",
            },
            # Contract guarantee: /api/intent/compile was NOT used.
            # SemanticResolver resolved the entity before this schema was built.
            "intent_compile_bypassed": True,
            "entity_config": entity_cfg,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _entity_config(self, entity: str) -> Dict[str, Any]:
        """
        Return the semantic_templates.json entry for the entity, or {} if absent.
        Provides supported_outputs, geometry_family, generation_mode from taxonomy.
        """
        return dict(self._templates.get(entity, {}))

    @staticmethod
    def _validate(semantic_resolution: Dict[str, Any]) -> None:
        """Validate required keys and known domain. Fail closed."""
        for key in _REQUIRED_SEMANTIC_KEYS:
            if not semantic_resolution.get(key):
                raise ExecutionSchemaError(
                    f"ExecutionSchemaFactory: missing required key '{key}' " f"in semantic_resolution.",
                    error_code="SCHEMA_MISSING_KEY",
                )
        domain = semantic_resolution["domain"]
        if domain not in _DOMAIN_SCHEMA_TYPE:
            raise ExecutionSchemaError(
                f"ExecutionSchemaFactory: unknown domain '{domain}'. "
                f"Valid domains: {sorted(_DOMAIN_SCHEMA_TYPE)}. Failing closed.",
                error_code="SCHEMA_UNKNOWN_DOMAIN",
            )

    @staticmethod
    def _load_templates(path: Path) -> Dict[str, Any]:
        """Load semantic_templates.json. Returns empty dict if file absent."""
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("templates", {})
        except FileNotFoundError:
            return {}
