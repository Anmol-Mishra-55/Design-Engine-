"""
Rule Validator
Task 7 — Validation Engine

Executes the machine-checkable validation_rules stored in the DesignSpecification.

Each rule carries a condition string (e.g. "master_bedroom area >= 160 sqft").
This validator parses and evaluates those conditions against the spec's actual data.

Supported condition patterns
─────────────────────────────
  <space_name> is present
  <space_name> area >= <N> sqft
  <space_name> area <= <N> sqft
  <space_name> and <space_name2> are present
  <space_name> is adjacent to <space_name2>
  <space_name> has direct_access to <space_name2>
  <space_name> is separated from <space_name2>
  no <space_name> is directly accessible from <space_name2>
  <space_name> is accessible from <space_name2>
  engineering category <cat> is present
  at least <N> spaces of type <keyword> are present

Unrecognised conditions are recorded as warnings (not errors) so that
new rule patterns added to DKB files do not silently break validation.
"""
from __future__ import annotations

import re
from typing import List, Optional, Set

from ...design_spec.models import DesignSpecification
from ..models import ValidationFinding
from .base import BaseValidator


class RuleValidator(BaseValidator):
    """Executes the validation_rules embedded in the DesignSpecification."""

    @property
    def name(self) -> str:
        return "RuleValidator"

    def validate(self, spec: DesignSpecification) -> List[ValidationFinding]:
        findings: List[ValidationFinding] = []
        space_names: Set[str] = {s.name for s in spec.spaces}
        space_areas: dict[str, float] = {s.name: s.area_min_sqft for s in spec.spaces}

        for rule in spec.validation_rules:
            finding = self._evaluate(rule.rule_id, rule.condition, rule.severity, spec, space_names, space_areas)
            findings.append(finding)

        if not spec.validation_rules:
            findings.append(
                self._fail(
                    "RULE-NONEMPTY",
                    "Specification has no validation rules — nothing to enforce.",
                    severity="warning",
                )
            )
        else:
            findings.append(
                self._pass(
                    "RULE-NONEMPTY",
                    f"Specification has {len(spec.validation_rules)} validation rule(s).",
                )
            )

        return findings

    # ── Condition evaluator ───────────────────────────────────────────────────

    def _evaluate(
        self,
        rule_id: str,
        condition: str,
        severity: str,
        spec: DesignSpecification,
        space_names: Set[str],
        space_areas: dict[str, float],
    ) -> ValidationFinding:
        c = condition.strip().lower()

        # ── "<space> is present" ──────────────────────────────────────────────
        m = re.match(r"^(\w+)\s+is\s+present", c)
        if m:
            space = m.group(1)
            if space in space_names:
                return self._pass(rule_id, f"[{rule_id}] '{space}' is present. ✓", severity)
            return self._fail(rule_id, f"[{rule_id}] Required space '{space}' is missing.", severity)

        # ── "<s1> and <s2> are present" ───────────────────────────────────────
        m = re.match(r"^(\w+)\s+and\s+(\w+)\s+are\s+present", c)
        if m:
            s1, s2 = m.group(1), m.group(2)
            missing = [s for s in (s1, s2) if s not in space_names]
            if not missing:
                return self._pass(rule_id, f"[{rule_id}] '{s1}' and '{s2}' are both present. ✓", severity)
            return self._fail(rule_id, f"[{rule_id}] Missing space(s): {missing}.", severity)

        # ── "<space> area >= N sqft" ──────────────────────────────────────────
        m = re.match(r"^(\w+)\s+area\s*>=\s*([\d.]+)\s*sqft", c)
        if m:
            space, threshold = m.group(1), float(m.group(2))
            actual = space_areas.get(space)
            if actual is None:
                return self._fail(rule_id, f"[{rule_id}] Space '{space}' not found in spec.", severity)
            if actual >= threshold:
                return self._pass(rule_id, f"[{rule_id}] '{space}' area {actual} sqft >= {threshold} sqft. ✓", severity)
            return self._fail(
                rule_id, f"[{rule_id}] '{space}' area {actual} sqft < required {threshold} sqft.", severity
            )

        # ── "<space> area <= N sqft" ──────────────────────────────────────────
        m = re.match(r"^(\w+)\s+area\s*<=\s*([\d.]+)\s*sqft", c)
        if m:
            space, threshold = m.group(1), float(m.group(2))
            actual = space_areas.get(space)
            if actual is None:
                return self._fail(rule_id, f"[{rule_id}] Space '{space}' not found in spec.", severity)
            if actual <= threshold:
                return self._pass(rule_id, f"[{rule_id}] '{space}' area {actual} sqft <= {threshold} sqft. ✓", severity)
            return self._fail(
                rule_id, f"[{rule_id}] '{space}' area {actual} sqft > maximum {threshold} sqft.", severity
            )

        # ── "<s1> is adjacent to <s2>" ────────────────────────────────────────
        m = re.match(r"^(\w+)\s+is\s+adjacent\s+to\s+(\w+)", c)
        if m:
            s1, s2 = m.group(1), m.group(2)
            return self._check_relationship(rule_id, s1, s2, "adjacent", spec, severity)

        # ── "<s1> has direct_access to <s2>" ─────────────────────────────────
        m = re.match(r"^(\w+)\s+has\s+direct_access\s+to\s+(\w+)", c)
        if m:
            s1, s2 = m.group(1), m.group(2)
            return self._check_relationship(rule_id, s1, s2, "direct_access", spec, severity)

        # ── "<s1> is separated from <s2>" ────────────────────────────────────
        m = re.match(r"^(\w+)\s+is\s+separated\s+from\s+(\w+)", c)
        if m:
            s1, s2 = m.group(1), m.group(2)
            return self._check_relationship(rule_id, s1, s2, "separated", spec, severity)

        # ── "<s1> is accessible from <s2>" ───────────────────────────────────
        m = re.match(r"^(\w+)\s+is\s+accessible\s+from\s+(\w+)", c)
        if m:
            s1, s2 = m.group(1), m.group(2)
            return self._check_any_relationship(rule_id, s1, s2, spec, severity)

        # ── "no <space> is directly accessible from <space2>" ────────────────
        m = re.match(r"^no\s+(\w+)\s+is\s+directly\s+accessible\s+from\s+(\w+)", c)
        if m:
            s1, s2 = m.group(1), m.group(2)
            has_direct = any(
                (e.from_space == s2 and e.to_space == s1 and e.relationship == "direct_access")
                or (e.from_space == s1 and e.to_space == s2 and e.relationship == "direct_access")
                for e in spec.adjacency_graph
            )
            if not has_direct:
                return self._pass(rule_id, f"[{rule_id}] No direct access between '{s1}' and '{s2}'. ✓", severity)
            return self._fail(
                rule_id, f"[{rule_id}] '{s1}' has direct access to '{s2}' — violates separation rule.", severity
            )

        # ── "engineering category <cat> is present" ───────────────────────────
        m = re.match(r"^engineering\s+category\s+(\w+)\s+is\s+present", c)
        if m:
            cat = m.group(1)
            present = any(e.category == cat for e in spec.engineering)
            if present:
                return self._pass(rule_id, f"[{rule_id}] Engineering category '{cat}' is present. ✓", severity)
            return self._fail(rule_id, f"[{rule_id}] Engineering category '{cat}' is missing.", severity)

        # ── "at least N spaces of type <keyword> are present" ────────────────
        m = re.match(r"^at\s+least\s+(\d+)\s+spaces?\s+of\s+type\s+(\w+)\s+are\s+present", c)
        if m:
            n, keyword = int(m.group(1)), m.group(2)
            matches = [s for s in space_names if keyword in s]
            if len(matches) >= n:
                return self._pass(
                    rule_id, f"[{rule_id}] Found {len(matches)} space(s) matching '{keyword}' (need {n}). ✓", severity
                )
            return self._fail(
                rule_id, f"[{rule_id}] Only {len(matches)} space(s) matching '{keyword}' found, need {n}.", severity
            )

        # ── unrecognised condition — record as warning, not error ─────────────
        return ValidationFinding(
            rule_id=rule_id,
            severity="warning",
            message=f'[{rule_id}] Condition not recognised by RuleValidator: "{condition[:80]}". Skipped.',
            validator=self.name,
            passed=True,  # don't penalise score for unrecognised patterns
        )

    # ── Relationship helpers ──────────────────────────────────────────────────

    def _check_relationship(
        self,
        rule_id: str,
        s1: str,
        s2: str,
        rel: str,
        spec: DesignSpecification,
        severity: str,
    ) -> ValidationFinding:
        found = any(
            (e.from_space == s1 and e.to_space == s2 and e.relationship == rel)
            or (e.from_space == s2 and e.to_space == s1 and e.relationship == rel)
            for e in spec.adjacency_graph
        )
        if found:
            return self._pass(rule_id, f"[{rule_id}] '{s1}' {rel} '{s2}'. ✓", severity)
        return self._fail(rule_id, f"[{rule_id}] Expected '{s1}' {rel} '{s2}' — relationship not found.", severity)

    def _check_any_relationship(
        self,
        rule_id: str,
        s1: str,
        s2: str,
        spec: DesignSpecification,
        severity: str,
    ) -> ValidationFinding:
        found = any(
            (e.from_space == s1 and e.to_space == s2) or (e.from_space == s2 and e.to_space == s1)
            for e in spec.adjacency_graph
        )
        if found:
            return self._pass(rule_id, f"[{rule_id}] '{s1}' is accessible from '{s2}'. ✓", severity)
        return self._fail(rule_id, f"[{rule_id}] '{s1}' has no relationship with '{s2}'.", severity)
