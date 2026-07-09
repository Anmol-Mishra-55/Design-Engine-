"""
Replay Service — Task 2 Production Hardening

Reads a stored bucket trace (.jsonl) and the corresponding spec payload
(.json) then re-executes the existing CoreBucketCanonicalOrchestrator
pipeline, producing a new set of artifacts.

The replay does NOT modify the original trace or spec — it creates a
fresh execution with a new spec_id and a new trace_id that references
the original via `replay_of`.

Public API
----------
    result = await ReplayService.replay(spec_id)
    # result is a ReplayResult dataclass
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.logging_config import set_trace_context

logger = logging.getLogger(__name__)

# Paths mirror CoreBucketCanonicalOrchestrator / BucketRouter conventions
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_TRACE_DIR = _BACKEND_ROOT / "data" / "bucket_traces"
_SPEC_DIR = _BACKEND_ROOT / "data" / "specs"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class TraceEntry:
    timestamp: str
    trace_id: str
    stage: str
    payload: Dict[str, Any]


@dataclass
class ReplayResult:
    original_spec_id: str
    replay_spec_id: str
    original_trace_id: str
    replay_trace_id: str
    status: str  # "success" | "failed"
    artifacts: Dict[str, str] = field(default_factory=dict)  # kind → url
    error: Optional[str] = None
    replayed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_spec_id": self.original_spec_id,
            "replay_spec_id": self.replay_spec_id,
            "original_trace_id": self.original_trace_id,
            "replay_trace_id": self.replay_trace_id,
            "status": self.status,
            "artifacts": self.artifacts,
            "error": self.error,
            "replayed_at": self.replayed_at,
        }


# ---------------------------------------------------------------------------
# Loader helpers
# ---------------------------------------------------------------------------


def _load_trace(spec_id: str) -> List[TraceEntry]:
    """
    Load all JSONL entries for a given spec_id.
    Trace file name: core_bucket_{spec_id}.jsonl
    """
    trace_file = _TRACE_DIR / f"core_bucket_{spec_id}.jsonl"
    if not trace_file.exists():
        raise FileNotFoundError(f"Trace file not found: {trace_file}")

    entries: List[TraceEntry] = []
    with open(trace_file, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            entries.append(
                TraceEntry(
                    timestamp=raw.get("timestamp", ""),
                    trace_id=raw.get("trace_id", ""),
                    stage=raw.get("stage", ""),
                    payload=raw.get("payload", {}),
                )
            )
    return entries


def _load_spec_payload(spec_id: str) -> Dict[str, Any]:
    """
    Load the stored spec JSON for a given spec_id.
    Falls back to reconstructing from the trace's prompt_runner_response stage.
    """
    spec_file = _SPEC_DIR / f"{spec_id}.json"
    if spec_file.exists():
        with open(spec_file, encoding="utf-8") as fh:
            return json.load(fh)
    raise FileNotFoundError(f"Spec file not found: {spec_file}")


def _extract_request_payload(entries: List[TraceEntry]) -> Dict[str, Any]:
    """
    Reconstruct the original request payload from the core_ingress trace entry.
    """
    for entry in entries:
        if entry.stage == "core_ingress":
            p = entry.payload
            return {
                "user_id": p.get("user_id", "replay_user"),
                "city": p.get("city", "Mumbai"),
                "prompt": p.get("prompt", ""),
                "style": p.get("style", "modern"),
                "constraints": p.get("constraints", {}),
            }
    # Fallback: return minimal payload
    return {"user_id": "replay_user", "city": "Mumbai", "prompt": "replay"}


# ---------------------------------------------------------------------------
# Replay service
# ---------------------------------------------------------------------------


class ReplayService:
    """
    Stateless service.  Call ReplayService.replay(spec_id) to re-execute
    a previously stored pipeline run.
    """

    @staticmethod
    async def replay(spec_id: str) -> ReplayResult:
        """
        Re-execute the pipeline for a stored spec_id.

        Steps:
          1. Load the original trace file.
          2. Load the original spec payload.
          3. Reconstruct the original request payload from the trace.
          4. Generate a new spec_id and trace_id (prefixed with replay_).
          5. Run CoreBucketCanonicalOrchestrator.execute() with the
             reconstructed payload.
          6. Return a ReplayResult with the new artifacts.
        """
        import uuid

        from app.core_bucket_pipeline import CoreBucketCanonicalOrchestrator

        replay_spec_id = f"replay_{spec_id[:12]}_{uuid.uuid4().hex[:8]}"
        original_trace_id = f"core_bucket_{spec_id}"
        replay_trace_id = f"core_bucket_{replay_spec_id}"

        set_trace_context(
            trace_id=replay_trace_id,
            execution_id=replay_spec_id,
            pipeline_stage="replay",
        )

        logger.info(
            "Replay started: original_spec_id=%s replay_spec_id=%s",
            spec_id,
            replay_spec_id,
        )

        try:
            entries = _load_trace(spec_id)
        except FileNotFoundError as exc:
            logger.error("Replay failed — trace not found: %s", exc)
            return ReplayResult(
                original_spec_id=spec_id,
                replay_spec_id=replay_spec_id,
                original_trace_id=original_trace_id,
                replay_trace_id=replay_trace_id,
                status="failed",
                error=str(exc),
            )

        request_payload = _extract_request_payload(entries)
        # Tag the payload so the pipeline knows this is a replay
        request_payload["_replay_of"] = spec_id

        try:
            orchestrator = CoreBucketCanonicalOrchestrator()
            result = await orchestrator.execute(replay_spec_id, request_payload)

            artifacts = {kind: artifact.url for kind, artifact in result.artifacts.items()}

            logger.info(
                "Replay completed: replay_spec_id=%s artifacts=%s",
                replay_spec_id,
                list(artifacts.keys()),
            )

            return ReplayResult(
                original_spec_id=spec_id,
                replay_spec_id=replay_spec_id,
                original_trace_id=original_trace_id,
                replay_trace_id=replay_trace_id,
                status="success",
                artifacts=artifacts,
            )

        except Exception as exc:
            logger.error(
                "Replay execution failed: replay_spec_id=%s error=%s",
                replay_spec_id,
                exc,
                exc_info=True,
            )
            return ReplayResult(
                original_spec_id=spec_id,
                replay_spec_id=replay_spec_id,
                original_trace_id=original_trace_id,
                replay_trace_id=replay_trace_id,
                status="failed",
                error=str(exc),
            )

    @staticmethod
    def list_replayable_specs() -> List[str]:
        """
        Return spec_ids for which both a trace file and a spec file exist.
        """
        if not _TRACE_DIR.exists():
            return []

        spec_ids: List[str] = []
        for trace_file in sorted(_TRACE_DIR.glob("core_bucket_spec_*.jsonl")):
            # Extract spec_id from filename: core_bucket_{spec_id}.jsonl
            stem = trace_file.stem  # core_bucket_spec_abc123
            spec_id = stem[len("core_bucket_") :]  # spec_abc123
            spec_file = _SPEC_DIR / f"{spec_id}.json"
            if spec_file.exists():
                spec_ids.append(spec_id)
        return spec_ids

    @staticmethod
    def get_trace_summary(spec_id: str) -> Dict[str, Any]:
        """
        Return a summary of the stored trace for a spec_id without re-executing.
        """
        try:
            entries = _load_trace(spec_id)
        except FileNotFoundError as exc:
            return {"error": str(exc)}

        return {
            "spec_id": spec_id,
            "trace_id": f"core_bucket_{spec_id}",
            "stage_count": len(entries),
            "stages": [e.stage for e in entries],
            "started_at": entries[0].timestamp if entries else None,
            "completed_at": entries[-1].timestamp if entries else None,
        }


__all__ = ["ReplayService", "ReplayResult", "TraceEntry"]
