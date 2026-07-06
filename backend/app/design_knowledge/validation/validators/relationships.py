"""
Relationship Validator
Task 7 — Validation Engine

Checks:
  - Every adjacency edge references spaces that exist in the specification
  - No self-referencing edges (from_space == to_space)
  - No duplicate edges (same from/to/relationship triple)
  - Separated relationships are not contradicted by direct_access edges
"""
from __future__ import annotations

from typing import List, Set, Tuple

from ...design_spec.models import DesignSpecification
from ..models import ValidationFinding
from .base import BaseValidator


class RelationshipValidator(BaseValidator):
    """Validates adjacency graph integrity."""

    @property
    def name(self) -> str:
        return "RelationshipValidator"

    def validate(self, spec: DesignSpecification) -> List[ValidationFinding]:
        findings: List[ValidationFinding] = []
        space_names: Set[str] = {s.name for s in spec.spaces}
        seen: Set[Tuple[str, str, str]] = set()

        for edge in spec.adjacency_graph:
            base_id = f"REL-{edge.from_space.upper()}-{edge.to_space.upper()}"

            # self-reference
            if edge.from_space == edge.to_space:
                findings.append(
                    self._fail(
                        f"{base_id}-SELF",
                        f"Adjacency edge has same from and to space: '{edge.from_space}'.",
                    )
                )
                continue

            # dangling reference — from_space
            if edge.from_space not in space_names:
                findings.append(
                    self._fail(
                        f"{base_id}-FROM-MISSING",
                        f"Adjacency edge references unknown space '{edge.from_space}'.",
                    )
                )
            # dangling reference — to_space
            if edge.to_space not in space_names:
                findings.append(
                    self._fail(
                        f"{base_id}-TO-MISSING",
                        f"Adjacency edge references unknown space '{edge.to_space}'.",
                    )
                )

            if edge.from_space in space_names and edge.to_space in space_names:
                # duplicate edge
                triple = (edge.from_space, edge.to_space, edge.relationship)
                if triple in seen:
                    findings.append(
                        self._fail(
                            f"{base_id}-DUPLICATE",
                            f"Duplicate adjacency edge: {edge.from_space} → {edge.to_space} " f"({edge.relationship}).",
                            severity="warning",
                        )
                    )
                else:
                    seen.add(triple)
                    findings.append(
                        self._pass(
                            f"{base_id}-{edge.relationship.upper()}",
                            f"Relationship {edge.from_space} → {edge.to_space} "
                            f"({edge.relationship}) references valid spaces.",
                        )
                    )

        # contradiction check: separated pair also has direct_access
        separated = {(e.from_space, e.to_space) for e in spec.adjacency_graph if e.relationship == "separated"}
        direct = {(e.from_space, e.to_space) for e in spec.adjacency_graph if e.relationship == "direct_access"}
        for pair in separated & direct:
            findings.append(
                self._fail(
                    f"REL-{pair[0].upper()}-{pair[1].upper()}-CONTRADICTION",
                    f"Spaces '{pair[0]}' and '{pair[1]}' are marked both 'separated' "
                    f"and 'direct_access' — contradiction.",
                )
            )

        if not spec.adjacency_graph:
            findings.append(
                self._fail(
                    "REL-GRAPH-NONEMPTY",
                    "Adjacency graph is empty — no space relationships defined.",
                    severity="warning",
                )
            )
        else:
            findings.append(
                self._pass(
                    "REL-GRAPH-NONEMPTY",
                    f"Adjacency graph has {len(spec.adjacency_graph)} relationship(s).",
                )
            )

        return findings
