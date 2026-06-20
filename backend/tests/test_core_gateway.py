"""
Integration tests for CoreGateway.
=====================================
Verifies:
  1. Full pipeline: Core auth → PromptRunner → SemanticResolver
  2. Core rejection  → PromptRunner is NEVER called
  3. Core error      → PromptRunner is NEVER called
  4. PromptRunner failure after auth → CoreGatewayError (not auth error)
  5. SemanticResolver failure        → CoreGatewayError
  6. Pipeline ordering guarantee     — Core always before PromptRunner

All external I/O is mocked. No real HTTP calls, no real filesystem reads
for semantic files (SemanticResolver is injected as a mock).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.contracts.core_execution_request import CoreExecutionRequest
from app.contracts.core_execution_response import CoreExecutionResponse
from app.design_semantics.semantic_resolver import SemanticResolutionError
from app.services.core_client import CoreError, CoreTimeoutError
from app.services.core_gateway import CoreGateway, CoreGatewayAuthError, CoreGatewayError
from app.services.prompt_runner_client import GenerateInstructionResponse, PromptRunnerError, PromptRunnerTimeoutError

# ── Fixtures ──────────────────────────────────────────────────────────────────

CORE_SUCCESS = CoreExecutionResponse(
    task_id="task_gw_001",
    trace_id="trace_gw_001",
    status="success",
    agent_output={"authorized": True},
)

CORE_REJECTED = CoreExecutionResponse(
    task_id="task_gw_002",
    trace_id="trace_gw_002",
    status="rejected",
    agent_output={"reason": "quota exceeded"},
)

CORE_FAILED = CoreExecutionResponse(
    task_id="task_gw_003",
    trace_id="trace_gw_003",
    status="failed",
    agent_output={"error": "internal error"},
)

PR_RAW = {
    "prompt": "Design a 2BHK flat",
    "module": "architecture",
    "intent": "design",
    "topic": "2bhk_flat",
    "tasks": ["floor_plan_design", "room_layout_planning"],
    "output_format": "step_by_step_guide",
    "product_context": "creator_core",
}
PR_RESPONSE = GenerateInstructionResponse(PR_RAW)

SEMANTIC_RESULT = {
    "domain": "architecture",
    "entity": "2bhk",
    "generation_mode": "layout",
    "geometry_family": "apartment_layout",
}

PR_RAW_VEHICLE = {
    "prompt": "Build a combat drone",
    "module": "vehicle",
    "intent": "design",
    "topic": "combat_drone",
    "tasks": ["mesh_generation"],
    "output_format": "step_by_step_guide",
    "product_context": "creator_core",
}
PR_RESPONSE_VEHICLE = GenerateInstructionResponse(PR_RAW_VEHICLE)

SEMANTIC_VEHICLE = {
    "domain": "vehicle",
    "entity": "drone",
    "generation_mode": "mesh",
    "geometry_family": "rotorcraft",
}


def make_gateway(
    core_response=CORE_SUCCESS,
    pr_response=PR_RESPONSE,
    semantic=SEMANTIC_RESULT,
    core_raises=None,
    pr_raises=None,
    semantic_raises=None,
) -> CoreGateway:
    """
    Build a CoreGateway with all dependencies mocked.
    """
    mock_core = MagicMock()
    if core_raises:
        mock_core.execute_task = AsyncMock(side_effect=core_raises)
    else:
        mock_core.execute_task = AsyncMock(return_value=core_response)

    mock_pr = MagicMock()
    if pr_raises:
        mock_pr.generate_instruction = AsyncMock(side_effect=pr_raises)
    else:
        mock_pr.generate_instruction = AsyncMock(return_value=pr_response)

    mock_resolver = MagicMock()
    if semantic_raises:
        mock_resolver.resolve = MagicMock(side_effect=semantic_raises)
    else:
        mock_resolver.resolve = MagicMock(return_value=semantic)

    return CoreGateway(
        core_client=mock_core,
        prompt_runner_client=mock_pr,
        semantic_resolver=mock_resolver,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 1. Full happy-path pipeline
# ══════════════════════════════════════════════════════════════════════════════


class TestFullPipeline:
    @pytest.mark.asyncio
    async def test_run_returns_all_three_keys(self):
        gw = make_gateway()
        result = await gw.run("Design a 2BHK flat", trace_id="trace_001")
        assert "authorization" in result
        assert "prompt_runner" in result
        assert "semantic" in result

    @pytest.mark.asyncio
    async def test_authorization_is_core_response(self):
        gw = make_gateway()
        result = await gw.run("Design a 2BHK flat", trace_id="trace_001")
        assert isinstance(result["authorization"], CoreExecutionResponse)
        assert result["authorization"].status == "success"

    @pytest.mark.asyncio
    async def test_prompt_runner_is_generate_instruction_response(self):
        gw = make_gateway()
        result = await gw.run("Design a 2BHK flat", trace_id="trace_001")
        assert isinstance(result["prompt_runner"], GenerateInstructionResponse)
        assert result["prompt_runner"].module == "architecture"

    @pytest.mark.asyncio
    async def test_semantic_contains_expected_keys(self):
        gw = make_gateway()
        result = await gw.run("Design a 2BHK flat", trace_id="trace_001")
        sem = result["semantic"]
        assert sem["domain"] == "architecture"
        assert sem["entity"] == "2bhk"
        assert sem["generation_mode"] == "layout"
        assert sem["geometry_family"] == "apartment_layout"

    @pytest.mark.asyncio
    async def test_vehicle_pipeline(self):
        gw = make_gateway(pr_response=PR_RESPONSE_VEHICLE, semantic=SEMANTIC_VEHICLE)
        result = await gw.run("Build a combat drone", trace_id="trace_002")
        assert result["semantic"]["domain"] == "vehicle"
        assert result["semantic"]["entity"] == "drone"
        assert result["semantic"]["generation_mode"] == "mesh"

    @pytest.mark.asyncio
    async def test_trace_id_propagated_to_core_request(self):
        mock_core = MagicMock()
        captured = {}

        async def capture_execute(req: CoreExecutionRequest):
            captured["trace_id"] = req.trace_id
            return CORE_SUCCESS

        mock_core.execute_task = capture_execute
        mock_pr = MagicMock()
        mock_pr.generate_instruction = AsyncMock(return_value=PR_RESPONSE)
        mock_resolver = MagicMock()
        mock_resolver.resolve = MagicMock(return_value=SEMANTIC_RESULT)

        gw = CoreGateway(core_client=mock_core, prompt_runner_client=mock_pr, semantic_resolver=mock_resolver)
        await gw.run("Design a flat", trace_id="trace_custom_99")
        assert captured["trace_id"] == "trace_custom_99"

    @pytest.mark.asyncio
    async def test_trace_id_autogenerated_when_not_provided(self):
        gw = make_gateway()
        result = await gw.run("Design a flat")
        assert result["authorization"].trace_id is not None

    @pytest.mark.asyncio
    async def test_core_called_with_authorization_agent(self):
        mock_core = MagicMock()
        captured = {}

        async def capture_execute(req: CoreExecutionRequest):
            captured["agent"] = req.agent
            return CORE_SUCCESS

        mock_core.execute_task = capture_execute
        mock_pr = MagicMock()
        mock_pr.generate_instruction = AsyncMock(return_value=PR_RESPONSE)
        mock_resolver = MagicMock()
        mock_resolver.resolve = MagicMock(return_value=SEMANTIC_RESULT)

        gw = CoreGateway(core_client=mock_core, prompt_runner_client=mock_pr, semantic_resolver=mock_resolver)
        await gw.run("Design a flat", trace_id="trace_001")
        assert captured["agent"] == CoreGateway._AUTHORIZATION_AGENT


# ══════════════════════════════════════════════════════════════════════════════
# 2. Core rejection blocks Prompt Runner — KEY INVARIANT
# ══════════════════════════════════════════════════════════════════════════════


class TestCoreRejectionBlocksPromptRunner:
    @pytest.mark.asyncio
    async def test_rejected_status_raises_auth_error(self):
        gw = make_gateway(core_response=CORE_REJECTED)
        with pytest.raises(CoreGatewayAuthError):
            await gw.run("Design a flat", trace_id="trace_001")

    @pytest.mark.asyncio
    async def test_failed_status_raises_auth_error(self):
        gw = make_gateway(core_response=CORE_FAILED)
        with pytest.raises(CoreGatewayAuthError):
            await gw.run("Design a flat", trace_id="trace_001")

    @pytest.mark.asyncio
    async def test_prompt_runner_never_called_on_rejection(self):
        mock_pr = MagicMock()
        mock_pr.generate_instruction = AsyncMock(return_value=PR_RESPONSE)
        mock_core = MagicMock()
        mock_core.execute_task = AsyncMock(return_value=CORE_REJECTED)
        mock_resolver = MagicMock()

        gw = CoreGateway(core_client=mock_core, prompt_runner_client=mock_pr, semantic_resolver=mock_resolver)

        with pytest.raises(CoreGatewayAuthError):
            await gw.run("Design a flat", trace_id="trace_001")

        mock_pr.generate_instruction.assert_not_called()

    @pytest.mark.asyncio
    async def test_prompt_runner_never_called_on_failed(self):
        mock_pr = MagicMock()
        mock_pr.generate_instruction = AsyncMock(return_value=PR_RESPONSE)
        mock_core = MagicMock()
        mock_core.execute_task = AsyncMock(return_value=CORE_FAILED)
        mock_resolver = MagicMock()

        gw = CoreGateway(core_client=mock_core, prompt_runner_client=mock_pr, semantic_resolver=mock_resolver)

        with pytest.raises(CoreGatewayAuthError):
            await gw.run("Design a flat", trace_id="trace_001")

        mock_pr.generate_instruction.assert_not_called()

    @pytest.mark.asyncio
    async def test_auth_error_carries_core_response(self):
        gw = make_gateway(core_response=CORE_REJECTED)
        with pytest.raises(CoreGatewayAuthError) as exc_info:
            await gw.run("Design a flat", trace_id="trace_001")
        assert exc_info.value.core_response is not None
        assert exc_info.value.core_response.status == "rejected"

    @pytest.mark.asyncio
    async def test_semantic_resolver_never_called_on_rejection(self):
        mock_pr = MagicMock()
        mock_pr.generate_instruction = AsyncMock(return_value=PR_RESPONSE)
        mock_core = MagicMock()
        mock_core.execute_task = AsyncMock(return_value=CORE_REJECTED)
        mock_resolver = MagicMock()
        mock_resolver.resolve = MagicMock(return_value=SEMANTIC_RESULT)

        gw = CoreGateway(core_client=mock_core, prompt_runner_client=mock_pr, semantic_resolver=mock_resolver)

        with pytest.raises(CoreGatewayAuthError):
            await gw.run("Design a flat", trace_id="trace_001")

        mock_resolver.resolve.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# 3. Core raises exception (network/timeout)
# ══════════════════════════════════════════════════════════════════════════════


class TestCoreExceptionBlocksPromptRunner:
    @pytest.mark.asyncio
    async def test_core_error_raises_auth_error(self):
        gw = make_gateway(core_raises=CoreError("network failure"))
        with pytest.raises(CoreGatewayAuthError):
            await gw.run("Design a flat", trace_id="trace_001")

    @pytest.mark.asyncio
    async def test_core_timeout_raises_auth_error(self):
        gw = make_gateway(core_raises=CoreTimeoutError("timed out"))
        with pytest.raises(CoreGatewayAuthError):
            await gw.run("Design a flat", trace_id="trace_001")

    @pytest.mark.asyncio
    async def test_prompt_runner_not_called_on_core_exception(self):
        mock_pr = MagicMock()
        mock_pr.generate_instruction = AsyncMock(return_value=PR_RESPONSE)
        mock_core = MagicMock()
        mock_core.execute_task = AsyncMock(side_effect=CoreError("down"))
        mock_resolver = MagicMock()

        gw = CoreGateway(core_client=mock_core, prompt_runner_client=mock_pr, semantic_resolver=mock_resolver)

        with pytest.raises(CoreGatewayAuthError):
            await gw.run("Design a flat", trace_id="trace_001")

        mock_pr.generate_instruction.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# 4. PromptRunner failure after successful auth
# ══════════════════════════════════════════════════════════════════════════════


class TestPromptRunnerFailureAfterAuth:
    @pytest.mark.asyncio
    async def test_prompt_runner_error_raises_gateway_error(self):
        gw = make_gateway(pr_raises=PromptRunnerError("PR down"))
        with pytest.raises(CoreGatewayError):
            await gw.run("Design a flat", trace_id="trace_001")

    @pytest.mark.asyncio
    async def test_prompt_runner_timeout_raises_gateway_error(self):
        gw = make_gateway(pr_raises=PromptRunnerTimeoutError("PR timeout"))
        with pytest.raises(CoreGatewayError):
            await gw.run("Design a flat", trace_id="trace_001")

    @pytest.mark.asyncio
    async def test_prompt_runner_error_is_not_auth_error(self):
        gw = make_gateway(pr_raises=PromptRunnerError("PR down"))
        with pytest.raises(CoreGatewayError) as exc_info:
            await gw.run("Design a flat", trace_id="trace_001")
        assert not isinstance(exc_info.value, CoreGatewayAuthError)


# ══════════════════════════════════════════════════════════════════════════════
# 5. SemanticResolver failure
# ══════════════════════════════════════════════════════════════════════════════


class TestSemanticResolverFailure:
    @pytest.mark.asyncio
    async def test_semantic_error_raises_gateway_error(self):
        gw = make_gateway(semantic_raises=SemanticResolutionError("unknown module"))
        with pytest.raises(CoreGatewayError):
            await gw.run("Design a flat", trace_id="trace_001")

    @pytest.mark.asyncio
    async def test_semantic_error_is_not_auth_error(self):
        gw = make_gateway(semantic_raises=SemanticResolutionError("unknown module"))
        with pytest.raises(CoreGatewayError) as exc_info:
            await gw.run("Design a flat", trace_id="trace_001")
        assert not isinstance(exc_info.value, CoreGatewayAuthError)


# ══════════════════════════════════════════════════════════════════════════════
# 6. Pipeline ordering guarantees
# ══════════════════════════════════════════════════════════════════════════════


class TestPipelineOrdering:
    @pytest.mark.asyncio
    async def test_core_called_before_prompt_runner(self):
        call_order = []

        async def core_execute(req):
            call_order.append("core")
            return CORE_SUCCESS

        async def pr_generate(prompt, model=None):
            call_order.append("prompt_runner")
            return PR_RESPONSE

        mock_core = MagicMock()
        mock_core.execute_task = core_execute
        mock_pr = MagicMock()
        mock_pr.generate_instruction = pr_generate
        mock_resolver = MagicMock()
        mock_resolver.resolve = MagicMock(return_value=SEMANTIC_RESULT)

        gw = CoreGateway(core_client=mock_core, prompt_runner_client=mock_pr, semantic_resolver=mock_resolver)
        await gw.run("Design a flat", trace_id="trace_order_001")

        assert call_order == ["core", "prompt_runner"]

    @pytest.mark.asyncio
    async def test_prompt_runner_called_before_resolver(self):
        call_order = []

        async def core_execute(req):
            call_order.append("core")
            return CORE_SUCCESS

        async def pr_generate(prompt, model=None):
            call_order.append("prompt_runner")
            return PR_RESPONSE

        def resolver_resolve(data):
            call_order.append("resolver")
            return SEMANTIC_RESULT

        mock_core = MagicMock()
        mock_core.execute_task = core_execute
        mock_pr = MagicMock()
        mock_pr.generate_instruction = pr_generate
        mock_resolver = MagicMock()
        mock_resolver.resolve = resolver_resolve

        gw = CoreGateway(core_client=mock_core, prompt_runner_client=mock_pr, semantic_resolver=mock_resolver)
        await gw.run("Design a flat", trace_id="trace_order_002")

        assert call_order == ["core", "prompt_runner", "resolver"]

    @pytest.mark.asyncio
    async def test_core_called_exactly_once_per_run(self):
        mock_core = MagicMock()
        mock_core.execute_task = AsyncMock(return_value=CORE_SUCCESS)
        mock_pr = MagicMock()
        mock_pr.generate_instruction = AsyncMock(return_value=PR_RESPONSE)
        mock_resolver = MagicMock()
        mock_resolver.resolve = MagicMock(return_value=SEMANTIC_RESULT)

        gw = CoreGateway(core_client=mock_core, prompt_runner_client=mock_pr, semantic_resolver=mock_resolver)
        await gw.run("Design a flat", trace_id="trace_001")

        assert mock_core.execute_task.call_count == 1

    @pytest.mark.asyncio
    async def test_prompt_runner_called_exactly_once_per_run(self):
        mock_core = MagicMock()
        mock_core.execute_task = AsyncMock(return_value=CORE_SUCCESS)
        mock_pr = MagicMock()
        mock_pr.generate_instruction = AsyncMock(return_value=PR_RESPONSE)
        mock_resolver = MagicMock()
        mock_resolver.resolve = MagicMock(return_value=SEMANTIC_RESULT)

        gw = CoreGateway(core_client=mock_core, prompt_runner_client=mock_pr, semantic_resolver=mock_resolver)
        await gw.run("Design a flat", trace_id="trace_001")

        assert mock_pr.generate_instruction.call_count == 1


# ══════════════════════════════════════════════════════════════════════════════
# 7. Exception hierarchy
# ══════════════════════════════════════════════════════════════════════════════


class TestExceptionHierarchy:
    def test_auth_error_is_gateway_error(self):
        assert issubclass(CoreGatewayAuthError, CoreGatewayError)

    def test_gateway_error_is_exception(self):
        assert issubclass(CoreGatewayError, Exception)

    def test_auth_error_stores_core_response(self):
        err = CoreGatewayAuthError("rejected", core_response=CORE_REJECTED)
        assert err.core_response is CORE_REJECTED

    def test_auth_error_without_response(self):
        err = CoreGatewayAuthError("network down")
        assert err.core_response is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
