"""
DKB Runtime Response Models

DKBRuntimeResult is the single structured output of DKBRuntime.execute().

It carries every stage of the pipeline so QA, Core, and TTG can inspect
each step independently without re-running the pipeline.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from ..design_spec.models import DesignSpecification
from ..knowledge.models import KnowledgeEntry
from ..validation.models import ValidationReport


class DKBRuntimeResult(BaseModel):
    """
    Complete output of a single DKBRuntime.execute() call.

    Carries every pipeline stage so downstream consumers (QA, Core, TTG)
    can inspect or re-use any intermediate result without re-running.

    Attributes
    ----------
    knowledge_entry:      The resolved KnowledgeEntry from the DKB.
    design_specification: The compiled DesignSpecification.
    validation_report:    The ValidationReport produced by the Validation Engine.
    search_score:         Relevance score (0.0–1.0) from the search engine.
    matched_fields:       Field-name → matched tokens from the search result.
    topic:                The search query used (from PromptInstruction.topic).
    module:               The Prompt Runner module that produced the instruction.
    intent:               The Prompt Runner intent.
    """

    knowledge_entry: KnowledgeEntry
    design_specification: DesignSpecification
    validation_report: ValidationReport
    search_score: float
    matched_fields: Dict[str, List[str]]
    topic: str
    module: str
    intent: str

    model_config = {"arbitrary_types_allowed": True}

    @property
    def valid(self) -> bool:
        """True if the validation report has no errors."""
        return self.validation_report.valid

    @property
    def knowledge_id(self) -> str:
        """Shortcut to the resolved knowledge entry id."""
        return self.knowledge_entry.metadata.id

    @property
    def design_type(self) -> str:
        """Shortcut to the compiled design type (e.g. '3bhk', 'villa')."""
        return self.design_specification.design_type

    def summary(self) -> Dict[str, Any]:
        """
        Return a compact summary dict suitable for logging and API responses.
        Does not include the full specification or report bodies.
        """
        return {
            "knowledge_id": self.knowledge_id,
            "design_type": self.design_type,
            "topic": self.topic,
            "module": self.module,
            "intent": self.intent,
            "search_score": round(self.search_score, 4),
            "matched_fields": self.matched_fields,
            "spec_id": self.design_specification.spec_id,
            "valid": self.valid,
            "validation_score": round(self.validation_report.score, 4),
            "error_count": len(self.validation_report.errors),
            "warning_count": len(self.validation_report.warnings),
        }
