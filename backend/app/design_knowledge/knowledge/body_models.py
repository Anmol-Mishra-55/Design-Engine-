"""
DKB Engineering Knowledge Body Models
Rudra Governance — Task 4

Boundary contract
─────────────────
These models define the CONTRACT between the DKB and the Compiler.
The Compiler receives typed body objects — never raw dicts.
The Loader is responsible for parsing JSON into the correct body model.

Domain hierarchy
─────────────────
  BaseKnowledgeBody          ← all domains inherit from this
      ResidentialKnowledgeBody
      CommercialKnowledgeBody   (Task 6)
      InfrastructureKnowledgeBody (Task 7)
      StyleKnowledgeBody        (Task 7)
      EngineeringKnowledgeBody  (Task 7)

Adding a new domain
───────────────────
  1. Create a subclass of BaseKnowledgeBody here.
  2. Add one entry to BODY_MODEL_REGISTRY in loader.py.
  Nothing else changes.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# ── Shared primitives ─────────────────────────────────────────────────────────


class AreaRange(BaseModel):
    """Minimum and maximum area in square feet."""

    min_sqft: float = Field(..., gt=0)
    max_sqft: float = Field(..., gt=0)


class DimensionRule(BaseModel):
    """A named dimensional constraint."""

    dimension: str  # e.g. "width", "length", "ceiling_height"
    min_value: float = Field(..., gt=0)
    unit: str = "ft"


class SpaceDefinition(BaseModel):
    """
    A single named space within a building programme.

    Examples: master_bedroom, living_room, dry_balcony
    """

    name: str
    area: AreaRange
    dimensions: List[DimensionRule] = Field(default_factory=list)
    notes: Optional[str] = None


class SpaceRelationship(BaseModel):
    """
    Defines how two spaces must relate to each other.

    relationship values:
      direct_access   — door between the two spaces
      adjacent        — share a wall or are immediately next to each other
      visual_connect  — sightline between spaces (open plan)
      separated       — must NOT be adjacent (acoustic / privacy)
      near            — within one room of each other
    """

    from_space: str
    to_space: str
    relationship: Literal["direct_access", "adjacent", "visual_connect", "separated", "near"]
    notes: Optional[str] = None


class CirculationRule(BaseModel):
    """
    A movement or visibility rule governing how occupants navigate the plan.
    """

    rule: str
    rationale: Optional[str] = None


class VentilationRule(BaseModel):
    """Natural or mechanical ventilation requirement for a space."""

    space: str
    requirement: Literal["natural", "mechanical", "either"]
    notes: Optional[str] = None


class LightingRule(BaseModel):
    """Daylighting or artificial lighting requirement for a space."""

    space: str
    requirement: Literal["natural", "artificial", "either"]
    min_window_to_floor_ratio: Optional[float] = None  # e.g. 0.10 = 10 %
    notes: Optional[str] = None


class EngineeringConstraint(BaseModel):
    """
    A hard structural, MEP, or code constraint.
    These are non-negotiable — the compiler must enforce them.
    """

    category: Literal["structural", "electrical", "plumbing", "hvac", "fire", "code"]
    constraint: str
    mandatory: bool = True


class ConstructionGuideline(BaseModel):
    """
    A preferred construction practice.
    These are advisory — the compiler should include them but may relax them.
    """

    category: str
    guideline: str


class ValidationRule(BaseModel):
    """
    A machine-checkable rule the Validation Engine will enforce.

    rule_id   — stable identifier used in validation reports
    condition — human-readable description of what is checked
    severity  — error stops compilation; warning is logged only
    """

    rule_id: str
    condition: str
    severity: Literal["error", "warning"] = "error"


# ── Base body ─────────────────────────────────────────────────────────────────


class BaseKnowledgeBody(BaseModel):
    """
    Root contract for all DKB body types.

    Every domain body must inherit from this class.
    The Compiler type-checks against BaseKnowledgeBody; domain-specific
    compilers downcast to the concrete subclass they require.
    """

    purpose: str
    planning_philosophy: str
    supported_styles: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    validation_rules: List[ValidationRule] = Field(default_factory=list)


# ── Residential ───────────────────────────────────────────────────────────────


class OccupancyProfile(BaseModel):
    """Who lives in this unit and how they use it."""

    typical_occupants: int = Field(..., gt=0)
    occupant_profile: str  # e.g. "nuclear family", "young professional"
    lifestyle_notes: Optional[str] = None


class ResidentialKnowledgeBody(BaseKnowledgeBody):
    """
    Engineering knowledge body for all residential building types.

    Covers: Studio, 1RK, 1BHK, 2BHK, 3BHK, 4BHK, Duplex, Villa, Penthouse.

    The Compiler reads this object to derive a Design Specification.
    Every field is intentional — none are cosmetic metadata.

    Field contract
    ──────────────
    purpose              Why this building type exists (design intent).
    planning_philosophy  The core spatial reasoning principle.
    occupancy            Who lives here and how they use the space.
    required_spaces      Spaces that MUST appear in every valid plan.
    optional_spaces      Spaces that MAY appear depending on brief/budget.
    space_relationships  Adjacency and access rules between named spaces.
    circulation          Movement and visibility rules across the plan.
    ventilation          Natural/mechanical ventilation per space.
    lighting             Daylighting requirements per space.
    engineering          Hard structural/MEP/code constraints.
    construction         Advisory construction practices.
    supported_styles     Architectural styles compatible with this type.
    constraints          Plain-language hard limits (area, height, etc.).
    validation_rules     Machine-checkable rules for the Validation Engine.
    """

    occupancy: OccupancyProfile

    required_spaces: List[SpaceDefinition] = Field(
        ..., min_length=1, description="Spaces that must appear in every valid plan."
    )
    optional_spaces: List[SpaceDefinition] = Field(
        default_factory=list, description="Spaces that may appear depending on brief or budget."
    )
    space_relationships: List[SpaceRelationship] = Field(
        default_factory=list, description="Adjacency and access rules between named spaces."
    )
    circulation: List[CirculationRule] = Field(
        default_factory=list, description="Movement and visibility rules across the plan."
    )
    ventilation: List[VentilationRule] = Field(
        default_factory=list, description="Natural or mechanical ventilation requirements."
    )
    lighting: List[LightingRule] = Field(
        default_factory=list, description="Daylighting and artificial lighting requirements."
    )
    engineering: List[EngineeringConstraint] = Field(
        default_factory=list, description="Hard structural, MEP, and code constraints."
    )
    construction: List[ConstructionGuideline] = Field(
        default_factory=list, description="Advisory construction practices."
    )
