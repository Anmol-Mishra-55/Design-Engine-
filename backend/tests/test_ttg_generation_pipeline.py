"""
Unit tests for TTGGenerationPipeline
=====================================
Zero real network calls — all sub-components are injected as mocks.
Run with: pytest tests/test_ttg_generation_pipeline.py -v --noconftest
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.contracts.core_execution_response import CoreExecutionResponse
from app.services.core_gateway import CoreGatewayAuthError, CoreGatewayError
from app.services.ttg_client import TTGError, TTGExecutionResponse, TTGExecutionStatus, TTGTimeoutError
from app.services.ttg_generation_pipeline import (
    TTGGenerationAuthError,
    TTGGenerationError,
    TTGGenerationPipeline,
    TTGGenerationResult,
    TTGGenerationTimeoutError,
)

# ── Shared fixtures ───────────────────────────────────────────────────────────

SEMANTIC_DRONE = {
    "domain": "vehicle",
    "entity": "drone",
    "generation_mode": "mesh",
    "geometry_family": "rotorcraft",
}

SEMANTIC_2BHK = {
    "domain": "architecture",
    "entity": "2bhk",
    "generation_mode": "layout",
    "geometry_family": "apartment_layout",
}

SPEC_JSON = {"domain": "vehicle", "entity": "drone", "prompt": "Generate delivery drone"}
SPEC_JSON_2BHK = {"domain": "architecture", "entity": "2bhk", "prompt": "Generate 2BHK flat"}
BUCKET_URLS = ["https://bhiv-bucket.onrender.com/bucket/artifact/drone-001-glb"]
TRACE_ID = "trace-test-001"

EXEC_RESPONSE = TTGExecutionResponse(
    execution_id="exec-abc123",
    status="queued",
    message="Queued successfully",
)

EXEC_STATUS_COMPLETED = TTGExecutionStatus(
    execution_id="exec-abc123",
    status="completed",
    result={"output_url": "https://bhiv-bucket.onrender.com/bucket/artifact/drone-001-glb"},
)

EXEC_STATUS_RUNNING = TTGExecutionStatus(
    execution_id="exec-abc123",
    status="running",
)

EXEC_STATUS_FAILED = TTGExecutionStatus(
    execution_id="exec-abc123",
    status="failed",
    error="Generation failed: unsupported geometry",
)


def _make_gateway(semantic=None, raise_auth=False, raise_error=False):
    gw = MagicMock()
    if raise_auth:
        gw.run = AsyncMock(side_effect=CoreGatewayAuthError("Core rejected"))
    elif raise_error:
        gw.run = AsyncMock(side_effect=CoreGatewayError("PR failed"))
    else:
        sem = semantic or SEMANTIC_DRONE
        auth_resp = CoreExecutionResponse(task_id="task-001", agent_output={}, status="success", trace_id=TRACE_ID)
        gw.run = AsyncMock(
            return_value={
                "authorization": auth_resp,
                "prompt_runner": MagicMock(module="vehicle", topic="drone"),
                "semantic": sem,
            }
        )
    return gw


def _make_ttg_client(
    exec_response=None,
    statuses=None,
    execute_raises=None,
    poll_raises=None,
):
    client = MagicMock()
    client.execute = AsyncMock(
        return_value=exec_response or EXEC_RESPONSE,
        side_effect=execute_raises,
    )
    if statuses is not None:
        client.get_execution_status = AsyncMock(side_effect=statuses)
    elif poll_raises is not None:
        client.get_execution_status = AsyncMock(side_effect=poll_raises)
    else:
        client.get_execution_status = AsyncMock(return_value=EXEC_STATUS_COMPLETED)
    return client


def _make_pipeline(
    semantic=None,
    raise_auth=False,
    raise_gateway_error=False,
    exec_response=None,
    poll_statuses=None,
    execute_raises=None,
    poll_raises=None,
    poll_max=20,
):
    gw = _make_gateway(semantic, raise_auth, raise_gateway_error)
    ttg = _make_ttg_client(exec_response, poll_statuses, execute_raises, poll_raises)
    return (
        TTGGenerationPipeline(
            core_gateway=gw,
            ttg_client=ttg,
            poll_interval=0,  # no sleep in tests
            poll_max=poll_max,
        ),
        gw,
        ttg,
    )


# -- TestFullPipeline --


class TestFullPipeline:
    @pytest.mark.asyncio
    async def test_run_returns_ttg_generation_result(self):
        pipeline, _, _ = _make_pipeline()
        result = await pipeline.run(TRACE_ID[0], SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)
        assert isinstance(result, TTGGenerationResult)

    @pytest.mark.asyncio
    async def test_result_trace_id_preserved(self):
        pipeline, _, _ = _make_pipeline()
        result = await pipeline.run("Generate drone", SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)
        assert result.trace_id == TRACE_ID

    @pytest.mark.asyncio
    async def test_result_execution_id_from_ttg(self):
        pipeline, _, _ = _make_pipeline()
        result = await pipeline.run("Generate drone", SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)
        assert result.execution_id == "exec-abc123"

    @pytest.mark.asyncio
    async def test_result_domain_is_vehicle(self):
        pipeline, _, _ = _make_pipeline()
        result = await pipeline.run("Generate drone", SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)
        assert result.domain == "vehicle"

    @pytest.mark.asyncio
    async def test_result_entity_is_drone(self):
        pipeline, _, _ = _make_pipeline()
        result = await pipeline.run("Generate drone", SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)
        assert result.entity == "drone"

    @pytest.mark.asyncio
    async def test_result_execution_status_is_completed(self):
        pipeline, _, _ = _make_pipeline()
        result = await pipeline.run("Generate drone", SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)
        assert result.execution_status.status == "completed"

    @pytest.mark.asyncio
    async def test_bucket_record_created(self):
        pipeline, _, _ = _make_pipeline()
        result = await pipeline.run("Generate drone", SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)
        assert result.bucket_record is not None

    @pytest.mark.asyncio
    async def test_bucket_record_trace_id_matches(self):
        pipeline, _, _ = _make_pipeline()
        result = await pipeline.run("Generate drone", SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)
        assert result.bucket_record.trace_id == TRACE_ID

    @pytest.mark.asyncio
    async def test_bucket_record_execution_id_matches(self):
        pipeline, _, _ = _make_pipeline()
        result = await pipeline.run("Generate drone", SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)
        assert result.bucket_record.execution_id == "exec-abc123"

    @pytest.mark.asyncio
    async def test_bucket_record_bucket_url_matches(self):
        pipeline, _, _ = _make_pipeline()
        result = await pipeline.run("Generate drone", SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)
        assert result.bucket_record.bucket_url == BUCKET_URLS[0]

    @pytest.mark.asyncio
    async def test_to_dict_contains_all_keys(self):
        pipeline, _, _ = _make_pipeline()
        result = await pipeline.run("Generate drone", SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)
        d = result.to_dict()
        for key in ("trace_id", "execution_id", "domain", "entity", "status", "bucket_url"):
            assert key in d


# ── TestCoreAuthRejection ─────────────────────────────────────────────────────


class TestCoreAuthRejection:
    @pytest.mark.asyncio
    async def test_auth_error_raises_ttg_generation_auth_error(self):
        pipeline, _, _ = _make_pipeline(raise_auth=True)
        with pytest.raises(TTGGenerationAuthError):
            await pipeline.run("Generate drone", SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)

    @pytest.mark.asyncio
    async def test_auth_error_ttg_execute_never_called(self):
        pipeline, _, ttg = _make_pipeline(raise_auth=True)
        with pytest.raises(TTGGenerationAuthError):
            await pipeline.run("Generate drone", SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)
        ttg.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_gateway_error_raises_ttg_generation_error(self):
        pipeline, _, _ = _make_pipeline(raise_gateway_error=True)
        with pytest.raises(TTGGenerationError):
            await pipeline.run("Generate drone", SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)

    @pytest.mark.asyncio
    async def test_ttg_generation_auth_error_is_subclass_of_ttg_generation_error(self):
        assert issubclass(TTGGenerationAuthError, TTGGenerationError)

    @pytest.mark.asyncio
    async def test_auth_error_bucket_record_never_created(self):
        pipeline, _, ttg = _make_pipeline(raise_auth=True)
        with pytest.raises(TTGGenerationAuthError):
            await pipeline.run("Generate drone", SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)
        ttg.get_execution_status.assert_not_called()


# ── TestTTGExecuteFailure ─────────────────────────────────────────────────────


class TestTTGExecuteFailure:
    @pytest.mark.asyncio
    async def test_ttg_error_raises_ttg_generation_error(self):
        pipeline, _, _ = _make_pipeline(execute_raises=TTGError("TTG down"))
        with pytest.raises(TTGGenerationError):
            await pipeline.run("Generate drone", SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)

    @pytest.mark.asyncio
    async def test_ttg_timeout_raises_ttg_generation_error(self):
        pipeline, _, _ = _make_pipeline(execute_raises=TTGTimeoutError("timeout"))
        with pytest.raises(TTGGenerationError):
            await pipeline.run("Generate drone", SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)

    @pytest.mark.asyncio
    async def test_ttg_error_poll_never_called(self):
        pipeline, _, ttg = _make_pipeline(execute_raises=TTGError("TTG down"))
        with pytest.raises(TTGGenerationError):
            await pipeline.run("Generate drone", SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)
        ttg.get_execution_status.assert_not_called()


# ── TestPolling ───────────────────────────────────────────────────────────────


class TestPolling:
    @pytest.mark.asyncio
    async def test_polls_until_completed(self):
        statuses = [EXEC_STATUS_RUNNING, EXEC_STATUS_RUNNING, EXEC_STATUS_COMPLETED]
        pipeline, _, ttg = _make_pipeline(poll_statuses=statuses)
        result = await pipeline.run("Generate drone", SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)
        assert ttg.get_execution_status.call_count == 3
        assert result.execution_status.status == "completed"

    @pytest.mark.asyncio
    async def test_failed_status_raises_ttg_generation_error(self):
        pipeline, _, _ = _make_pipeline(poll_statuses=[EXEC_STATUS_FAILED])
        with pytest.raises(TTGGenerationError, match="failed"):
            await pipeline.run("Generate drone", SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)

    @pytest.mark.asyncio
    async def test_poll_timeout_raises_ttg_generation_timeout_error(self):
        # Never returns terminal status
        pipeline, _, _ = _make_pipeline(
            poll_statuses=[EXEC_STATUS_RUNNING] * 5,
            poll_max=3,
        )
        with pytest.raises(TTGGenerationTimeoutError):
            await pipeline.run("Generate drone", SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)

    @pytest.mark.asyncio
    async def test_timeout_error_is_subclass_of_ttg_generation_error(self):
        assert issubclass(TTGGenerationTimeoutError, TTGGenerationError)

    @pytest.mark.asyncio
    async def test_poll_error_raises_ttg_generation_error(self):
        pipeline, _, _ = _make_pipeline(poll_raises=TTGError("poll failed"))
        with pytest.raises(TTGGenerationError):
            await pipeline.run("Generate drone", SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)


# ── TestPipelineOrdering ──────────────────────────────────────────────────────


class TestPipelineOrdering:
    @pytest.mark.asyncio
    async def test_gateway_called_before_ttg_execute(self):
        call_order = []

        gw = MagicMock()

        async def gateway_run(*a, **kw):
            call_order.append("gateway")
            auth_resp = CoreExecutionResponse(task_id="t", agent_output={}, status="success", trace_id=TRACE_ID)
            return {"authorization": auth_resp, "prompt_runner": MagicMock(), "semantic": SEMANTIC_DRONE}

        gw.run = gateway_run

        ttg = MagicMock()

        async def ttg_execute(*a, **kw):
            call_order.append("ttg_execute")
            return EXEC_RESPONSE

        ttg.execute = ttg_execute
        ttg.get_execution_status = AsyncMock(return_value=EXEC_STATUS_COMPLETED)

        pipeline = TTGGenerationPipeline(core_gateway=gw, ttg_client=ttg, poll_interval=0)
        await pipeline.run("Generate drone", SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)

        assert call_order.index("gateway") < call_order.index("ttg_execute")

    @pytest.mark.asyncio
    async def test_execute_called_before_poll(self):
        call_order = []

        gw = _make_gateway()
        ttg = MagicMock()

        async def ttg_execute(*a, **kw):
            call_order.append("execute")
            return EXEC_RESPONSE

        async def ttg_poll(*a, **kw):
            call_order.append("poll")
            return EXEC_STATUS_COMPLETED

        ttg.execute = ttg_execute
        ttg.get_execution_status = ttg_poll

        pipeline = TTGGenerationPipeline(core_gateway=gw, ttg_client=ttg, poll_interval=0)
        await pipeline.run("Generate drone", SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)

        assert call_order.index("execute") < call_order.index("poll")


# ── TestArchitectureDomain ────────────────────────────────────────────────────


class TestArchitectureDomain:
    @pytest.mark.asyncio
    async def test_architecture_domain_resolves_correctly(self):
        pipeline, _, _ = _make_pipeline(semantic=SEMANTIC_2BHK)
        result = await pipeline.run("Generate 2BHK flat", SPEC_JSON_2BHK, BUCKET_URLS, trace_id=TRACE_ID)
        assert result.domain == "architecture"
        assert result.entity == "2bhk"

    @pytest.mark.asyncio
    async def test_architecture_asset_type_is_step(self):
        pipeline, _, _ = _make_pipeline(semantic=SEMANTIC_2BHK)
        result = await pipeline.run("Generate 2BHK flat", SPEC_JSON_2BHK, BUCKET_URLS, trace_id=TRACE_ID)
        assert result.bucket_record.asset_type == "step"

    @pytest.mark.asyncio
    async def test_vehicle_asset_type_is_glb(self):
        pipeline, _, _ = _make_pipeline()
        result = await pipeline.run("Generate drone", SPEC_JSON, BUCKET_URLS, trace_id=TRACE_ID)
        assert result.bucket_record.asset_type == "glb"
