"""
Validation Engine
Task 7

Boundary contract
─────────────────
RECEIVES : DesignSpecification
PRODUCES : ValidationReport
NEVER    : reads files, modifies the registry, or calls external services

Pipeline position
─────────────────
  DesignSpecification → ValidationEngine → ValidationReport

Validator registry
──────────────────
  VALIDATOR_REGISTRY maps project_type → BaseValidator subclass.
  Adding a new domain (e.g. commercial) requires only:
    1. A new CommmercialValidator(BaseValidator) class
    2. One entry in VALIDATOR_REGISTRY
  Nothing else changes.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Type

from ..design_spec.models import DesignSpecification
from .models import ValidationFinding, ValidationReport
from .validators.base import BaseValidator
from .validators.residential import ResidentialValidator


class ValidationEngineError(Exception):
    """Raised when no validator is registered for the spec's project_type."""


# ── Validator registry ────────────────────────────────────────────────────────
# Maps project_type → validator class (not instance — instantiated per call).

VALIDATOR_REGISTRY: Dict[str, Type[BaseValidator]] = {
    "residential": ResidentialValidator,
}


class ValidationEngine:
    """
    Validates a compiled DesignSpecification and returns a ValidationReport.

    The engine is stateless — every call to validate() is independent.
    It never reads files, never touches the registry, and never calls
    external services.

    Usage::

        engine = ValidationEngine()
        report = engine.validate(spec)
        if not report.valid:
            print(report.errors)
    """

    def validate(self, spec: DesignSpecification) -> ValidationReport:
        """
        Validate *spec* and return a ValidationReport.

        Args:
            spec: A compiled DesignSpecification.

        Returns:
            ValidationReport with valid, errors, warnings, score, and findings.

        Raises:
            ValidationEngineError: if no validator is registered for spec.project_type.
        """
        validator_cls = VALIDATOR_REGISTRY.get(spec.project_type)
        if validator_cls is None:
            raise ValidationEngineError(
                f"No validator registered for project_type '{spec.project_type}'. "
                f"Registered types: {sorted(VALIDATOR_REGISTRY)}"
            )

        validator = validator_cls()
        findings = validator.validate(spec)

        return ValidationReport(
            spec_id=spec.spec_id,
            validated_at=datetime.utcnow(),
            findings=findings,
        )
