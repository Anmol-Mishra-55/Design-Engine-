"""
Residential Validator
Task 7 — Validation Engine

Orchestrates all sub-validators for residential DesignSpecifications.
Registered in the VALIDATOR_REGISTRY under the key "residential".
"""
from __future__ import annotations

from typing import List

from ...design_spec.models import DesignSpecification
from ..models import ValidationFinding
from .base import BaseValidator
from .engineering import EngineeringValidator
from .relationships import RelationshipValidator
from .rules import RuleValidator
from .spaces import SpaceValidator


class ResidentialValidator(BaseValidator):
    """
    Composite validator for residential design specifications.

    Runs SpaceValidator, RelationshipValidator, EngineeringValidator,
    and RuleValidator in sequence and merges all findings.
    """

    _SUB_VALIDATORS: List[BaseValidator] = [
        SpaceValidator(),
        RelationshipValidator(),
        EngineeringValidator(),
        RuleValidator(),
    ]

    @property
    def name(self) -> str:
        return "ResidentialValidator"

    def validate(self, spec: DesignSpecification) -> List[ValidationFinding]:
        findings: List[ValidationFinding] = []
        for validator in self._SUB_VALIDATORS:
            findings.extend(validator.validate(spec))
        return findings
