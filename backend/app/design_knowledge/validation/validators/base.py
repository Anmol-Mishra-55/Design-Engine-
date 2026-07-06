"""
Base Validator
Task 7 — Validation Engine

Every domain validator inherits from BaseValidator.
The ValidationEngine calls validate() on each registered validator
and merges the returned findings into one ValidationReport.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from ...design_spec.models import DesignSpecification
from ..models import ValidationFinding


class BaseValidator(ABC):
    """
    Abstract base for all domain validators.

    Subclasses implement validate() and return a list of ValidationFinding.
    They must never raise — all failures are captured as findings.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable validator name used in finding.validator field."""

    @abstractmethod
    def validate(self, spec: DesignSpecification) -> List[ValidationFinding]:
        """
        Inspect *spec* and return all findings (passed and failed).

        Args:
            spec: The compiled DesignSpecification to validate.

        Returns:
            List of ValidationFinding — one per rule checked.
            Must never raise an exception.
        """

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _pass(self, rule_id: str, message: str, severity: str = "error") -> ValidationFinding:
        return ValidationFinding(
            rule_id=rule_id,
            severity=severity,
            message=message,
            validator=self.name,
            passed=True,
        )

    def _fail(self, rule_id: str, message: str, severity: str = "error") -> ValidationFinding:
        return ValidationFinding(
            rule_id=rule_id,
            severity=severity,
            message=message,
            validator=self.name,
            passed=False,
        )
