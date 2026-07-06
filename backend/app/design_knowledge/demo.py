"""
DKB Pipeline — End-to-End Demonstration
========================================

Exercises the complete pipeline from Prompt Runner output through to a
DKBExecutionResult, with the TTG boundary mocked so no live server is needed.

Run from the backend root:

    python -m app.design_knowledge.demo

Or with a specific query:

    python -m app.design_knowledge.demo "luxury villa with garden"
    python -m app.design_knowledge.demo "3bhk family apartment"
    python -m app.design_knowledge.demo "studio single room"
"""
from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# ── Paths ─────────────────────────────────────────────────────────────────────

_RESIDENTIAL_DIR = Path(__file__).parent / "data" / "residential"


# ── TTG mock (no live server needed) ─────────────────────────────────────────


def _make_mock_ttg() -> MagicMock:
    """
    Returns a mock TTGGenerationPipeline that simulates a successful TTG run.
    Replaces Steps 2–6 so the demo works without a live Core/TTG server.
    """
    execution_id = f"exec_{uuid.uuid4().hex[:12]}"
    bucket_url = f"https://bhiv-bucket.onrender.com/bucket/artifact/{uuid.uuid4().hex[:8]}"

    exec_response = MagicMock()
    exec_response.execution_id = execution_id

    exec_status = MagicMock()
    exec_status.status = "completed"

    bucket_record = MagicMock()
    bucket_record.bucket_url = bucket_url

    ttg_result = MagicMock()
    ttg_result.execution_id = execution_id
    ttg_result.domain = "architecture"
    ttg_result.entity = "demo"
    ttg_result.execution_status = exec_status
    ttg_result.bucket_record = bucket_record
    ttg_result.semantic = {}

    pipeline = MagicMock()
    pipeline._step_payload.return_value = {}
    pipeline._step_execute = AsyncMock(return_value=exec_response)
    pipeline._step_poll = AsyncMock(return_value=exec_status)
    pipeline._step_record.return_value = bucket_record

    return pipeline, ttg_result


# ── Demo ──────────────────────────────────────────────────────────────────────


async def run_demo(topic: str) -> None:
    from app.design_knowledge.runtime.pipeline import DKBExecutionPipeline
    from app.design_knowledge.runtime.request import PromptInstruction

    # ── Step 1: Simulate Prompt Runner output ─────────────────────────────────
    raw_prompt_runner_response = {
        "module": "architecture",
        "intent": "generate",
        "topic": topic,
        "tasks": ["resolve_knowledge", "compile_spec", "generate_geometry"],
        "output_format": "3d_model",
        "product_context": "creator_core",
    }

    print("=" * 60)
    print("DKB Pipeline — End-to-End Demo")
    print("=" * 60)
    print(f"\nPrompt Runner output:")
    print(json.dumps(raw_prompt_runner_response, indent=2))

    # ── Step 2: Build PromptInstruction ───────────────────────────────────────
    instruction = PromptInstruction.from_prompt_runner(raw_prompt_runner_response)
    print(f"\nPromptInstruction built:")
    print(f"  module  = {instruction.module}")
    print(f"  intent  = {instruction.intent}")
    print(f"  topic   = {instruction.topic!r}")

    # ── Step 3: Build pipeline (mocked TTG) ───────────────────────────────────
    mock_ttg, mock_ttg_result = _make_mock_ttg()

    pipeline = DKBExecutionPipeline.from_directory(
        directory=_RESIDENTIAL_DIR,
        bucket_urls=["https://bhiv-bucket.onrender.com/bucket/artifact/demo"],
        ttg_pipeline=mock_ttg,
    )

    # Patch _run_ttg to return our mock result directly
    async def _mock_run_ttg(**kwargs):
        mock_ttg_result.domain = kwargs["semantic"]["domain"]
        mock_ttg_result.entity = kwargs["semantic"]["entity"]
        mock_ttg_result.semantic = kwargs["semantic"]
        return mock_ttg_result

    pipeline._run_ttg = _mock_run_ttg

    # ── Step 4: Execute ───────────────────────────────────────────────────────
    print(f"\nRunning DKBExecutionPipeline.run() ...")
    trace_id = f"trace_demo_{uuid.uuid4().hex[:8]}"
    result = await pipeline.run(instruction, trace_id=trace_id)

    # ── Step 5: Print result ──────────────────────────────────────────────────
    print(f"\n{'-' * 60}")
    print("DKBExecutionResult")
    print(f"{'-' * 60}")
    print(json.dumps(result.to_dict(), indent=2))

    print(f"\n{'-' * 60}")
    print("DKB Runtime Detail")
    print(f"{'-' * 60}")
    dkb = result.dkb_result
    spec = dkb.design_specification
    report = dkb.validation_report

    print(f"  knowledge_id     : {dkb.knowledge_id}")
    print(f"  design_type      : {dkb.design_type}")
    print(f"  search_score     : {dkb.search_score:.4f}")
    print(f"  matched_fields   : {dkb.matched_fields}")
    print(f"  spec_id          : {spec.spec_id}")
    print(
        f"  spaces           : {len(spec.spaces)} ({sum(1 for s in spec.spaces if s.required)} required, {sum(1 for s in spec.spaces if not s.required)} optional)"
    )
    print(f"  adjacency_edges  : {len(spec.adjacency_graph)}")
    print(f"  engineering      : {len(spec.engineering)} constraints")
    print(f"  validation_rules : {len(spec.validation_rules)}")
    print(f"  supported_styles : {spec.supported_styles}")

    print(f"\n  ValidationReport:")
    print(f"    valid  = {report.valid}")
    print(f"    score  = {report.score:.4f}")
    print(f"    passed = {len(report.passed_rules)}")
    print(f"    failed = {len(report.failed_rules)}")
    if report.errors:
        print(f"    errors:")
        for e in report.errors[:3]:
            print(f"      [{e.rule_id}] {e.message}")
    if report.warnings:
        print(f"    warnings: {len(report.warnings)}")

    print(f"\n{'-' * 60}")
    print("TTG Semantic Resolution")
    print(f"{'-' * 60}")
    for k, v in result.semantic.items():
        print(f"  {k:<20} = {v}")

    print(f"\n{'=' * 60}")
    print(f"Pipeline complete.")
    print(f"  trace_id         : {result.trace_id}")
    print(f"  execution_id     : {result.execution_id}")
    print(f"  execution_status : {result.execution_status}")
    print(f"  bucket_url       : {result.bucket_url}")
    print(f"{'=' * 60}\n")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "3bhk three bedroom family apartment"
    asyncio.run(run_demo(query))
