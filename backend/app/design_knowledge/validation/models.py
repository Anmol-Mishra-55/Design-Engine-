"""
Validation Engine Output Models
Task 7

These are the typed objects the Validation Engine produces.
Downstream consumers (Prompt Runner, Core, QA) read these — never raw dicts.

Pipeline position
─────────────────
  DesignSpecification → ValidationEngine → ValidationReport
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, computed_field


class ValidationFinding(BaseModel):
    """
    A single finding produced by a validator.

    rule_id    — stable identifier (e.g. "3BHK-001", "ENG-002")
    severity   — "error" blocks the spec; "warning" is advisory
    message    — human-readable description of what failed or passed
    validator  — which validator produced this finding
    passed     — True if the rule passed, False if it failed
    """

    rule_id: str
    severity: str  # "error" | "warning"
    message: str
    validator: str  # "SpaceValidator" | "RelationshipValidator" | etc.
    passed: bool


class ValidationReport(BaseModel):
    """
    Aggregated output of the ValidationEngine.

    valid          — True only when there are zero error-severity failures
    errors         — human-readable messages for all failed error rules
    warnings       — human-readable messages for all failed warning rules
    passed_rules   — rule_ids that passed
    failed_rules   — rule_ids that failed
    score          — percentage of rules that passed (0.0 – 1.0)
    findings       — full structured list of all findings
    spec_id        — the spec that was validated
    validated_at   — timestamp
    """

    spec_id: str
    validated_at: datetime = Field(default_factory=datetime.utcnow)
    findings: List[ValidationFinding] = Field(default_factory=list)

    @computed_field
    @property
    def errors(self) -> List[str]:
        return [f.message for f in self.findings if not f.passed and f.severity == "error"]

    @computed_field
    @property
    def warnings(self) -> List[str]:
        return [f.message for f in self.findings if not f.passed and f.severity == "warning"]

    @computed_field
    @property
    def passed_rules(self) -> List[str]:
        return [f.rule_id for f in self.findings if f.passed]

    @computed_field
    @property
    def failed_rules(self) -> List[str]:
        return [f.rule_id for f in self.findings if not f.passed]

    @computed_field
    @property
    def valid(self) -> bool:
        return len(self.errors) == 0

    @computed_field
    @property
    def score(self) -> float:
        if not self.findings:
            return 1.0
        return round(len(self.passed_rules) / len(self.findings), 4)
