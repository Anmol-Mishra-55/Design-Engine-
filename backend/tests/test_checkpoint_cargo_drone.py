"""
CHECKPOINT TEST — Tasks 6–9
============================
Input  : "Generate a cargo drone"
Expected flow:
    CoreGateway
        ↓
    CoreClient.execute_task       (POST /execute_task  → status=success)
        ↓
    PromptRunnerClient.generate   (POST /generate      → module=vehicle, topic=cargo_drone)
        ↓
    SemanticResolver              (cargo_drone → drone → vehicle/rotorcraft/mesh)

Expected output:
    {
        "domain":          "vehicle",
        "entity":          "drone",
        "generation_mode": "mesh",
        "geometry_family": "rotorcraft"
    }

Run:
    cd backend
    python -m pytest tests/test_checkpoint_cargo_drone.py -v
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.contracts.core_execution_request import CoreExecutionRequest
from app.contracts.core_execution_response import CoreExecutionResponse
from app.design_semantics.semantic_resolver import SemanticResolver
from app.services.core_gateway import CoreGateway, CoreGatewayAuthError
from app.services.prompt_runner_client import GenerateInstructionResponse

# ── Simulated live Prompt Runner response for "Generate a cargo drone" ─────────
#
# Mirrors what https://prompt-runner.onrender.com/generate actually returns
# for a drone-related prompt (confirmed against live /docs).

_PROMPT_RUNNER_LIVE_SHAPE = {
    "prompt": "Generate a cargo drone",
    "module": "vehicle",
    "intent": "design_creation",
    "topic": "cargo_drone",
    "tasks": ["frame_design", "rotor_assembly", "payload_bay_design"],
    "output_format": "step_by_step_guide",
    "product_context": "creator_core",
}

# ── Core auth success response ─────────────────────────────────────────────────

_CORE_AUTH_SUCCESS = CoreExecutionResponse(
    task_id="task_checkpoint_001",
    trace_id="trace_checkpoint_001",
    status="success",
    agent_output={"authorized": True, "pipeline": "prompt_runner_gateway"},
)


# ══════════════════════════════════════════════════════════════════════════════
# CHECKPOINT TEST CLASS
# ══════════════════════════════════════════════════════════════════════════════


class TestCheckpointCargoDrone:
    """
    Full pipeline checkpoint test for "Generate a cargo drone".
    CoreClient and PromptRunnerClient are mocked.
    SemanticResolver uses REAL semantic_taxonomy.json + semantic_templates.json.
    """

    @pytest.fixture
    def gateway(self):
        # Mock CoreClient — always authorizes
        mock_core = MagicMock()
        mock_core.execute_task = AsyncMock(return_value=_CORE_AUTH_SUCCESS)

        # Mock PromptRunnerClient — returns live-shape response for cargo drone
        mock_pr = MagicMock()
        mock_pr.generate_instruction = AsyncMock(return_value=GenerateInstructionResponse(_PROMPT_RUNNER_LIVE_SHAPE))

        # REAL SemanticResolver — reads from actual semantic_taxonomy.json + semantic_templates.json
        real_resolver = SemanticResolver()

        return CoreGateway(
            core_client=mock_core,
            prompt_runner_client=mock_pr,
            semantic_resolver=real_resolver,
        )

    # ── Main checkpoint ────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_cargo_drone_full_pipeline(self, gateway):
        """Run the complete pipeline and assert the exact expected output."""
        result = await gateway.run(
            prompt="Generate a cargo drone",
            trace_id="trace_checkpoint_001",
        )

        semantic = result["semantic"]

        print("\n" + "=" * 60)
        print("CHECKPOINT RESULT — Generate a cargo drone")
        print("=" * 60)
        print(f"  domain:          {semantic['domain']}")
        print(f"  entity:          {semantic['entity']}")
        print(f"  generation_mode: {semantic['generation_mode']}")
        print(f"  geometry_family: {semantic['geometry_family']}")
        print("=" * 60)

        assert semantic["domain"] == "vehicle", f"domain mismatch: {semantic['domain']}"
        assert semantic["entity"] == "drone", f"entity mismatch: {semantic['entity']}"
        assert semantic["generation_mode"] == "mesh", f"generation_mode mismatch: {semantic['generation_mode']}"
        assert semantic["geometry_family"] == "rotorcraft", f"geometry_family mismatch: {semantic['geometry_family']}"

    # ── Pipeline structure checks ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_result_has_all_three_pipeline_stages(self, gateway):
        result = await gateway.run("Generate a cargo drone", trace_id="trace_cp_002")
        assert "authorization" in result
        assert "prompt_runner" in result
        assert "semantic" in result

    @pytest.mark.asyncio
    async def test_core_was_called_first(self, gateway):
        """Core must be called exactly once before Prompt Runner."""
        call_order = []

        async def track_core(req):
            call_order.append("core")
            return _CORE_AUTH_SUCCESS

        async def track_pr(prompt, model=None):
            call_order.append("prompt_runner")
            return GenerateInstructionResponse(_PROMPT_RUNNER_LIVE_SHAPE)

        gateway._core.execute_task = track_core
        gateway._prompt_runner.generate_instruction = track_pr

        await gateway.run("Generate a cargo drone", trace_id="trace_cp_003")

        assert call_order[0] == "core", f"Core must be first, got: {call_order}"
        assert call_order[1] == "prompt_runner", f"PR must be second, got: {call_order}"

    @pytest.mark.asyncio
    async def test_authorization_status_is_success(self, gateway):
        result = await gateway.run("Generate a cargo drone", trace_id="trace_cp_004")
        assert result["authorization"].status == "success"

    @pytest.mark.asyncio
    async def test_prompt_runner_module_is_vehicle(self, gateway):
        result = await gateway.run("Generate a cargo drone", trace_id="trace_cp_005")
        assert result["prompt_runner"].module == "vehicle"

    @pytest.mark.asyncio
    async def test_prompt_runner_topic_is_cargo_drone(self, gateway):
        result = await gateway.run("Generate a cargo drone", trace_id="trace_cp_006")
        assert result["prompt_runner"].topic == "cargo_drone"

    # ── Invariant: Core rejection blocks Prompt Runner ─────────────────────────

    @pytest.mark.asyncio
    async def test_core_rejection_blocks_prompt_runner(self, gateway):
        """If Core rejects, Prompt Runner must NEVER be called."""
        gateway._core.execute_task = AsyncMock(
            return_value=CoreExecutionResponse(
                task_id="task_rej_001",
                trace_id="trace_rej_001",
                status="rejected",
                agent_output={"reason": "quota exceeded"},
            )
        )

        with pytest.raises(CoreGatewayAuthError):
            await gateway.run("Generate a cargo drone", trace_id="trace_cp_007")

        gateway._prompt_runner.generate_instruction.assert_not_called()

    # ── SemanticResolver: alias coverage for drone variants ───────────────────

    @pytest.mark.asyncio
    async def test_uav_topic_resolves_to_drone(self):
        """SemanticResolver should map 'uav' → drone."""
        resolver = SemanticResolver()
        result = resolver.resolve({"module": "vehicle", "topic": "uav", "intent": "design"})
        assert result["entity"] == "drone"
        assert result["domain"] == "vehicle"

    @pytest.mark.asyncio
    async def test_quadcopter_topic_resolves_to_drone(self):
        """SemanticResolver should map 'quadcopter' → drone."""
        resolver = SemanticResolver()
        result = resolver.resolve({"module": "vehicle", "topic": "quadcopter", "intent": "design"})
        assert result["entity"] == "drone"
        assert result["domain"] == "vehicle"

    @pytest.mark.asyncio
    async def test_combat_drone_topic_resolves_to_drone(self):
        """SemanticResolver should map 'combat_drone' → drone (from original spec example)."""
        resolver = SemanticResolver()
        result = resolver.resolve({"module": "vehicle", "topic": "combat_drone", "intent": "design"})
        assert result["entity"] == "drone"
        assert result["geometry_family"] == "rotorcraft"

    @pytest.mark.asyncio
    async def test_cargo_drone_semantic_output_matches_spec(self):
        """Direct SemanticResolver test — cargo_drone must produce exact spec output."""
        resolver = SemanticResolver()
        result = resolver.resolve(
            {
                "module": "vehicle",
                "topic": "cargo_drone",
                "intent": "design_creation",
            }
        )

        print("\n" + "─" * 50)
        print("SemanticResolver direct output for cargo_drone:")
        for k, v in result.items():
            print(f"  {k}: {v}")
        print("─" * 50)

        assert result == {
            "domain": "vehicle",
            "entity": "drone",
            "generation_mode": "mesh",
            "geometry_family": "rotorcraft",
        }, f"Unexpected result: {result}"


# ══════════════════════════════════════════════════════════════════════════════
# STANDALONE RUNNER (python tests/test_checkpoint_cargo_drone.py)
# ══════════════════════════════════════════════════════════════════════════════


async def _run_checkpoint():
    """Standalone async runner — prints a formatted checkpoint report."""
    print("\n" + "═" * 60)
    print("  TANTRA CHECKPOINT — Generate a cargo drone")
    print("  Tasks 6–9 Integration Verification")
    print("═" * 60)

    # ── Step 1: Mock Core auth ─────────────────────────────────────────────────
    mock_core = MagicMock()
    mock_core.execute_task = AsyncMock(return_value=_CORE_AUTH_SUCCESS)
    print("\n[STEP 1] CoreClient.execute_task      → status=success ✓")

    # ── Step 2: Mock Prompt Runner ─────────────────────────────────────────────
    mock_pr = MagicMock()
    mock_pr.generate_instruction = AsyncMock(return_value=GenerateInstructionResponse(_PROMPT_RUNNER_LIVE_SHAPE))
    print("[STEP 2] PromptRunnerClient.generate  → module=vehicle, topic=cargo_drone ✓")

    # ── Step 3: Real SemanticResolver ─────────────────────────────────────────
    real_resolver = SemanticResolver()
    print("[STEP 3] SemanticResolver             → resolving cargo_drone ...")

    gateway = CoreGateway(
        core_client=mock_core,
        prompt_runner_client=mock_pr,
        semantic_resolver=real_resolver,
    )

    result = await gateway.run(
        prompt="Generate a cargo drone",
        trace_id="trace_checkpoint_001",
    )

    semantic = result["semantic"]

    print("\n" + "─" * 60)
    print("  PIPELINE OUTPUT")
    print("─" * 60)
    print(f"  domain          : {semantic['domain']}")
    print(f"  entity          : {semantic['entity']}")
    print(f"  generation_mode : {semantic['generation_mode']}")
    print(f"  geometry_family : {semantic['geometry_family']}")
    print("─" * 60)

    expected = {
        "domain": "vehicle",
        "entity": "drone",
        "generation_mode": "mesh",
        "geometry_family": "rotorcraft",
    }

    passed = semantic == expected
    print(f"\n  CHECKPOINT: {'PASS ✅' if passed else 'FAIL ❌'}")

    if not passed:
        print(f"\n  Expected : {expected}")
        print(f"  Got      : {semantic}")
    else:
        print("\n  All 4 fields match expected output exactly.")

    print("═" * 60 + "\n")
    return passed


if __name__ == "__main__":
    success = asyncio.run(_run_checkpoint())
    raise SystemExit(0 if success else 1)
