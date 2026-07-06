"""
Design Specification Models
Task 6 — DKB Compiler output contract

These are the typed objects the Compiler produces.
The Validation Engine and TTG adapter consume these — never raw dicts.

Pipeline position
─────────────────
  KnowledgeEntry → DesignSpecCompiler → DesignSpecification → ValidationEngine → TTG
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SpaceSpec(BaseModel):
    """A single resolved space in the design specification."""

    name: str
    area_min_sqft: float
    area_max_sqft: float
    required: bool = True
    notes: Optional[str] = None


class AdjacencyEdge(BaseModel):
    """A directed adjacency relationship between two spaces."""

    from_space: str
    to_space: str
    relationship: str  # direct_access | adjacent | visual_connect | separated | near
    notes: Optional[str] = None


class EngineeringConstraintSpec(BaseModel):
    """A hard engineering constraint carried into the specification."""

    category: str  # structural | electrical | plumbing | hvac | fire | code
    constraint: str
    mandatory: bool = True


class ValidationRuleSpec(BaseModel):
    """A machine-checkable rule for the Validation Engine."""

    rule_id: str
    condition: str
    severity: str = "error"  # error | warning


class GenerationMetadata(BaseModel):
    """Provenance and compilation metadata."""

    knowledge_id: str
    knowledge_version: str
    knowledge_source_path: Optional[str]
    compiled_at: datetime = Field(default_factory=datetime.utcnow)
    compiler_version: str = "v1.0.0"


class DesignSpecification(BaseModel):
    """
    Canonical output of the Design Specification Compiler.

    This is the single object that flows from the Compiler to:
      - ValidationEngine  (checks validation_rules)
      - TTG / Core        (uses spaces, adjacency, engineering for geometry)

    Field contract
    ──────────────
    spec_id              Unique identifier for this specification instance.
    project_type         The knowledge type (e.g. "residential").
    design_type          The specific subtype (e.g. "3bhk", "villa").
    spaces               All resolved spaces (required + optional).
    adjacency_graph      All space relationships.
    circulation_rules    Movement and visibility rules (plain strings).
    engineering          Hard structural/MEP/code constraints.
    validation_rules     Rules the Validation Engine will enforce.
    supported_styles     Architectural styles compatible with this type.
    generation_metadata  Provenance — which DKB entry was compiled and when.
    raw_body             The original typed body, preserved for downstream use.
    """

    spec_id: str
    project_type: str
    design_type: str
    spaces: List[SpaceSpec] = Field(default_factory=list)
    adjacency_graph: List[AdjacencyEdge] = Field(default_factory=list)
    circulation_rules: List[str] = Field(default_factory=list)
    engineering: List[EngineeringConstraintSpec] = Field(default_factory=list)
    validation_rules: List[ValidationRuleSpec] = Field(default_factory=list)
    supported_styles: List[str] = Field(default_factory=list)
    generation_metadata: GenerationMetadata
    raw_body: Optional[Dict[str, Any]] = None  # serialised body for TTG passthrough
