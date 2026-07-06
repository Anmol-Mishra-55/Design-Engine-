"""
Design Specification Compiler
Task 6 — DKB Compiler

Boundary contract
─────────────────
RECEIVES : KnowledgeEntry with a validated BaseKnowledgeBody subclass
PRODUCES : DesignSpecification
NEVER    : reads files, calls external services, or modifies the registry

Pipeline position
─────────────────
  KnowledgeEntry → DesignSpecCompiler → DesignSpecification

Domain dispatch
───────────────
  The compiler uses a _COMPILER_REGISTRY dict to route each body type
  to the correct compile method.  Adding a new domain (e.g. commercial)
  requires only:
    1. A new _compile_commercial() method
    2. One entry in _COMPILER_REGISTRY
  Nothing else changes.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict

from ..knowledge.body_models import BaseKnowledgeBody, ResidentialKnowledgeBody
from ..knowledge.models import KnowledgeEntry
from .models import (
    AdjacencyEdge,
    DesignSpecification,
    EngineeringConstraintSpec,
    GenerationMetadata,
    SpaceSpec,
    ValidationRuleSpec,
)


class DesignSpecCompilerError(Exception):
    """Raised when the compiler cannot produce a specification."""


class DesignSpecCompiler:
    """
    Compiles a KnowledgeEntry into a DesignSpecification.

    The compiler is stateless — every call to compile() is independent.
    It never reads files, never touches the registry, and never calls
    external services.

    Usage::

        compiler = DesignSpecCompiler()
        spec = compiler.compile(entry)
    """

    # ── Domain dispatch ───────────────────────────────────────────────────────
    # Maps body class → compile method name.
    # Add one entry here when a new domain body model is introduced.

    _COMPILER_REGISTRY: Dict[type, str] = {
        ResidentialKnowledgeBody: "_compile_residential",
    }

    # ── Public API ────────────────────────────────────────────────────────────

    def compile(self, entry: KnowledgeEntry) -> DesignSpecification:
        """
        Compile *entry* into a DesignSpecification.

        Args:
            entry: A KnowledgeEntry whose body is a validated BaseKnowledgeBody subclass.

        Returns:
            DesignSpecification ready for the Validation Engine and TTG.

        Raises:
            DesignSpecCompilerError: if the body type has no registered compiler.
        """
        body = entry.body
        method_name = self._COMPILER_REGISTRY.get(type(body))
        if method_name is None:
            raise DesignSpecCompilerError(
                f"No compiler registered for body type '{type(body).__name__}'. "
                f"Registered types: {[t.__name__ for t in self._COMPILER_REGISTRY]}"
            )

        metadata = GenerationMetadata(
            knowledge_id=entry.metadata.id,
            knowledge_version=entry.metadata.version,
            knowledge_source_path=entry.source_path,
            compiled_at=datetime.utcnow(),
        )

        method = getattr(self, method_name)
        return method(entry, metadata)

    # ── Residential compiler ──────────────────────────────────────────────────

    def _compile_residential(
        self,
        entry: KnowledgeEntry,
        metadata: GenerationMetadata,
    ) -> DesignSpecification:
        body: ResidentialKnowledgeBody = entry.body  # type: ignore[assignment]

        spaces = [
            SpaceSpec(
                name=s.name,
                area_min_sqft=s.area.min_sqft,
                area_max_sqft=s.area.max_sqft,
                required=True,
                notes=s.notes,
            )
            for s in body.required_spaces
        ] + [
            SpaceSpec(
                name=s.name,
                area_min_sqft=s.area.min_sqft,
                area_max_sqft=s.area.max_sqft,
                required=False,
                notes=s.notes,
            )
            for s in body.optional_spaces
        ]

        adjacency = [
            AdjacencyEdge(
                from_space=r.from_space,
                to_space=r.to_space,
                relationship=r.relationship,
                notes=r.notes,
            )
            for r in body.space_relationships
        ]

        circulation = [r.rule for r in body.circulation]

        engineering = [
            EngineeringConstraintSpec(
                category=c.category,
                constraint=c.constraint,
                mandatory=c.mandatory,
            )
            for c in body.engineering
        ]

        validation_rules = [
            ValidationRuleSpec(
                rule_id=r.rule_id,
                condition=r.condition,
                severity=r.severity,
            )
            for r in body.validation_rules
        ]

        return DesignSpecification(
            spec_id=f"spec_{entry.metadata.id}_{uuid.uuid4().hex[:8]}",
            project_type=entry.metadata.type,
            design_type=entry.metadata.id,
            spaces=spaces,
            adjacency_graph=adjacency,
            circulation_rules=circulation,
            engineering=engineering,
            validation_rules=validation_rules,
            supported_styles=list(body.supported_styles),
            generation_metadata=metadata,
            raw_body=body.model_dump(),
        )
