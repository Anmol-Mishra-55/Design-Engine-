"""
Engineering Validator
Task 7 — Validation Engine

Checks:
  - At least one structural constraint is present
  - At least one fire constraint is present (life safety)
  - At least one plumbing constraint is present
  - All mandatory constraints have non-empty constraint text
  - No duplicate constraint text within the same category
"""
from __future__ import annotations

from typing import List, Set

from ...design_spec.models import DesignSpecification
from ..models import ValidationFinding
from .base import BaseValidator

# Categories that MUST be represented in any valid residential spec
_REQUIRED_CATEGORIES = {"structural", "fire", "plumbing"}


class EngineeringValidator(BaseValidator):
    """Validates engineering constraints for completeness and integrity."""

    @property
    def name(self) -> str:
        return "EngineeringValidator"

    def validate(self, spec: DesignSpecification) -> List[ValidationFinding]:
        findings: List[ValidationFinding] = []
        constraints = spec.engineering

        # ── required category coverage ────────────────────────────────────────
        present_categories = {c.category for c in constraints}
        for cat in _REQUIRED_CATEGORIES:
            rule_id = f"ENG-{cat.upper()}-PRESENT"
            if cat in present_categories:
                findings.append(self._pass(rule_id, f"Engineering category '{cat}' is present."))
            else:
                findings.append(
                    self._fail(
                        rule_id,
                        f"Engineering category '{cat}' is missing — mandatory for all residential specs.",
                    )
                )

        # ── mandatory constraints must have non-empty text ────────────────────
        for i, c in enumerate(constraints):
            rule_id = f"ENG-{c.category.upper()}-TEXT-{i}"
            if c.mandatory and not c.constraint.strip():
                findings.append(
                    self._fail(
                        rule_id,
                        f"Mandatory engineering constraint [{c.category}] has empty text.",
                    )
                )
            else:
                findings.append(
                    self._pass(
                        rule_id,
                        f"Engineering constraint [{c.category}] has valid text.",
                    )
                )

        # ── duplicate constraint text within same category ────────────────────
        seen_per_cat: dict[str, Set[str]] = {}
        for c in constraints:
            bucket = seen_per_cat.setdefault(c.category, set())
            norm = c.constraint.strip().lower()
            rule_id = f"ENG-{c.category.upper()}-DUPLICATE"
            if norm in bucket:
                findings.append(
                    self._fail(
                        rule_id,
                        f"Duplicate engineering constraint in category '{c.category}': \"{c.constraint[:60]}\".",
                        severity="warning",
                    )
                )
            else:
                bucket.add(norm)

        if not constraints:
            findings.append(
                self._fail(
                    "ENG-NONEMPTY",
                    "Specification has no engineering constraints.",
                )
            )
        else:
            findings.append(
                self._pass(
                    "ENG-NONEMPTY",
                    f"Specification has {len(constraints)} engineering constraint(s).",
                )
            )

        return findings
