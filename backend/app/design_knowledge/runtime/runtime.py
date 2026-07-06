"""
DKB Runtime
Task 8 — Prompt Runner → DKB Integration

Boundary contract
─────────────────
RECEIVES : PromptInstruction (built from Prompt Runner output)
PRODUCES : DKBRuntimeResult
NEVER    : calls Prompt Runner, calls TTG, reads files directly,
           duplicates search / compiler / validator logic

Pipeline position
─────────────────
  Prompt Runner output
      │
      ▼
  PromptInstruction
      │
      ▼
  DKBRuntime.execute()
      │
      ├─ KnowledgeSearchEngine.search()  → SearchResult (score + matched_fields)
      ├─ DesignSpecCompiler.compile()    → DesignSpecification
      └─ ValidationEngine.validate()    → ValidationReport
      │
      ▼
  DKBRuntimeResult

The runtime is a pure orchestrator.
It owns no business logic — every step is delegated to the existing components.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from ..design_spec.compiler import DesignSpecCompiler, DesignSpecCompilerError
from ..knowledge.loader import KnowledgeLoader
from ..knowledge.models import KnowledgeEntry
from ..knowledge.registry import KnowledgeRegistry
from ..knowledge.search import KnowledgeSearchEngine, SearchResult, TFIDFSearchProvider
from ..validation.engine import ValidationEngine, ValidationEngineError
from .exceptions import (
    DKBRuntimeCompilerError,
    DKBRuntimeNoMatchError,
    DKBRuntimeNotInitializedError,
    DKBRuntimeValidationError,
)
from .request import PromptInstruction
from .response import DKBRuntimeResult

logger = logging.getLogger(__name__)


class DKBRuntime:
    """
    Orchestrates the full DKB pipeline from a PromptInstruction to a
    validated DKBRuntimeResult.

    The runtime is stateless between calls — each execute() is independent.
    It must be initialised with a search index before execute() is called.

    Usage (with pre-loaded registry)::

        registry = KnowledgeRegistry()
        loader = KnowledgeLoader(root_dir, registry)
        loader.load_directory(root_dir)

        engine = KnowledgeSearchEngine(TFIDFSearchProvider())
        engine.index(registry.list())

        runtime = DKBRuntime(search_engine=engine)
        result = runtime.execute(instruction)

    Usage (with auto-load from directory)::

        runtime = DKBRuntime.from_directory(Path("data/residential"))
        result = runtime.execute(instruction)
    """

    def __init__(
        self,
        search_engine: KnowledgeSearchEngine,
        compiler: Optional[DesignSpecCompiler] = None,
        validator: Optional[ValidationEngine] = None,
    ) -> None:
        self._engine = search_engine
        self._compiler = compiler or DesignSpecCompiler()
        self._validator = validator or ValidationEngine()
        self._indexed = False

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def from_directory(
        cls,
        directory: Path,
        provider=None,
    ) -> "DKBRuntime":
        """
        Build a fully initialised DKBRuntime by loading all DKB files
        from *directory* and indexing them.

        Args:
            directory: Path to a directory containing versioned DKB JSON files.
            provider:  Optional SearchProvider. Defaults to TFIDFSearchProvider.

        Returns:
            A DKBRuntime ready to call execute().
        """
        registry = KnowledgeRegistry()
        loader = KnowledgeLoader(root_directory=directory, registry=registry)
        loader.load_directory(directory)

        search_provider = provider or TFIDFSearchProvider()
        engine = KnowledgeSearchEngine(search_provider)
        engine.index(registry.list())

        runtime = cls(search_engine=engine)
        runtime._indexed = True
        logger.info(
            "DKBRuntime initialised from %s — %d entries indexed",
            directory,
            len(registry.list()),
        )
        return runtime

    # ── Index management ──────────────────────────────────────────────────────

    def index(self, entries: List[KnowledgeEntry]) -> None:
        """
        Build the search index from *entries*.

        Must be called before execute() when using the constructor directly.
        """
        self._engine.index(entries)
        self._indexed = True

    # ── Core pipeline ─────────────────────────────────────────────────────────

    def execute(self, instruction: PromptInstruction) -> DKBRuntimeResult:
        """
        Run the full DKB pipeline for *instruction*.

        Pipeline:
            1. Search  — find the best matching KnowledgeEntry for instruction.topic
            2. Compile — transform the entry into a DesignSpecification
            3. Validate — run the ValidationEngine on the specification

        Args:
            instruction: A PromptInstruction built from Prompt Runner output.

        Returns:
            DKBRuntimeResult containing all pipeline outputs.

        Raises:
            DKBRuntimeNotInitializedError: if index() has not been called.
            DKBRuntimeNoMatchError:        if no entry matches the topic.
            DKBRuntimeCompilerError:       if the compiler fails.
            DKBRuntimeValidationError:     if the validator is not registered.
        """
        if not self._indexed:
            raise DKBRuntimeNotInitializedError("DKBRuntime has no search index. Call index() or use from_directory().")

        topic = instruction.topic
        logger.info(
            "DKBRuntime.execute: module=%s intent=%s topic=%r",
            instruction.module,
            instruction.intent,
            topic,
        )

        # ── Step 1: Search ────────────────────────────────────────────────────
        results = self._engine.search(topic, top_k=1)
        if not results:
            raise DKBRuntimeNoMatchError(
                f"No DKB entry found for topic {topic!r}. " "Ensure the knowledge library is loaded and indexed."
            )

        top: SearchResult = results[0]
        entry = top.entry
        logger.info(
            "DKBRuntime: resolved %r (score=%.4f matched_on=%s)",
            entry.metadata.id,
            top.score,
            list(top.matched_on.keys()),
        )

        # ── Step 2: Compile ───────────────────────────────────────────────────
        try:
            spec = self._compiler.compile(entry)
        except DesignSpecCompilerError as exc:
            raise DKBRuntimeCompilerError(f"Compiler failed for entry {entry.metadata.id!r}: {exc}") from exc

        logger.info("DKBRuntime: compiled spec_id=%s", spec.spec_id)

        # ── Step 3: Validate ──────────────────────────────────────────────────
        try:
            report = self._validator.validate(spec)
        except ValidationEngineError as exc:
            raise DKBRuntimeValidationError(f"Validator failed for spec {spec.spec_id!r}: {exc}") from exc

        logger.info(
            "DKBRuntime: validated valid=%s score=%.4f errors=%d warnings=%d",
            report.valid,
            report.score,
            len(report.errors),
            len(report.warnings),
        )

        return DKBRuntimeResult(
            knowledge_entry=entry,
            design_specification=spec,
            validation_report=report,
            search_score=top.score,
            matched_fields=top.matched_on,
            topic=topic,
            module=instruction.module,
            intent=instruction.intent,
        )
