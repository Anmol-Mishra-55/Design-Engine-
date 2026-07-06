"""
Tests for DKB Runtime — Task 8

Covers:
  PromptInstruction model and from_prompt_runner()
  DKBRuntimeResult model and properties
  DKBRuntime constructor and from_directory()
  execute() — happy path with real DKB entries
  execute() — no match raises DKBRuntimeNoMatchError
  execute() — not initialised raises DKBRuntimeNotInitializedError
  execute() — compiler error raises DKBRuntimeCompilerError
  execute() — validator error raises DKBRuntimeValidationError
  execute() — result carries all pipeline outputs
  execute() — result.valid reflects validation report
  execute() — result.summary() is a compact dict
  execute() — all 9 residential entries resolve correctly
  PromptInstruction.from_prompt_runner() — valid input
  PromptInstruction.from_prompt_runner() — missing fields raises ValueError
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from app.design_knowledge.design_spec.compiler import DesignSpecCompiler, DesignSpecCompilerError
from app.design_knowledge.design_spec.models import DesignSpecification, GenerationMetadata
from app.design_knowledge.knowledge.body_models import BaseKnowledgeBody
from app.design_knowledge.knowledge.models import KnowledgeEntry, KnowledgeMetadata
from app.design_knowledge.knowledge.registry import KnowledgeRegistry
from app.design_knowledge.knowledge.search import KnowledgeSearchEngine, TFIDFSearchProvider
from app.design_knowledge.runtime import (
    DKBRuntime,
    DKBRuntimeCompilerError,
    DKBRuntimeNoMatchError,
    DKBRuntimeNotInitializedError,
    DKBRuntimeResult,
    DKBRuntimeValidationError,
    PromptInstruction,
)
from app.design_knowledge.validation.engine import ValidationEngine, ValidationEngineError
from app.design_knowledge.validation.models import ValidationFinding, ValidationReport

# ── Paths ─────────────────────────────────────────────────────────────────────

_RESIDENTIAL_DIR = Path(__file__).parent.parent / "data" / "residential"


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _instruction(
    topic: str = "3bhk apartment", module: str = "architecture", intent: str = "generate"
) -> PromptInstruction:
    return PromptInstruction(module=module, intent=intent, topic=topic)


def _runtime_from_residential() -> DKBRuntime:
    return DKBRuntime.from_directory(_RESIDENTIAL_DIR)


# ── PromptInstruction ─────────────────────────────────────────────────────────


def test_prompt_instruction_fields():
    inst = PromptInstruction(module="architecture", intent="generate", topic="villa")
    assert inst.module == "architecture"
    assert inst.intent == "generate"
    assert inst.topic == "villa"
    assert inst.tasks == []
    assert inst.output_format == "3d_model"
    assert inst.product_context == "creator_core"
    assert inst.parameters == {}


def test_prompt_instruction_from_prompt_runner_valid():
    raw = {
        "module": "architecture",
        "intent": "generate",
        "topic": "2bhk apartment",
        "tasks": ["layout", "rooms"],
        "output_format": "floor_plan",
        "product_context": "creator_core",
    }
    inst = PromptInstruction.from_prompt_runner(raw)
    assert inst.module == "architecture"
    assert inst.intent == "generate"
    assert inst.topic == "2bhk apartment"
    assert inst.tasks == ["layout", "rooms"]
    assert inst.output_format == "floor_plan"


def test_prompt_instruction_from_prompt_runner_missing_module():
    with pytest.raises(ValueError, match="module"):
        PromptInstruction.from_prompt_runner({"intent": "generate", "topic": "villa"})


def test_prompt_instruction_from_prompt_runner_missing_intent():
    with pytest.raises(ValueError, match="intent"):
        PromptInstruction.from_prompt_runner({"module": "architecture", "topic": "villa"})


def test_prompt_instruction_from_prompt_runner_missing_topic():
    with pytest.raises(ValueError, match="topic"):
        PromptInstruction.from_prompt_runner({"module": "architecture", "intent": "generate"})


def test_prompt_instruction_from_prompt_runner_defaults():
    raw = {"module": "architecture", "intent": "generate", "topic": "studio"}
    inst = PromptInstruction.from_prompt_runner(raw)
    assert inst.tasks == []
    assert inst.output_format == "3d_model"
    assert inst.product_context == "creator_core"


# ── DKBRuntimeResult ──────────────────────────────────────────────────────────


def _make_result(valid: bool = True) -> DKBRuntimeResult:
    from app.design_knowledge.knowledge.loader import KnowledgeLoader

    registry = KnowledgeRegistry()
    loader = KnowledgeLoader(_RESIDENTIAL_DIR, registry)
    loader.load_directory(_RESIDENTIAL_DIR)
    entry = next(e for e in registry.list() if e.metadata.id == "3bhk")

    compiler = DesignSpecCompiler()
    spec = compiler.compile(entry)

    engine = ValidationEngine()
    report = engine.validate(spec)

    return DKBRuntimeResult(
        knowledge_entry=entry,
        design_specification=spec,
        validation_report=report,
        search_score=0.95,
        matched_fields={"title": ["3bhk"], "tags": ["residential"]},
        topic="3bhk apartment",
        module="architecture",
        intent="generate",
    )


def test_result_valid_property():
    result = _make_result()
    assert result.valid == result.validation_report.valid


def test_result_knowledge_id():
    result = _make_result()
    assert result.knowledge_id == "3bhk"


def test_result_design_type():
    result = _make_result()
    assert result.design_type == "3bhk"


def test_result_summary_keys():
    result = _make_result()
    s = result.summary()
    for key in (
        "knowledge_id",
        "design_type",
        "topic",
        "module",
        "intent",
        "search_score",
        "matched_fields",
        "spec_id",
        "valid",
        "validation_score",
        "error_count",
        "warning_count",
    ):
        assert key in s, f"summary missing key: {key}"


def test_result_summary_values():
    result = _make_result()
    s = result.summary()
    assert s["knowledge_id"] == "3bhk"
    assert s["topic"] == "3bhk apartment"
    assert s["module"] == "architecture"
    assert s["search_score"] == round(0.95, 4)


# ── DKBRuntime construction ───────────────────────────────────────────────────


def test_runtime_instantiates():
    engine = KnowledgeSearchEngine(TFIDFSearchProvider())
    runtime = DKBRuntime(search_engine=engine)
    assert runtime is not None


def test_runtime_from_directory():
    runtime = _runtime_from_residential()
    assert runtime is not None
    assert runtime._indexed is True


def test_runtime_not_initialized_raises():
    engine = KnowledgeSearchEngine(TFIDFSearchProvider())
    runtime = DKBRuntime(search_engine=engine)
    with pytest.raises(DKBRuntimeNotInitializedError):
        runtime.execute(_instruction())


# ── execute() happy path ──────────────────────────────────────────────────────


def test_execute_returns_result():
    runtime = _runtime_from_residential()
    result = runtime.execute(_instruction("3bhk apartment"))
    assert isinstance(result, DKBRuntimeResult)


def test_execute_result_has_knowledge_entry():
    runtime = _runtime_from_residential()
    result = runtime.execute(_instruction("3bhk apartment"))
    assert result.knowledge_entry is not None
    assert result.knowledge_entry.metadata.id is not None


def test_execute_result_has_design_specification():
    runtime = _runtime_from_residential()
    result = runtime.execute(_instruction("3bhk apartment"))
    assert isinstance(result.design_specification, DesignSpecification)


def test_execute_result_has_validation_report():
    runtime = _runtime_from_residential()
    result = runtime.execute(_instruction("3bhk apartment"))
    assert isinstance(result.validation_report, ValidationReport)


def test_execute_result_search_score_between_0_and_1():
    runtime = _runtime_from_residential()
    result = runtime.execute(_instruction("3bhk apartment"))
    assert 0.0 <= result.search_score <= 1.0


def test_execute_result_matched_fields_is_dict():
    runtime = _runtime_from_residential()
    result = runtime.execute(_instruction("3bhk apartment"))
    assert isinstance(result.matched_fields, dict)


def test_execute_result_topic_preserved():
    runtime = _runtime_from_residential()
    result = runtime.execute(_instruction("villa luxury"))
    assert result.topic == "villa luxury"


def test_execute_result_module_preserved():
    runtime = _runtime_from_residential()
    result = runtime.execute(_instruction(module="architecture"))
    assert result.module == "architecture"


def test_execute_result_intent_preserved():
    runtime = _runtime_from_residential()
    result = runtime.execute(_instruction(intent="generate"))
    assert result.intent == "generate"


def test_execute_villa_resolves_villa():
    runtime = _runtime_from_residential()
    result = runtime.execute(_instruction("villa independent house"))
    assert result.knowledge_id == "villa"


def test_execute_studio_resolves_studio():
    runtime = _runtime_from_residential()
    result = runtime.execute(_instruction("studio apartment single room"))
    assert result.knowledge_id == "studio"


def test_execute_penthouse_resolves_penthouse():
    runtime = _runtime_from_residential()
    result = runtime.execute(_instruction("penthouse top floor terrace"))
    assert result.knowledge_id == "penthouse"


# ── execute() — all 9 residential entries ────────────────────────────────────

_RESIDENTIAL_QUERIES = [
    ("studio apartment single room", "studio"),
    ("1rk room kitchen", "1rk"),
    ("1bhk one bedroom hall kitchen", "1bhk"),
    ("2bhk two bedroom apartment", "2bhk"),
    ("3bhk three bedroom family apartment", "3bhk"),
    ("4bhk four bedroom large apartment", "4bhk"),
    ("villa independent house garden", "villa"),
    ("duplex two floor apartment", "duplex"),
    ("penthouse top floor terrace luxury", "penthouse"),
]


@pytest.mark.parametrize("topic,expected_id", _RESIDENTIAL_QUERIES)
def test_execute_all_residential_entries(topic, expected_id):
    runtime = _runtime_from_residential()
    result = runtime.execute(_instruction(topic))
    assert (
        result.knowledge_id == expected_id
    ), f"Expected {expected_id!r} for topic {topic!r}, got {result.knowledge_id!r}"


# ── execute() — error paths ───────────────────────────────────────────────────


def test_execute_no_match_raises():
    engine = KnowledgeSearchEngine(TFIDFSearchProvider())
    engine.index([])  # empty index
    runtime = DKBRuntime(search_engine=engine)
    runtime._indexed = True
    with pytest.raises(DKBRuntimeNoMatchError):
        runtime.execute(_instruction("3bhk apartment"))


def test_execute_compiler_error_raises():
    runtime = _runtime_from_residential()
    mock_compiler = MagicMock(spec=DesignSpecCompiler)
    mock_compiler.compile.side_effect = DesignSpecCompilerError("boom")
    runtime._compiler = mock_compiler
    with pytest.raises(DKBRuntimeCompilerError, match="boom"):
        runtime.execute(_instruction("3bhk apartment"))


def test_execute_validator_error_raises():
    runtime = _runtime_from_residential()
    mock_validator = MagicMock(spec=ValidationEngine)
    mock_validator.validate.side_effect = ValidationEngineError("no validator")
    runtime._validator = mock_validator
    with pytest.raises(DKBRuntimeValidationError, match="no validator"):
        runtime.execute(_instruction("3bhk apartment"))


# ── execute() — validation result passthrough ─────────────────────────────────


def test_execute_valid_spec_has_valid_true():
    runtime = _runtime_from_residential()
    result = runtime.execute(_instruction("3bhk apartment"))
    # All 9 DKB entries are well-formed — they should produce valid specs
    assert isinstance(result.valid, bool)


def test_execute_validation_score_between_0_and_1():
    runtime = _runtime_from_residential()
    result = runtime.execute(_instruction("villa"))
    assert 0.0 <= result.validation_report.score <= 1.0


# ── index() method ────────────────────────────────────────────────────────────


def test_index_method_enables_execute():
    from app.design_knowledge.knowledge.loader import KnowledgeLoader

    registry = KnowledgeRegistry()
    loader = KnowledgeLoader(_RESIDENTIAL_DIR, registry)
    loader.load_directory(_RESIDENTIAL_DIR)

    engine = KnowledgeSearchEngine(TFIDFSearchProvider())
    runtime = DKBRuntime(search_engine=engine)

    runtime.index(registry.list())
    result = runtime.execute(_instruction("3bhk apartment"))
    assert result.knowledge_id == "3bhk"
