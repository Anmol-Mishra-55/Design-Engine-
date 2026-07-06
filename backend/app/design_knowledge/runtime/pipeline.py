"""
DKB Execution Pipeline
Task 9 — DKB → TTG Integration

Boundary contract
─────────────────
RECEIVES : PromptInstruction (from Prompt Runner output)
PRODUCES : DKBExecutionResult (DKBRuntimeResult + TTGGenerationResult)
NEVER    : modifies TTGGenerationPipeline, TTGPayloadBuilder, TTGClient,
           CoreGateway, or any Sprint 1 component

Pipeline position
─────────────────
  Prompt Runner output
      │
      ▼
  PromptInstruction
      │
      ▼
  DKBRuntime.execute()          ← Task 8
      │
      ▼
  DKBRuntimeResult
      │
      ▼
  DKBExecutionPipeline.run()    ← Task 9 (this file)
      │
      ├─ _build_semantic()      converts DesignSpecification → semantic_resolution
      ├─ _build_spec_json()     converts DesignSpecification → spec_json dict
      └─ TTGGenerationPipeline.run()  ← Sprint 1, unchanged
      │
      ▼
  DKBExecutionResult

Architecture decision
─────────────────────
TTGGenerationPipeline.run() normally calls CoreGateway (Step 1) which calls
Prompt Runner + SemanticResolver.  For the DKB path, semantic context is
already resolved by DKBRuntime — we do NOT call CoreGateway again.

Instead, DKBExecutionPipeline calls the TTGGenerationPipeline steps directly
after Step 1, injecting the DKB-derived semantic context.  This reuses
Steps 2–6 (payload build, execute, poll, bucket) without duplication.

Semantic resolution from DesignSpecification
────────────────────────────────────────────
DesignSpecification.project_type → domain  (e.g. "residential" → "architecture")
DesignSpecification.design_type  → entity  (e.g. "3bhk", "villa")
domain                           → generation_mode + geometry_family (fixed per domain)
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..design_spec.models import DesignSpecification
from .request import PromptInstruction
from .response import DKBRuntimeResult
from .runtime import DKBRuntime

logger = logging.getLogger(__name__)

# ── Domain mapping ────────────────────────────────────────────────────────────
# Maps DKB project_type → TTG semantic domain
_PROJECT_TYPE_TO_DOMAIN: Dict[str, str] = {
    "residential": "architecture",
    "commercial": "architecture",
    "architecture": "architecture",
}

# Fixed generation_mode and geometry_family per TTG domain
_DOMAIN_GENERATION_MODE: Dict[str, str] = {
    "architecture": "layout",
    "vehicle": "mesh",
    "object": "mesh",
    "environment": "grouped_geometry",
    "gameplay": "mesh",
}

_DOMAIN_GEOMETRY_FAMILY: Dict[str, str] = {
    "architecture": "apartment_layout",
    "vehicle": "rotorcraft",
    "object": "primitive_prop",
    "environment": "urban_zone",
    "gameplay": "gameplay_prop",
}


# ── Exceptions ────────────────────────────────────────────────────────────────


class DKBExecutionPipelineError(Exception):
    """Raised when the DKB execution pipeline fails."""


class DKBExecutionSemanticError(DKBExecutionPipelineError):
    """Raised when DesignSpecification cannot be mapped to a TTG semantic context."""


# ── Result ────────────────────────────────────────────────────────────────────


@dataclass
class DKBExecutionResult:
    """
    Complete result of a DKBExecutionPipeline.run() call.

    Carries both the DKB pipeline output (Task 8) and the TTG generation
    result (Sprint 1) so every stage is inspectable by QA and Core.

    Attributes
    ----------
    dkb_result:       Full DKBRuntimeResult from Task 8.
    trace_id:         End-to-end trace ID.
    execution_id:     TTG execution ID from POST /core/execute.
    domain:           Resolved TTG domain (e.g. "architecture").
    entity:           Resolved TTG entity (e.g. "3bhk").
    bucket_url:       Primary bucket URL where the generated asset is stored.
    execution_status: Final TTG execution status string.
    semantic:         The semantic_resolution dict passed to TTGPayloadBuilder.
    ttg_result:       Raw TTGGenerationResult from Sprint 1 pipeline (optional —
                      None when TTG is mocked or skipped in tests).
    """

    dkb_result: DKBRuntimeResult
    trace_id: str
    execution_id: str
    domain: str
    entity: str
    bucket_url: str
    execution_status: str
    semantic: Dict[str, Any]
    ttg_result: Optional[Any] = None  # TTGGenerationResult — typed as Any to avoid circular import

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "execution_id": self.execution_id,
            "domain": self.domain,
            "entity": self.entity,
            "bucket_url": self.bucket_url,
            "execution_status": self.execution_status,
            "knowledge_id": self.dkb_result.knowledge_id,
            "design_type": self.dkb_result.design_type,
            "spec_id": self.dkb_result.design_specification.spec_id,
            "valid": self.dkb_result.valid,
            "validation_score": round(self.dkb_result.validation_report.score, 4),
            "semantic": self.semantic,
        }


# ── Pipeline ──────────────────────────────────────────────────────────────────


class DKBExecutionPipeline:
    """
    Connects the DKB Runtime (Task 8) to the existing TTG generation pipeline
    (Sprint 1) without modifying any Sprint 1 component.

    The pipeline:
        1. DKBRuntime.execute()          — resolve + compile + validate
        2. _build_semantic()             — DesignSpecification → semantic_resolution
        3. _build_spec_json()            — DesignSpecification → spec_json dict
        4. TTGGenerationPipeline steps   — payload build → execute → poll → bucket
           (Steps 2–6 only; Step 1 / CoreGateway is bypassed because DKBRuntime
            already resolved the semantic context)

    Usage::

        pipeline = DKBExecutionPipeline.from_directory(
            directory=Path("app/design_knowledge/data/residential"),
            bucket_urls=["https://bhiv-bucket.onrender.com/bucket/artifact/abc"],
        )
        result = await pipeline.run(instruction)
        print(result.bucket_url)
        print(result.execution_status)
    """

    def __init__(
        self,
        dkb_runtime: DKBRuntime,
        bucket_urls: List[str],
        ttg_pipeline=None,  # TTGGenerationPipeline — injected for testing
    ) -> None:
        self._runtime = dkb_runtime
        self._bucket_urls = list(bucket_urls)
        self._ttg_pipeline = ttg_pipeline  # None → real TTGGenerationPipeline created lazily

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def from_directory(
        cls,
        directory,
        bucket_urls: List[str],
        ttg_pipeline=None,
    ) -> "DKBExecutionPipeline":
        """
        Build a fully initialised DKBExecutionPipeline from a DKB data directory.

        Args:
            directory:    Path to a directory containing versioned DKB JSON files.
            bucket_urls:  Target bucket URLs for TTG output storage.
            ttg_pipeline: Optional TTGGenerationPipeline (for testing/injection).

        Returns:
            DKBExecutionPipeline ready to call run().
        """
        from pathlib import Path

        runtime = DKBRuntime.from_directory(Path(directory))
        return cls(dkb_runtime=runtime, bucket_urls=bucket_urls, ttg_pipeline=ttg_pipeline)

    # ── Public API ────────────────────────────────────────────────────────────

    async def run(
        self,
        instruction: PromptInstruction,
        trace_id: Optional[str] = None,
        asset_refs: Optional[List[str]] = None,
    ) -> DKBExecutionResult:
        """
        Execute the full DKB → TTG pipeline.

        Steps:
            1. DKBRuntime.execute(instruction)  — search + compile + validate
            2. Build semantic_resolution from DesignSpecification
            3. Build spec_json from DesignSpecification
            4. TTGGenerationPipeline steps 2–6  — payload → execute → poll → bucket

        Args:
            instruction: PromptInstruction built from Prompt Runner output.
            trace_id:    Optional trace ID; auto-generated if not provided.
            asset_refs:  Optional existing bucket artifact references.

        Returns:
            DKBExecutionResult with all pipeline outputs.

        Raises:
            DKBExecutionSemanticError:  if DesignSpecification cannot be mapped.
            DKBExecutionPipelineError:  if TTG execution fails.
        """
        trace_id = trace_id or f"trace_{uuid.uuid4().hex[:16]}"

        logger.info(
            "DKBExecutionPipeline.run: trace=%s topic=%r module=%s intent=%s",
            trace_id,
            instruction.topic,
            instruction.module,
            instruction.intent,
        )

        # ── Step 1: DKB Runtime ───────────────────────────────────────────────
        dkb_result = self._runtime.execute(instruction)
        spec = dkb_result.design_specification

        logger.info(
            "DKBExecutionPipeline: DKB resolved knowledge_id=%s spec_id=%s valid=%s",
            dkb_result.knowledge_id,
            spec.spec_id,
            dkb_result.valid,
        )

        # ── Step 2: Build semantic_resolution ────────────────────────────────
        semantic = self._build_semantic(spec)

        # ── Step 3: Build spec_json ───────────────────────────────────────────
        spec_json = self._build_spec_json(spec, dkb_result)

        # ── Steps 4–6: TTG pipeline (payload → execute → poll → bucket) ──────
        ttg_result = await self._run_ttg(
            semantic=semantic,
            spec_json=spec_json,
            trace_id=trace_id,
            asset_refs=asset_refs or [],
            metadata={
                "module": instruction.module,
                "intent": instruction.intent,
                "topic": instruction.topic,
                "knowledge_id": dkb_result.knowledge_id,
                "spec_id": spec.spec_id,
                "validation_valid": dkb_result.valid,
            },
        )

        result = DKBExecutionResult(
            dkb_result=dkb_result,
            trace_id=trace_id,
            execution_id=ttg_result.execution_id,
            domain=ttg_result.domain,
            entity=ttg_result.entity,
            bucket_url=ttg_result.bucket_record.bucket_url,
            execution_status=ttg_result.execution_status.status,
            semantic=semantic,
            ttg_result=ttg_result,
        )

        logger.info(
            "DKBExecutionPipeline.run complete: trace=%s execution_id=%s status=%s bucket=%s",
            trace_id,
            result.execution_id,
            result.execution_status,
            result.bucket_url,
        )
        return result

    # ── Semantic conversion ───────────────────────────────────────────────────

    def _build_semantic(self, spec: DesignSpecification) -> Dict[str, Any]:
        """
        Convert a DesignSpecification into the semantic_resolution dict
        expected by TTGPayloadBuilder.build().

        Mapping:
            spec.project_type → domain  (via _PROJECT_TYPE_TO_DOMAIN)
            spec.design_type  → entity
            domain            → generation_mode (fixed per domain)
            domain            → geometry_family (fixed per domain)

        Raises:
            DKBExecutionSemanticError: if project_type has no TTG domain mapping.
        """
        domain = _PROJECT_TYPE_TO_DOMAIN.get(spec.project_type)
        if not domain:
            raise DKBExecutionSemanticError(
                f"DKBExecutionPipeline: no TTG domain mapping for "
                f"project_type={spec.project_type!r}. "
                f"Registered types: {sorted(_PROJECT_TYPE_TO_DOMAIN)}"
            )

        return {
            "domain": domain,
            "entity": spec.design_type,
            "generation_mode": _DOMAIN_GENERATION_MODE[domain],
            "geometry_family": _DOMAIN_GEOMETRY_FAMILY[domain],
        }

    # ── spec_json conversion ──────────────────────────────────────────────────

    @staticmethod
    def _build_spec_json(
        spec: DesignSpecification,
        dkb_result: DKBRuntimeResult,
    ) -> Dict[str, Any]:
        """
        Convert a DesignSpecification into the spec_json dict expected by
        TTGPayloadBuilder.build().

        Preserves the raw_body from the DKB entry for TTG passthrough,
        and enriches it with compiled spec fields.
        """
        base: Dict[str, Any] = {
            "type": spec.design_type,
            "design_type": spec.design_type,
            "domain": spec.project_type,
            "spec_id": spec.spec_id,
            "spaces": [s.model_dump() for s in spec.spaces],
            "adjacency": [a.model_dump() for a in spec.adjacency_graph],
            "engineering": [e.model_dump() for e in spec.engineering],
            "styles": spec.supported_styles,
            "knowledge_id": dkb_result.knowledge_id,
            "knowledge_version": spec.generation_metadata.knowledge_version,
        }
        # Merge raw_body for TTG passthrough (rooms, dimensions, etc.)
        if spec.raw_body:
            base["raw_body"] = spec.raw_body
        return base

    # ── TTG execution ─────────────────────────────────────────────────────────

    async def _run_ttg(
        self,
        semantic: Dict[str, Any],
        spec_json: Dict[str, Any],
        trace_id: str,
        asset_refs: List[str],
        metadata: Dict[str, Any],
    ):
        """
        Run TTG Steps 2–6 by calling TTGGenerationPipeline._step_payload(),
        _step_execute(), _step_poll(), and _step_record() directly.

        This bypasses _step_gateway() (CoreGateway + Prompt Runner) because
        DKBRuntime has already resolved the semantic context.

        Falls back to creating a real TTGGenerationPipeline if none was injected.
        """
        from app.services.ttg_generation_pipeline import (
            TTGGenerationAuthError,
            TTGGenerationError,
            TTGGenerationPipeline,
            TTGGenerationTimeoutError,
        )

        pipeline = self._ttg_pipeline or TTGGenerationPipeline()

        try:
            payload_dict = pipeline._step_payload(
                semantic=semantic,
                spec_json=spec_json,
                bucket_urls=self._bucket_urls,
                trace_id=trace_id,
                asset_refs=asset_refs,
                metadata=metadata,
            )
            exec_response = await pipeline._step_execute(payload_dict, trace_id)
            exec_status = await pipeline._step_poll(exec_response.execution_id, trace_id)
            bucket_record = pipeline._step_record(
                trace_id=trace_id,
                execution_id=exec_response.execution_id,
                bucket_urls=self._bucket_urls,
                semantic=semantic,
                exec_status=exec_status,
            )
        except (TTGGenerationError, TTGGenerationAuthError, TTGGenerationTimeoutError) as exc:
            raise DKBExecutionPipelineError(f"DKBExecutionPipeline: TTG execution failed — {exc}") from exc

        # Return a lightweight result object that mirrors TTGGenerationResult
        from app.services.ttg_generation_pipeline import TTGGenerationResult

        return TTGGenerationResult(
            trace_id=trace_id,
            execution_id=exec_response.execution_id,
            domain=semantic["domain"],
            entity=semantic["entity"],
            execution_response=exec_response,
            execution_status=exec_status,
            bucket_record=bucket_record,
            semantic=semantic,
        )
