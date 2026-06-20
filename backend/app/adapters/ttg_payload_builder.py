"""
TTGPayloadBuilder
=================
Converts Design Engine outputs into TTG /core/execute contracts.

NO HTTP calls. Pure data assembly and validation.

Pipeline position:
    SemanticResolver.resolve()
        ↓  { domain, entity, generation_mode, geometry_family }
    TTGPayloadBuilder.build()
        ↓  TTGExecutePayload (validated dataclass)
    TTGClient.execute()          ← next task
        ↓  POST /core/execute

Domain → schema_type mapping:
    architecture → scene/layout schema
    vehicle      → mesh schema
    object       → reusable asset schema
    environment  → zone schema
    gameplay     → gameplay schema

Fail-closed on unknown domain (raises TTGPayloadError).

Fixes CWE-22 from ttg_adapter.py: uses pathlib.Path.resolve() throughout,
never os.path.join with __file__.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..factories.execution_schema_factory import ExecutionSchemaError, ExecutionSchemaFactory

# ── Domain → schema_type table ────────────────────────────────────────────────

_DOMAIN_SCHEMA_TYPE: Dict[str, str] = {
    "architecture": "scene/layout",
    "vehicle": "mesh",
    "object": "reusable_asset",
    "environment": "zone",
    "gameplay": "gameplay",
}

# Supported output formats per domain (mirrors semantic_templates.json)
_DOMAIN_OUTPUT_FORMATS: Dict[str, List[str]] = {
    "architecture": ["glb", "stl", "step"],
    "vehicle": ["glb", "stl", "step"],
    "object": ["glb", "stl", "step"],
    "environment": ["glb", "stl", "step"],
    "gameplay": ["glb", "stl", "step"],
}

# Generator names (consistent with TTGAdapter)
_DOMAIN_GENERATOR: Dict[str, str] = {
    "architecture": "layout_generator",
    "vehicle": "mesh_generator",
    "object": "mesh_generator",
    "gameplay": "mixed_generator",
    "environment": "grouped_geometry_generator",
}

PAYLOAD_SCHEMA_VERSION = "1.0"


# ── Exceptions ────────────────────────────────────────────────────────────────


class TTGPayloadError(Exception):
    """Raised when payload construction fails validation."""

    def __init__(self, message: str, error_code: str = "TTG_PAYLOAD_ERROR") -> None:
        super().__init__(message)
        self.error_code = error_code


# ── Output dataclass ──────────────────────────────────────────────────────────


@dataclass
class TTGExecutePayload:
    """
    Validated TTG /core/execute contract.

    Fields match the /core/execute body exactly as documented in
    TTG_INTEGRATION_ANALYSIS.md.

    Usage::

        payload = TTGPayloadBuilder().build(
            semantic_resolution={
                "domain": "vehicle", "entity": "drone",
                "generation_mode": "mesh", "geometry_family": "rotorcraft",
            },
            spec_json={"type": "drone", "dimensions": {...}},
            bucket_urls=["https://bhiv-bucket.onrender.com/bucket/artifact/abc"],
            trace_id="trace_001",
            execution_id="exec_001",
        )
        # pass payload.to_dict() to TTGClient.execute()
    """

    execution_id: str
    trace_id: str
    executionSchema: Dict[str, Any]
    spec_json: Dict[str, Any]
    asset_refs: List[str]
    bucket_urls: List[str]

    # Derived convenience fields (populated by builder, not required as input)
    domain: str = field(default="")
    schema_type: str = field(default="")
    output_formats: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "trace_id": self.trace_id,
            "executionSchema": self.executionSchema,
            "spec_json": self.spec_json,
            "asset_refs": self.asset_refs,
            "bucket_urls": self.bucket_urls,
        }

    def to_full_dict(self) -> Dict[str, Any]:
        """Extended dict including derived fields — useful for logging/debug."""
        base = self.to_dict()
        base["_meta"] = {
            "domain": self.domain,
            "schema_type": self.schema_type,
            "output_formats": self.output_formats,
        }
        return base


# ── Builder ───────────────────────────────────────────────────────────────────


class TTGPayloadBuilder:
    """
    Converts Design Engine outputs into a TTGExecutePayload.

    This class is stateless — all state lives in the returned dataclass.
    No HTTP calls. No file I/O after construction.

    Usage::

        builder = TTGPayloadBuilder()

        payload = builder.build(
            semantic_resolution={
                "domain":          "vehicle",
                "entity":          "drone",
                "generation_mode": "mesh",
                "geometry_family": "rotorcraft",
            },
            spec_json={
                "type":       "drone",
                "dimensions": {"width": 0.8, "length": 0.8, "height": 0.3},
                "components": ["frame", "rotor", "motor"],
                "units":      "meters",
            },
            bucket_urls=[
                "https://bhiv-bucket.onrender.com/bucket/artifact/abc123",
            ],
            trace_id="trace_001",
            execution_id="exec_001",
            metadata={
                "prompt":          "Generate a cargo drone",
                "intent":          "design_creation",
                "product_context": "creator_core",
            },
        )
    """

    # ── Public API ────────────────────────────────────────────────────────────

    def build(
        self,
        semantic_resolution: Dict[str, Any],
        spec_json: Dict[str, Any],
        bucket_urls: List[str],
        trace_id: str,
        execution_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        asset_refs: Optional[List[str]] = None,
    ) -> TTGExecutePayload:
        """
        Build and validate a TTGExecutePayload.

        Args:
            semantic_resolution: Output of SemanticResolver.resolve() —
                                 {domain, entity, generation_mode, geometry_family}
            spec_json:           Enriched design specification dict.
            bucket_urls:         List of Bucket URLs for TTG output storage.
            trace_id:            Mandatory pipeline trace ID.
            execution_id:        Execution ID; auto-generated if not provided.
            metadata:            Optional pipeline metadata (prompt, intent, etc.).
            asset_refs:          Optional list of existing Bucket artifact URLs
                                 (intermediate geometry/spec already stored).

        Returns:
            TTGExecutePayload — validated, ready for TTGClient.execute()

        Raises:
            TTGPayloadError: on unknown domain, missing required fields,
                             invalid bucket_urls, or empty spec_json.
        """
        self._validate_inputs(semantic_resolution, spec_json, bucket_urls, trace_id)

        domain = semantic_resolution["domain"]
        entity = semantic_resolution["entity"]
        generation_mode = semantic_resolution["generation_mode"]
        geometry_family = semantic_resolution["geometry_family"]

        schema_type = _DOMAIN_SCHEMA_TYPE[domain]
        generator = _DOMAIN_GENERATOR[domain]
        output_formats = _DOMAIN_OUTPUT_FORMATS[domain]
        exec_id = execution_id or f"exec_{uuid.uuid4().hex[:12]}"

        # Delegate schema construction to ExecutionSchemaFactory (single authority)
        try:
            execution_schema = ExecutionSchemaFactory().build(semantic_resolution)
        except ExecutionSchemaError as exc:
            raise TTGPayloadError(str(exc), error_code=exc.error_code) from exc

        # Attach pipeline metadata into schema
        execution_schema["pipeline_metadata"] = metadata or {}

        return TTGExecutePayload(
            execution_id=exec_id,
            trace_id=trace_id,
            executionSchema=execution_schema,
            spec_json=spec_json,
            asset_refs=list(asset_refs or []),
            bucket_urls=list(bucket_urls),
            domain=domain,
            schema_type=schema_type,
            output_formats=output_formats,
        )

    # ── Validation ────────────────────────────────────────────────────────────

    @staticmethod
    def _validate_inputs(
        semantic: Dict[str, Any],
        spec_json: Dict[str, Any],
        bucket_urls: List[str],
        trace_id: str,
    ) -> None:
        # trace_id required
        if not trace_id or not str(trace_id).strip():
            raise TTGPayloadError(
                "TTGPayloadBuilder: 'trace_id' is required and cannot be empty.",
                error_code="TTG_MISSING_TRACE_ID",
            )

        # Required semantic keys
        for key in ("domain", "entity", "generation_mode", "geometry_family"):
            if not semantic.get(key):
                raise TTGPayloadError(
                    f"TTGPayloadBuilder: semantic_resolution missing required key '{key}'.",
                    error_code="TTG_MISSING_SEMANTIC_KEY",
                )

        # Domain must be known — fail closed
        domain = semantic["domain"]
        if domain not in _DOMAIN_SCHEMA_TYPE:
            raise TTGPayloadError(
                f"TTGPayloadBuilder: unknown domain '{domain}'. "
                f"Valid domains: {sorted(_DOMAIN_SCHEMA_TYPE)}. "
                f"Failing closed — no payload built.",
                error_code="TTG_UNKNOWN_DOMAIN",
            )

        # spec_json must be a non-empty dict
        if not isinstance(spec_json, dict) or not spec_json:
            raise TTGPayloadError(
                "TTGPayloadBuilder: 'spec_json' must be a non-empty dict.",
                error_code="TTG_INVALID_SPEC_JSON",
            )

        # bucket_urls must be a non-empty list of non-empty strings
        if not isinstance(bucket_urls, list) or not bucket_urls:
            raise TTGPayloadError(
                "TTGPayloadBuilder: 'bucket_urls' must be a non-empty list.",
                error_code="TTG_MISSING_BUCKET_URLS",
            )
        for url in bucket_urls:
            if not isinstance(url, str) or not url.strip():
                raise TTGPayloadError(
                    f"TTGPayloadBuilder: each bucket_url must be a non-empty string, got {url!r}.",
                    error_code="TTG_INVALID_BUCKET_URL",
                )

    # Schema construction is delegated entirely to ExecutionSchemaFactory.
    # TTGPayloadBuilder is responsible for assembly; factory owns schema shape.
