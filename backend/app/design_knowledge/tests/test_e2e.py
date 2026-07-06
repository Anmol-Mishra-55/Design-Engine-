"""
Task 10 — End-to-End Integration Tests

These tests verify the complete execution path from a raw Prompt Runner
response through to a DKBExecutionResult.  They are NOT unit tests.

Every test exercises the full chain:
    PromptInstruction
        → DKBRuntime (search → compile → validate)
        → DKBExecutionPipeline (semantic mapping → spec_json → TTG steps)
        → DKBExecutionResult

TTG network calls are mocked at the TTGGenerationPipeline boundary.
No real HTTP is made.  All DKB data files are read from disk.

Coverage
────────
  Prompt → Studio → Success
  Prompt → Villa → Success
  Prompt → Penthouse → Success
  Invalid prompt → No match
  Invalid specification → Validation failure (valid=False, not exception)
  TTG failure → Pipeline error propagation
  Trace ID preserved through every stage
  Execution ID preserved
  Bucket URL returned
  Validation report included
  to_dict() serialization
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.design_knowledge.knowledge.search import KnowledgeSearchEngine, TFIDFSearchProvider
from app.design_knowledge.runtime import (
    DKBExecutionPipeline,
    DKBExecutionPipelineError,
    DKBExecutionResult,
    DKBRuntime,
    PromptInstruction,
)
from app.design_knowledge.runtime.exceptions import DKBRuntimeNoMatchError

_RESIDENTIAL_DIR = Path(__file__).parent.parent / "data" / "residential"

_BUCKET_URL = "https://bhiv-bucket.onrender.com/bucket/artifact/e2e-test"


# ── Shared helpers ────────────────────────────────────────────────────────────


def _prompt(topic: str, module: str = "architecture", intent: str = "generate") -> PromptInstruction:
    """Build a PromptInstruction the same way Prompt Runner output would produce it."""
    return PromptInstruction.from_prompt_runner(
        {
            "module": module,
            "intent": intent,
            "topic": topic,
            "tasks": ["generate_layout", "validate_spaces"],
            "output_format": "3d_model",
            "product_context": "creator_core",
        }
    )


def _mock_ttg(execution_id: str = "exec_e2e_001", status: str = "completed") -> MagicMock:
    """
    Return a fully mocked TTGGenerationPipeline.

    Mirrors the mock helper in test_pipeline.py so the e2e tests use the
    same TTG boundary contract without duplicating infrastructure.
    """
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
        result={"glb_url": f"https://bucket.example.com/{execution_id}.glb"},
    )
    bucket_record = BucketAssetRecord.create(
        trace_id="trace_e2e",
        execution_id=execution_id,
        bucket_url=_BUCKET_URL,
        asset_type="step",
        asset_name="e2e_asset",
        payload_hash="e2ehash",
    )

    mock = MagicMock()
    mock._step_payload.return_value = {"execution_id": execution_id, "trace_id": "t"}
    mock._step_execute = AsyncMock(return_value=exec_response)
    mock._step_poll = AsyncMock(return_value=exec_status)
    mock._step_record.return_value = bucket_record
    return mock


def _pipeline(ttg=None) -> DKBExecutionPipeline:
    """Build a DKBExecutionPipeline loaded from the residential DKB directory."""
    return DKBExecutionPipeline.from_directory(
        directory=_RESIDENTIAL_DIR,
        bucket_urls=[_BUCKET_URL],
        ttg_pipeline=ttg or _mock_ttg(),
    )


# ── Prompt → Studio → Success ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_studio_success():
    result = await _pipeline().run(_prompt("studio apartment single room compact"))
    assert isinstance(result, DKBExecutionResult)
    assert result.entity == "studio"
    assert result.domain == "architecture"
    assert result.execution_status == "completed"


@pytest.mark.asyncio
async def test_e2e_studio_dkb_result_valid():
    result = await _pipeline().run(_prompt("studio apartment single room compact"))
    assert result.dkb_result is not None
    assert result.dkb_result.knowledge_id == "studio"


@pytest.mark.asyncio
async def test_e2e_studio_validation_report_included():
    result = await _pipeline().run(_prompt("studio apartment single room compact"))
    report = result.dkb_result.validation_report
    assert report is not None
    assert report.spec_id is not None
    assert isinstance(report.score, float)


# ── Prompt → Villa → Success ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_villa_success():
    result = await _pipeline().run(_prompt("villa independent house garden bungalow"))
    assert isinstance(result, DKBExecutionResult)
    assert result.entity == "villa"
    assert result.domain == "architecture"
    assert result.execution_status == "completed"


@pytest.mark.asyncio
async def test_e2e_villa_design_spec_compiled():
    result = await _pipeline().run(_prompt("villa independent house garden bungalow"))
    spec = result.dkb_result.design_specification
    assert spec is not None
    assert spec.design_type == "villa"
    assert len(spec.spaces) > 0


@pytest.mark.asyncio
async def test_e2e_villa_validation_report_included():
    result = await _pipeline().run(_prompt("villa independent house garden bungalow"))
    report = result.dkb_result.validation_report
    assert report is not None
    assert report.spec_id == result.dkb_result.design_specification.spec_id


# ── Prompt → Penthouse → Success ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_penthouse_success():
    result = await _pipeline().run(_prompt("penthouse top floor terrace luxury sky"))
    assert isinstance(result, DKBExecutionResult)
    assert result.entity == "penthouse"
    assert result.domain == "architecture"
    assert result.execution_status == "completed"


@pytest.mark.asyncio
async def test_e2e_penthouse_dkb_result_valid():
    result = await _pipeline().run(_prompt("penthouse top floor terrace luxury sky"))
    assert result.dkb_result.knowledge_id == "penthouse"


@pytest.mark.asyncio
async def test_e2e_penthouse_validation_report_included():
    result = await _pipeline().run(_prompt("penthouse top floor terrace luxury sky"))
    report = result.dkb_result.validation_report
    assert report is not None
    assert isinstance(report.score, float)
    assert 0.0 <= report.score <= 1.0


# ── Invalid prompt → No match ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_invalid_prompt_no_match():
    """
    A topic with no resemblance to any DKB entry must raise DKBRuntimeNoMatchError.
    The pipeline must not silently return a wrong result.
    """
    engine = KnowledgeSearchEngine(TFIDFSearchProvider())
    engine.index([])  # empty index — guaranteed no match
    runtime = DKBRuntime(search_engine=engine)
    runtime._indexed = True

    pipeline = DKBExecutionPipeline(
        dkb_runtime=runtime,
        bucket_urls=[_BUCKET_URL],
        ttg_pipeline=_mock_ttg(),
    )
    with pytest.raises(DKBRuntimeNoMatchError):
        await pipeline.run(_prompt("xyzzy quantum refrigerator blockchain"))


@pytest.mark.asyncio
async def test_e2e_empty_topic_raises():
    """from_prompt_runner must reject a missing topic before the pipeline runs."""
    with pytest.raises(ValueError, match="topic"):
        PromptInstruction.from_prompt_runner(
            {
                "module": "architecture",
                "intent": "generate",
                "topic": "",
            }
        )


# ── Invalid specification → Validation failure ────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_validation_failure_is_result_not_exception():
    """
    A spec that fails validation rules must return a DKBRuntimeResult with
    valid=False — it must NOT raise an exception.  Validation failure is a
    data outcome, not a pipeline crash.
    """
    from datetime import datetime
    from unittest.mock import patch

    import app.design_knowledge.validation.engine as _engine_module
    from app.design_knowledge.validation.models import ValidationFinding, ValidationReport

    class _AlwaysFailValidator:
        def validate(self, spec):
            finding = ValidationFinding(
                rule_id="e2e_forced_failure",
                passed=False,
                severity="error",
                message="Forced failure for e2e test",
                validator="AlwaysFailValidator",
            )
            return [finding]

    with patch.dict(_engine_module.VALIDATOR_REGISTRY, {"residential": _AlwaysFailValidator}):
        runtime = DKBRuntime.from_directory(_RESIDENTIAL_DIR)
        pipeline = DKBExecutionPipeline(
            dkb_runtime=runtime,
            bucket_urls=[_BUCKET_URL],
            ttg_pipeline=_mock_ttg(),
        )
        result = await pipeline.run(_prompt("3bhk three bedroom family apartment"))

    # Pipeline completes — no exception raised
    assert isinstance(result, DKBExecutionResult)
    # Validation report reflects the failure
    assert result.dkb_result.valid is False
    assert len(result.dkb_result.validation_report.errors) > 0


# ── TTG failure → Pipeline error propagation ──────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_ttg_execute_failure_raises_pipeline_error():
    """
    A TTG network failure during _step_execute must surface as
    DKBExecutionPipelineError — not swallowed or re-raised as a raw TTG error.
    """
    from app.services.ttg_generation_pipeline import TTGGenerationError

    mock_ttg = MagicMock()
    mock_ttg._step_payload.return_value = {}
    mock_ttg._step_execute = AsyncMock(side_effect=TTGGenerationError("TTG service unavailable"))

    pipeline = DKBExecutionPipeline(
        dkb_runtime=DKBRuntime.from_directory(_RESIDENTIAL_DIR),
        bucket_urls=[_BUCKET_URL],
        ttg_pipeline=mock_ttg,
    )
    with pytest.raises(DKBExecutionPipelineError, match="TTG service unavailable"):
        await pipeline.run(_prompt("3bhk three bedroom family apartment"))


@pytest.mark.asyncio
async def test_e2e_ttg_poll_failure_raises_pipeline_error():
    """A TTG polling failure must also surface as DKBExecutionPipelineError."""
    from app.services.ttg_client import TTGExecutionResponse
    from app.services.ttg_generation_pipeline import TTGGenerationTimeoutError

    mock_ttg = MagicMock()
    mock_ttg._step_payload.return_value = {}
    mock_ttg._step_execute = AsyncMock(
        return_value=TTGExecutionResponse(execution_id="exec_timeout", status="accepted", message="queued")
    )
    mock_ttg._step_poll = AsyncMock(side_effect=TTGGenerationTimeoutError("Polling timed out after 20 attempts"))

    pipeline = DKBExecutionPipeline(
        dkb_runtime=DKBRuntime.from_directory(_RESIDENTIAL_DIR),
        bucket_urls=[_BUCKET_URL],
        ttg_pipeline=mock_ttg,
    )
    with pytest.raises(DKBExecutionPipelineError, match="Polling timed out"):
        await pipeline.run(_prompt("2bhk two bedroom apartment"))


# ── Trace ID preserved through every stage ────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_trace_id_preserved():
    """A caller-supplied trace_id must appear unchanged in DKBExecutionResult."""
    trace = "trace_e2e_sprint2_qa_001"
    result = await _pipeline().run(_prompt("3bhk three bedroom family apartment"), trace_id=trace)
    assert result.trace_id == trace


@pytest.mark.asyncio
async def test_e2e_trace_id_auto_generated_when_not_supplied():
    """When no trace_id is supplied, one must be auto-generated and non-empty."""
    result = await _pipeline().run(_prompt("1bhk one bedroom hall kitchen"))
    assert result.trace_id
    assert result.trace_id.startswith("trace_")


@pytest.mark.asyncio
async def test_e2e_trace_id_unique_per_run():
    """Two runs without an explicit trace_id must produce different trace IDs."""
    pipeline = _pipeline()
    r1 = await pipeline.run(_prompt("studio apartment"))
    r2 = await pipeline.run(_prompt("studio apartment"))
    assert r1.trace_id != r2.trace_id


# ── Execution ID preserved ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_execution_id_preserved():
    """The execution_id returned by TTG must be preserved in DKBExecutionResult."""
    mock_ttg = _mock_ttg(execution_id="exec_preserved_abc")
    result = await _pipeline(ttg=mock_ttg).run(_prompt("villa independent house"))
    assert result.execution_id == "exec_preserved_abc"


@pytest.mark.asyncio
async def test_e2e_execution_id_in_to_dict():
    """execution_id must appear in to_dict() output."""
    mock_ttg = _mock_ttg(execution_id="exec_dict_check")
    result = await _pipeline(ttg=mock_ttg).run(_prompt("penthouse luxury top floor"))
    assert result.to_dict()["execution_id"] == "exec_dict_check"


# ── Bucket URL returned ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_bucket_url_returned():
    """DKBExecutionResult must carry a non-empty bucket_url."""
    result = await _pipeline().run(_prompt("3bhk three bedroom family apartment"))
    assert result.bucket_url
    assert result.bucket_url.startswith("https://")


@pytest.mark.asyncio
async def test_e2e_bucket_url_matches_configured_url():
    """bucket_url in the result must match the URL configured on the pipeline."""
    result = await _pipeline().run(_prompt("2bhk two bedroom apartment"))
    assert result.bucket_url == _BUCKET_URL


@pytest.mark.asyncio
async def test_e2e_bucket_url_in_to_dict():
    """bucket_url must appear in to_dict() output."""
    result = await _pipeline().run(_prompt("1bhk one bedroom hall kitchen"))
    assert "bucket_url" in result.to_dict()
    assert result.to_dict()["bucket_url"].startswith("https://")


# ── Validation report included ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_validation_report_present():
    """Every successful run must include a ValidationReport."""
    result = await _pipeline().run(_prompt("4bhk four bedroom large apartment"))
    assert result.dkb_result.validation_report is not None


@pytest.mark.asyncio
async def test_e2e_validation_report_score_in_range():
    """Validation score must be a float in [0.0, 1.0]."""
    result = await _pipeline().run(_prompt("duplex two floor split level"))
    score = result.dkb_result.validation_report.score
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


@pytest.mark.asyncio
async def test_e2e_validation_report_spec_id_matches():
    """ValidationReport.spec_id must match the compiled DesignSpecification.spec_id."""
    result = await _pipeline().run(_prompt("1rk room kitchen compact"))
    spec_id = result.dkb_result.design_specification.spec_id
    report_spec_id = result.dkb_result.validation_report.spec_id
    assert spec_id == report_spec_id


@pytest.mark.asyncio
async def test_e2e_validation_report_in_to_dict():
    """to_dict() must include valid and validation_score from the report."""
    result = await _pipeline().run(_prompt("3bhk three bedroom family apartment"))
    d = result.to_dict()
    assert "valid" in d
    assert "validation_score" in d
    assert isinstance(d["validation_score"], float)


# ── to_dict() serialization ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_to_dict_all_required_keys():
    """to_dict() must contain every key the API contract requires."""
    result = await _pipeline().run(_prompt("3bhk three bedroom family apartment"))
    d = result.to_dict()
    required = {
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
    }
    missing = required - d.keys()
    assert not missing, f"to_dict() missing keys: {missing}"


@pytest.mark.asyncio
async def test_e2e_to_dict_semantic_has_required_keys():
    """The semantic sub-dict in to_dict() must have all four TTG fields."""
    result = await _pipeline().run(_prompt("villa independent house garden"))
    semantic = result.to_dict()["semantic"]
    for key in ("domain", "entity", "generation_mode", "geometry_family"):
        assert key in semantic, f"semantic missing key: {key}"


@pytest.mark.asyncio
async def test_e2e_to_dict_values_are_correct_types():
    """to_dict() values must have the correct Python types."""
    result = await _pipeline().run(_prompt("penthouse top floor terrace luxury"))
    d = result.to_dict()
    assert isinstance(d["trace_id"], str)
    assert isinstance(d["execution_id"], str)
    assert isinstance(d["domain"], str)
    assert isinstance(d["entity"], str)
    assert isinstance(d["bucket_url"], str)
    assert isinstance(d["execution_status"], str)
    assert isinstance(d["knowledge_id"], str)
    assert isinstance(d["design_type"], str)
    assert isinstance(d["spec_id"], str)
    assert isinstance(d["valid"], bool)
    assert isinstance(d["validation_score"], float)
    assert isinstance(d["semantic"], dict)


@pytest.mark.asyncio
async def test_e2e_to_dict_is_json_serializable():
    """to_dict() output must be serializable to JSON without errors."""
    import json

    result = await _pipeline().run(_prompt("studio apartment single room"))
    d = result.to_dict()
    serialized = json.dumps(d)
    assert isinstance(serialized, str)
    assert len(serialized) > 0
