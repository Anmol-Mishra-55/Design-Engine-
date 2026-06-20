"""
TTGAdapter
==========
Bridges the TANTRA semantic layer (SemanticResolver output) and the TTG
generation engine (CoreExecutionRequest / CoreExecutionResponse).

Responsibilities:
  - prepare_request()   : SemanticResolver output → CoreExecutionRequest
  - validate_output()   : CoreExecutionResponse → raises TTGValidationError on bad output
  - route_to_generator(): resolve domain → generator name

Domain routing:
  architecture → layout_generator
  vehicle      → mesh_generator
  object       → mesh_generator
  gameplay     → mixed_generator
  environment  → grouped_geometry_generator

Constraint checking uses generation_constraints.json to detect and reject
domain contamination (DOMAIN_CONTAMINATION error code).
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict

from ..contracts.core_execution_request import CoreExecutionRequest, ValidationError
from ..contracts.core_execution_response import CoreExecutionResponse

# ── Constants ─────────────────────────────────────────────────────────────────

_CONSTRAINTS_PATH = os.path.join(os.path.dirname(__file__), "..", "design_semantics", "generation_constraints.json")

_DOMAIN_TO_GENERATOR: Dict[str, str] = {
    "architecture": "layout_generator",
    "vehicle": "mesh_generator",
    "object": "mesh_generator",
    "gameplay": "mixed_generator",
    "environment": "grouped_geometry_generator",
}


# ── Exceptions ────────────────────────────────────────────────────────────────


class TTGValidationError(Exception):
    """Raised when domain contamination or output validation fails."""

    def __init__(self, message: str, error_code: str = "TTG_VALIDATION_ERROR") -> None:
        super().__init__(message)
        self.error_code = error_code


# ── Adapter ───────────────────────────────────────────────────────────────────


class TTGAdapter:
    """
    Bridge between TANTRA semantic layer and the TTG generation engine.

    Usage::

        adapter = TTGAdapter()

        request = adapter.prepare_request(
            semantic={
                "domain": "vehicle",
                "entity": "drone",
                "generation_mode": "mesh",
                "geometry_family": "rotorcraft",
            },
            prompt="Build a combat drone",
            trace_id="trace_abc123",
        )

        response = core_client.execute_task(request)
        adapter.validate_output(response, expected_domain="vehicle")
    """

    def __init__(self, constraints_path: str = _CONSTRAINTS_PATH) -> None:
        self._constraints = self._load_constraints(constraints_path)

    # ── Public Methods ────────────────────────────────────────────────────────

    def prepare_request(
        self,
        semantic: Dict[str, Any],
        prompt: str,
        trace_id: str,
        task_id: str | None = None,
        tags: list | None = None,
    ) -> CoreExecutionRequest:
        """
        Convert SemanticResolver output into a CoreExecutionRequest.

        Args:
            semantic:  Output of SemanticResolver.resolve() —
                       {domain, entity, generation_mode, geometry_family}
            prompt:    Original user prompt string.
            trace_id:  Mandatory trace ID.
            task_id:   Optional task ID; auto-generated if None.
            tags:      Optional tag list.

        Returns:
            CoreExecutionRequest ready for CoreClient.execute_task()

        Raises:
            TTGValidationError: if domain contamination is detected.
            ValidationError:    if execution_token or trace_id are empty.
        """
        domain = semantic.get("domain", "")
        entity = semantic.get("entity", "")
        generation_mode = semantic.get("generation_mode", "")
        geometry_family = semantic.get("geometry_family", "")

        self._check_contamination(domain, geometry_family, generation_mode)

        generator = self.route_to_generator(domain)

        return CoreExecutionRequest(
            input=prompt,
            agent=generator,
            execution_token=CoreExecutionRequest.generate_token(),
            trace_id=trace_id,
            task_id=task_id or f"task_{uuid.uuid4().hex[:12]}",
            input_type="semantic",
            tags=tags or [domain, entity, generation_mode],
            retries=3,
            fallback_agent="fallback_generator",
        )

    def validate_output(
        self,
        response: CoreExecutionResponse,
        expected_domain: str,
    ) -> None:
        """
        Validate a CoreExecutionResponse from the TTG engine.

        Args:
            response:        Response from CoreClient.execute_task().
            expected_domain: The domain that was requested (used for contamination check).

        Raises:
            TTGValidationError: if status is 'failed'/'rejected', agent_output is
                                missing required keys, or domain contamination is found
                                in the output.
        """
        if response.status in ("failed", "rejected"):
            raise TTGValidationError(
                f"TTG generation failed with status '{response.status}': "
                f"{response.agent_output.get('error', 'no details')}",
                error_code="TTG_GENERATION_FAILED",
            )

        output = response.agent_output
        if not isinstance(output, dict):
            raise TTGValidationError(
                "agent_output must be a dict.",
                error_code="TTG_INVALID_OUTPUT_TYPE",
            )

        self._check_output_contamination(expected_domain, output)

    def route_to_generator(self, domain: str) -> str:
        """
        Map a semantic domain to its TTG generator name.

        Args:
            domain: One of architecture | vehicle | object | gameplay | environment.

        Returns:
            Generator name string.

        Raises:
            TTGValidationError: if domain is unknown.
        """
        generator = _DOMAIN_TO_GENERATOR.get(domain)
        if not generator:
            raise TTGValidationError(
                f"Unknown domain '{domain}'. Cannot route to generator. "
                f"Valid domains: {sorted(_DOMAIN_TO_GENERATOR)}",
                error_code="TTG_UNKNOWN_DOMAIN",
            )
        return generator

    # ── Private Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _load_constraints(path: str) -> Dict[str, Any]:
        try:
            with open(os.path.normpath(path), "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {"domains": {}}

    def _check_contamination(
        self,
        domain: str,
        geometry_family: str,
        generation_mode: str,
    ) -> None:
        """
        Check that geometry_family and generation_mode are allowed for the domain.
        Raises TTGValidationError with DOMAIN_CONTAMINATION on violation.
        """
        domain_rules = self._constraints.get("domains", {}).get(domain)
        if not domain_rules:
            return

        allowed_families = domain_rules.get("allowed_geometry_families", [])
        if allowed_families and geometry_family and geometry_family not in allowed_families:
            raise TTGValidationError(
                f"DOMAIN_CONTAMINATION: geometry_family '{geometry_family}' is not allowed "
                f"in domain '{domain}'. Allowed: {allowed_families}",
                error_code="DOMAIN_CONTAMINATION",
            )

        supported_modes = domain_rules.get("supported_generation_modes", [])
        if supported_modes and generation_mode and generation_mode not in supported_modes:
            raise TTGValidationError(
                f"DOMAIN_CONTAMINATION: generation_mode '{generation_mode}' is not supported "
                f"in domain '{domain}'. Supported: {supported_modes}",
                error_code="DOMAIN_CONTAMINATION",
            )

        forbidden_terms = domain_rules.get("forbidden_terms", [])
        for term in forbidden_terms:
            if term in geometry_family:
                raise TTGValidationError(
                    f"DOMAIN_CONTAMINATION: forbidden term '{term}' found in "
                    f"geometry_family '{geometry_family}' for domain '{domain}'.",
                    error_code="DOMAIN_CONTAMINATION",
                )

    def _check_output_contamination(
        self,
        expected_domain: str,
        output: Dict[str, Any],
    ) -> None:
        """Scan agent_output values for forbidden terms of the expected domain."""
        domain_rules = self._constraints.get("domains", {}).get(expected_domain)
        if not domain_rules:
            return

        forbidden_terms = domain_rules.get("forbidden_terms", [])
        output_text = json.dumps(output).lower()

        for term in forbidden_terms:
            if term.lower() in output_text:
                raise TTGValidationError(
                    f"DOMAIN_CONTAMINATION: forbidden term '{term}' found in TTG output "
                    f"for domain '{expected_domain}'.",
                    error_code="DOMAIN_CONTAMINATION",
                )
