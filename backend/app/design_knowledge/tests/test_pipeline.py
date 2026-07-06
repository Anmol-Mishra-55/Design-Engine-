"""
Tests for DKBExecutionPipeline — Task 9

All TTG network calls are mocked.  No real HTTP is made.

Covers:
  _build_semantic() — all project_type mappings
  _build_semantic() — unknown project_type raises DKBExecutionSemanticError
  _build_spec_json() — fields present, raw_body merged
  DKBExecutionPipeline construction and from_directory()
  run() — happy path end-to-end with mocked TTG
  run() — DKBRuntimeNoMatchError propagates
  run() — TTG failure raises DKBExecutionPipelineError
  DKBExecutionResult.to_dict() — all keys present
  Semantic mapping for residential, commercial, architecture project types
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.design_knowledge.design_spec.compiler import DesignSpecCompiler
from app.design_knowledge.knowledge.loader import KnowledgeLoader
from app.design_knowledge.knowledge.registry import KnowledgeRegistry
from app.design_knowledge.knowledge.search import KnowledgeSearchEngine, TFIDFSearchProvider
from app.design_knowledge.runtime import (
    DKBExecutionPipeline,
    DKBExecutionPipelineError,
    DKBExecutionResult,
    DKBExecutionSemanticError,
    DKBRuntime,
    PromptInstruction,
)
from app.design_knowledge.runtime.pipeline import (
    _DOMAIN_GENERATION_MODE,
    _DOMAIN_GEOMETRY_FAMILY,
    _PROJECT_TYPE_TO_DOMAIN,
)
from app.design_knowledge.validation.engine import ValidationEngine

_RESIDENTIAL_DIR = Path(__file__).parent.parent / "data" / "residential"

# ── Helpers ───────────────────────────────────────────────────────────────────


def _instruction(topic: str = "3bhk apartment") -> PromptInstruction:
    return PromptInstruction(module="architecture", intent="generate", topic=topic)


def _runtime() -> DKBRuntime:
    return DKBRuntime.from_directory(_RESIDENTIAL_DIR)


def _compiled_spec(design_type: str = "3bhk"):
    registry = KnowledgeRegistry()
    loader = KnowledgeLoader(_RESIDENTIAL_DIR, registry)
    loader.load_directory(_RESIDENTIAL_DIR)
    entry = next(e for e in registry.list() if e.metadata.id == design_type)
    return DesignSpecCompiler().compile(entry)


def _mock_ttg_pipeline(execution_id: str = "exec_abc123", status: str = "completed"):
    """Build a fully mocked TTGGenerationPipeline that never makes HTTP calls."""
    from app.contracts.bucket_asset_record import BucketAssetRecord
    from app.services.ttg_client import TTGExecutionResponse, TTGExecutionStatus

    exec_response = TTGExecutionResponse(
        execution_id=execution_id,
        status="accepted",
        message="queued",
    )
    exec_status = TTGExecutionStatus(
        execution_id=execution_id,
        status=status,
        result={"glb_url": "https://bucket.example.com/asset.glb"},
    )
    bucket_record = BucketAssetRecord.create(
        trace_id="trace_test",
        execution_id=execution_id,
        bucket_url="https://bhiv-bucket.onrender.com/bucket/artifact/test",
        asset_type="step",
        asset_name="3bhk",
        payload_hash="abc123",
    )

    mock = MagicMock()
    mock._step_payload.return_value = {"execution_id": execution_id, "trace_id": "t"}
    mock._step_execute = AsyncMock(return_value=exec_response)
    mock._step_poll = AsyncMock(return_value=exec_status)
    mock._step_record.return_value = bucket_record
    return mock


# ── Semantic mapping tests ────────────────────────────────────────────────────


def test_project_type_to_domain_residential():
    assert _PROJECT_TYPE_TO_DOMAIN["residential"] == "architecture"


def test_project_type_to_domain_commercial():
    assert _PROJECT_TYPE_TO_DOMAIN["commercial"] == "architecture"


def test_project_type_to_domain_architecture():
    assert _PROJECT_TYPE_TO_DOMAIN["architecture"] == "architecture"


def test_domain_generation_mode_architecture():
    assert _DOMAIN_GENERATION_MODE["architecture"] == "layout"


def test_domain_geometry_family_architecture():
    assert _DOMAIN_GEOMETRY_FAMILY["architecture"] == "apartment_layout"


def test_build_semantic_residential():
    spec = _compiled_spec("3bhk")
    pipeline = DKBExecutionPipeline(dkb_runtime=_runtime(), bucket_urls=["https://bucket.example.com"])
    semantic = pipeline._build_semantic(spec)
    assert semantic["domain"] == "architecture"
    assert semantic["entity"] == "3bhk"
    assert semantic["generation_mode"] == "layout"
    assert semantic["geometry_family"] == "apartment_layout"


def test_build_semantic_villa():
    spec = _compiled_spec("villa")
    pipeline = DKBExecutionPipeline(dkb_runtime=_runtime(), bucket_urls=["https://bucket.example.com"])
    semantic = pipeline._build_semantic(spec)
    assert semantic["domain"] == "architecture"
    assert semantic["entity"] == "villa"


def test_build_semantic_unknown_project_type_raises():
    spec = _compiled_spec("3bhk")
    # Patch project_type to something unknown
    spec = spec.model_copy(update={"project_type": "unknown_type"})
    pipeline = DKBExecutionPipeline(dkb_runtime=_runtime(), bucket_urls=["https://bucket.example.com"])
    with pytest.raises(DKBExecutionSemanticError, match="unknown_type"):
        pipeline._build_semantic(spec)


# ── spec_json conversion tests ────────────────────────────────────────────────


def test_build_spec_json_has_required_keys():
    runtime = _runtime()
    inst = _instruction("3bhk apartment")
    dkb_result = runtime.execute(inst)
    spec = dkb_result.design_specification
    pipeline = DKBExecutionPipeline(dkb_runtime=runtime, bucket_urls=["https://bucket.example.com"])
    spec_json = pipeline._build_spec_json(spec, dkb_result)
    for key in (
        "type",
        "design_type",
        "domain",
        "spec_id",
        "spaces",
        "adjacency",
        "engineering",
        "styles",
        "knowledge_id",
        "knowledge_version",
    ):
        assert key in spec_json, f"spec_json missing key: {key}"


def test_build_spec_json_design_type_matches():
    runtime = _runtime()
    dkb_result = runtime.execute(_instruction("villa"))
    spec = dkb_result.design_specification
    pipeline = DKBExecutionPipeline(dkb_runtime=runtime, bucket_urls=["https://bucket.example.com"])
    spec_json = pipeline._build_spec_json(spec, dkb_result)
    assert spec_json["design_type"] == "villa"
    assert spec_json["knowledge_id"] == "villa"


def test_build_spec_json_raw_body_merged():
    runtime = _runtime()
    dkb_result = runtime.execute(_instruction("3bhk apartment"))
    spec = dkb_result.design_specification
    pipeline = DKBExecutionPipeline(dkb_runtime=runtime, bucket_urls=["https://bucket.example.com"])
    spec_json = pipeline._build_spec_json(spec, dkb_result)
    if spec.raw_body:
        assert "raw_body" in spec_json


def test_build_spec_json_spaces_is_list():
    runtime = _runtime()
    dkb_result = runtime.execute(_instruction("2bhk two bedroom"))
    spec = dkb_result.design_specification
    pipeline = DKBExecutionPipeline(dkb_runtime=runtime, bucket_urls=["https://bucket.example.com"])
    spec_json = pipeline._build_spec_json(spec, dkb_result)
    assert isinstance(spec_json["spaces"], list)
    assert len(spec_json["spaces"]) > 0


# ── Pipeline construction ─────────────────────────────────────────────────────


def test_pipeline_instantiates():
    pipeline = DKBExecutionPipeline(
        dkb_runtime=_runtime(),
        bucket_urls=["https://bucket.example.com"],
    )
    assert pipeline is not None


def test_pipeline_from_directory():
    pipeline = DKBExecutionPipeline.from_directory(
        directory=_RESIDENTIAL_DIR,
        bucket_urls=["https://bucket.example.com"],
    )
    assert pipeline is not None


# ── run() happy path ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_returns_execution_result():
    mock_ttg = _mock_ttg_pipeline()
    pipeline = DKBExecutionPipeline(
        dkb_runtime=_runtime(),
        bucket_urls=["https://bhiv-bucket.onrender.com/bucket/artifact/test"],
        ttg_pipeline=mock_ttg,
    )
    result = await pipeline.run(_instruction("3bhk apartment"))
    assert isinstance(result, DKBExecutionResult)


@pytest.mark.asyncio
async def test_run_result_has_dkb_result():
    mock_ttg = _mock_ttg_pipeline()
    pipeline = DKBExecutionPipeline(
        dkb_runtime=_runtime(),
        bucket_urls=["https://bhiv-bucket.onrender.com/bucket/artifact/test"],
        ttg_pipeline=mock_ttg,
    )
    result = await pipeline.run(_instruction("3bhk apartment"))
    assert result.dkb_result is not None
    assert result.dkb_result.knowledge_id == "3bhk"


@pytest.mark.asyncio
async def test_run_result_domain_is_architecture():
    mock_ttg = _mock_ttg_pipeline()
    pipeline = DKBExecutionPipeline(
        dkb_runtime=_runtime(),
        bucket_urls=["https://bhiv-bucket.onrender.com/bucket/artifact/test"],
        ttg_pipeline=mock_ttg,
    )
    result = await pipeline.run(_instruction("3bhk apartment"))
    assert result.domain == "architecture"


@pytest.mark.asyncio
async def test_run_result_entity_matches_design_type():
    mock_ttg = _mock_ttg_pipeline()
    pipeline = DKBExecutionPipeline(
        dkb_runtime=_runtime(),
        bucket_urls=["https://bhiv-bucket.onrender.com/bucket/artifact/test"],
        ttg_pipeline=mock_ttg,
    )
    result = await pipeline.run(_instruction("3bhk apartment"))
    assert result.entity == "3bhk"


@pytest.mark.asyncio
async def test_run_result_execution_id_preserved():
    mock_ttg = _mock_ttg_pipeline(execution_id="exec_xyz999")
    pipeline = DKBExecutionPipeline(
        dkb_runtime=_runtime(),
        bucket_urls=["https://bhiv-bucket.onrender.com/bucket/artifact/test"],
        ttg_pipeline=mock_ttg,
    )
    result = await pipeline.run(_instruction("3bhk apartment"))
    assert result.execution_id == "exec_xyz999"


@pytest.mark.asyncio
async def test_run_result_bucket_url_set():
    mock_ttg = _mock_ttg_pipeline()
    pipeline = DKBExecutionPipeline(
        dkb_runtime=_runtime(),
        bucket_urls=["https://bhiv-bucket.onrender.com/bucket/artifact/test"],
        ttg_pipeline=mock_ttg,
    )
    result = await pipeline.run(_instruction("3bhk apartment"))
    assert result.bucket_url.startswith("https://")


@pytest.mark.asyncio
async def test_run_result_execution_status_completed():
    mock_ttg = _mock_ttg_pipeline(status="completed")
    pipeline = DKBExecutionPipeline(
        dkb_runtime=_runtime(),
        bucket_urls=["https://bhiv-bucket.onrender.com/bucket/artifact/test"],
        ttg_pipeline=mock_ttg,
    )
    result = await pipeline.run(_instruction("3bhk apartment"))
    assert result.execution_status == "completed"


@pytest.mark.asyncio
async def test_run_result_semantic_has_required_keys():
    mock_ttg = _mock_ttg_pipeline()
    pipeline = DKBExecutionPipeline(
        dkb_runtime=_runtime(),
        bucket_urls=["https://bhiv-bucket.onrender.com/bucket/artifact/test"],
        ttg_pipeline=mock_ttg,
    )
    result = await pipeline.run(_instruction("3bhk apartment"))
    for key in ("domain", "entity", "generation_mode", "geometry_family"):
        assert key in result.semantic, f"semantic missing key: {key}"


@pytest.mark.asyncio
async def test_run_trace_id_propagated():
    mock_ttg = _mock_ttg_pipeline()
    pipeline = DKBExecutionPipeline(
        dkb_runtime=_runtime(),
        bucket_urls=["https://bhiv-bucket.onrender.com/bucket/artifact/test"],
        ttg_pipeline=mock_ttg,
    )
    result = await pipeline.run(_instruction("3bhk apartment"), trace_id="trace_custom_001")
    assert result.trace_id == "trace_custom_001"


# ── run() — all 9 residential entries ────────────────────────────────────────

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


@pytest.mark.asyncio
@pytest.mark.parametrize("topic,expected_entity", _RESIDENTIAL_QUERIES)
async def test_run_all_residential_entries(topic, expected_entity):
    mock_ttg = _mock_ttg_pipeline()
    pipeline = DKBExecutionPipeline(
        dkb_runtime=_runtime(),
        bucket_urls=["https://bhiv-bucket.onrender.com/bucket/artifact/test"],
        ttg_pipeline=mock_ttg,
    )
    result = await pipeline.run(_instruction(topic))
    assert (
        result.entity == expected_entity
    ), f"Expected entity={expected_entity!r} for topic={topic!r}, got {result.entity!r}"


# ── run() — error paths ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_no_match_propagates():
    from app.design_knowledge.knowledge.search import KnowledgeSearchEngine, TFIDFSearchProvider
    from app.design_knowledge.runtime import DKBRuntimeNoMatchError

    engine = KnowledgeSearchEngine(TFIDFSearchProvider())
    engine.index([])  # empty index
    runtime = DKBRuntime(search_engine=engine)
    runtime._indexed = True

    pipeline = DKBExecutionPipeline(
        dkb_runtime=runtime,
        bucket_urls=["https://bucket.example.com"],
    )
    with pytest.raises(DKBRuntimeNoMatchError):
        await pipeline.run(_instruction("3bhk apartment"))


@pytest.mark.asyncio
async def test_run_ttg_failure_raises_pipeline_error():
    from app.services.ttg_generation_pipeline import TTGGenerationError

    mock_ttg = MagicMock()
    mock_ttg._step_payload.return_value = {}
    mock_ttg._step_execute = AsyncMock(side_effect=TTGGenerationError("TTG down"))

    pipeline = DKBExecutionPipeline(
        dkb_runtime=_runtime(),
        bucket_urls=["https://bucket.example.com"],
        ttg_pipeline=mock_ttg,
    )
    with pytest.raises(DKBExecutionPipelineError, match="TTG down"):
        await pipeline.run(_instruction("3bhk apartment"))


# ── DKBExecutionResult.to_dict() ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_result_to_dict_has_all_keys():
    mock_ttg = _mock_ttg_pipeline()
    pipeline = DKBExecutionPipeline(
        dkb_runtime=_runtime(),
        bucket_urls=["https://bhiv-bucket.onrender.com/bucket/artifact/test"],
        ttg_pipeline=mock_ttg,
    )
    result = await pipeline.run(_instruction("3bhk apartment"))
    d = result.to_dict()
    for key in (
        "trace_id",
        "execution_id",
        "domain",
        "entity",
        "bucket_url",
        "execution_status",
        "knowledge_id",
        "design_type",
        "spec_id",
        "valid",
        "validation_score",
        "semantic",
    ):
        assert key in d, f"to_dict() missing key: {key}"


@pytest.mark.asyncio
async def test_result_to_dict_knowledge_id_correct():
    mock_ttg = _mock_ttg_pipeline()
    pipeline = DKBExecutionPipeline(
        dkb_runtime=_runtime(),
        bucket_urls=["https://bhiv-bucket.onrender.com/bucket/artifact/test"],
        ttg_pipeline=mock_ttg,
    )
    result = await pipeline.run(_instruction("villa independent house"))
    assert result.to_dict()["knowledge_id"] == "villa"
