"""
Canonical Core -> Bucket -> Prompt Runner -> Geometry -> Bucket execution.

This module keeps the required deterministic execution path and isolates
Prompt Runner integration behind the adapter contract.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.config import settings
from app.prompt_runner_adapter import PromptRunnerAdapterBridge, PromptRunnerUnavailableError

logger = logging.getLogger(__name__)


@dataclass
class ArtifactLocation:
    kind: str
    url: str
    storage_mode: str
    bucket_path: str | None = None
    local_path: str | None = None


@dataclass
class CanonicalExecutionResult:
    spec_json: Dict[str, Any]
    provider: str
    deterministic_hash: str
    bucket_trace_id: str
    artifacts: Dict[str, ArtifactLocation]


class BucketRouter:
    """Bucket gateway for artifact persistence with remote-first, local-fallback behavior."""

    def __init__(self):
        project_root = Path(__file__).resolve().parents[1]
        data_root = project_root / "data"

        self.spec_dir = data_root / "specs"
        self.geometry_dir = data_root / "geometry_outputs"
        self.export_dir = data_root / "export_outputs"
        self.trace_dir = data_root / "bucket_traces"

        for directory in (self.spec_dir, self.geometry_dir, self.export_dir, self.trace_dir):
            directory.mkdir(parents=True, exist_ok=True)

        self.geometry_bucket = getattr(settings, "STORAGE_BUCKET_GEOMETRY", "geometry")
        self.files_bucket = getattr(settings, "STORAGE_BUCKET_FILES", "files")

    def append_trace(self, trace_id: str, stage: str, payload: Dict[str, Any]) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
            "stage": stage,
            "payload": payload,
        }
        trace_file = self.trace_dir / f"{trace_id}.jsonl"
        with open(trace_file, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=True) + "\n")

    async def store_artifact(self, spec_id: str, kind: str, data: bytes) -> ArtifactLocation:
        kind = kind.lower()
        if kind not in {"glb", "stl", "step"}:
            raise ValueError(f"Unsupported artifact kind: {kind}")

        if kind == "glb":
            bucket_path = f"{spec_id}.glb"
            local_path = self.geometry_dir / f"{spec_id}.glb"
            local_url = f"/static/geometry/{spec_id}.glb"
        else:
            bucket_path = f"exports/{spec_id}.{kind}"
            local_path = self.export_dir / f"{spec_id}.{kind}"
            local_url = f"/static/exports/{spec_id}.{kind}"

        try:
            remote_url = await upload_to_bucket(self.geometry_bucket, bucket_path, data)
            return ArtifactLocation(
                kind=kind,
                url=remote_url,
                storage_mode="bucket_remote",
                bucket_path=bucket_path,
            )
        except Exception as exc:
            logger.warning("Bucket upload failed for %s (%s), using local fallback", kind, exc)
            local_path.write_bytes(data)
            return ArtifactLocation(
                kind=kind,
                url=local_url,
                storage_mode="bucket_local_fallback",
                local_path=str(local_path),
            )

    async def store_spec_payload(self, spec_id: str, spec_json: Dict[str, Any]) -> Dict[str, str]:
        payload_bytes = json.dumps(spec_json, indent=2, ensure_ascii=True).encode("utf-8")
        bucket_path = f"specs/{spec_id}.json"

        try:
            remote_url = await upload_to_bucket(self.files_bucket, bucket_path, payload_bytes)
            return {"mode": "bucket_remote", "url": remote_url, "bucket_path": bucket_path}
        except Exception as exc:
            logger.warning("Spec payload upload failed (%s), using local fallback", exc)
            local_path = self.spec_dir / f"{spec_id}.json"
            local_path.write_bytes(payload_bytes)
            return {"mode": "bucket_local_fallback", "local_path": str(local_path)}


class CoreBucketCanonicalOrchestrator:
    """Canonical orchestration path:

    Core -> Bucket -> Prompt Runner Adapter -> Geometry -> Bucket -> Core
    """

    def __init__(self):
        self.bucket = BucketRouter()
        self.prompt_runner = PromptRunnerAdapterBridge()

    async def execute(self, spec_id: str, request_payload: Dict[str, Any]) -> CanonicalExecutionResult:
        trace_id = f"core_bucket_{spec_id}"

        self.bucket.append_trace(
            trace_id,
            "core_ingress",
            {
                "spec_id": spec_id,
                "user_id": request_payload.get("user_id"),
                "city": request_payload.get("city"),
                "style": request_payload.get("style"),
                "payload_keys": sorted(request_payload.keys()),
            },
        )

        self.bucket.append_trace(trace_id, "bucket_request_received", {"route": "prompt_runner_adapter"})

        runner_result = await self.prompt_runner.run_from_platform(request_payload)

        spec_json = runner_result.get("spec_json")
        if not isinstance(spec_json, dict):
            raise PromptRunnerUnavailableError("Prompt Runner adapter response is missing a valid spec_json")

        provider = str(runner_result.get("provider", "prompt_runner_adapter"))
        deterministic_hash = str(runner_result.get("deterministic_hash") or self._hash_payload(request_payload))

        metadata = spec_json.setdefault("metadata", {})
        metadata["execution_authority"] = "prompt_runner_adapter"
        metadata["routing_authority"] = "core"
        metadata["storage_authority"] = "bucket"
        metadata["deterministic_hash"] = deterministic_hash
        metadata["bucket_trace_id"] = trace_id
        metadata["canonical_flow"] = "core->bucket->prompt_runner_adapter->design_engine_geometry->bucket->core"

        # Keep top-level fields aligned with incoming request for consistency.
        spec_json.setdefault("city", request_payload.get("city") or "Mumbai")
        spec_json.setdefault("style", request_payload.get("style") or "modern")

        self.bucket.append_trace(
            trace_id,
            "prompt_runner_response",
            {
                "provider": provider,
                "deterministic_hash": deterministic_hash,
                "design_type": spec_json.get("design_type"),
            },
        )

        glb_bytes = self._generate_glb(spec_json)
        stl_bytes = self._convert_glb_to_stl(glb_bytes, spec_json, spec_id)
        step_bytes = self._convert_glb_to_step(glb_bytes, spec_json, spec_id)

        artifacts = {
            "glb": await self.bucket.store_artifact(spec_id, "glb", glb_bytes),
            "stl": await self.bucket.store_artifact(spec_id, "stl", stl_bytes),
            "step": await self.bucket.store_artifact(spec_id, "step", step_bytes),
        }

        metadata["export_urls"] = {kind: artifact.url for kind, artifact in artifacts.items()}

        spec_store = await self.bucket.store_spec_payload(spec_id, spec_json)
        self.bucket.append_trace(
            trace_id,
            "bucket_persist_complete",
            {
                "artifacts": {kind: asdict(artifact) for kind, artifact in artifacts.items()},
                "spec_payload": spec_store,
            },
        )

        self.bucket.append_trace(trace_id, "core_response_ready", {"spec_id": spec_id})

        return CanonicalExecutionResult(
            spec_json=spec_json,
            provider=provider,
            deterministic_hash=deterministic_hash,
            bucket_trace_id=trace_id,
            artifacts=artifacts,
        )

    def _generate_glb(self, spec_json: Dict[str, Any]) -> bytes:
        try:
            from app.geometry_generator_real import generate_real_glb

            return generate_real_glb(spec_json)
        except Exception as exc:
            logger.warning("Real geometry generation failed (%s), using fallback GLB", exc)
            return self._fallback_glb()

    def _fallback_glb(self) -> bytes:
        glb_header = b"glTF\x02\x00\x00\x00"
        mock_data = (
            b'{"asset":{"version":"2.0"},"scenes":[{"nodes":[0]}],"nodes":[{"mesh":0}],'
            b'"meshes":[{"primitives":[{"attributes":{"POSITION":0}}]}]}'
        )
        padding = b"\x00" * max(0, 1024 - len(mock_data))
        return glb_header + mock_data + padding

    def _convert_glb_to_stl(self, glb_bytes: bytes, spec_json: Dict[str, Any], spec_id: str) -> bytes:
        width, length, height = self._extract_dimensions(spec_json)
        vertices = self._box_vertices(width, length, height)
        faces = [
            (0, 1, 2),
            (0, 2, 3),
            (4, 5, 6),
            (4, 6, 7),
            (0, 1, 5),
            (0, 5, 4),
            (1, 2, 6),
            (1, 6, 5),
            (2, 3, 7),
            (2, 7, 6),
            (3, 0, 4),
            (3, 4, 7),
        ]

        source_hash = hashlib.sha256(glb_bytes).hexdigest()[:16]
        lines = [f"solid bhiv_{spec_id}_{source_hash}"]
        for a_idx, b_idx, c_idx in faces:
            a = vertices[a_idx]
            b = vertices[b_idx]
            c = vertices[c_idx]
            normal = self._triangle_normal(a, b, c)
            lines.append(f"  facet normal {normal[0]:.6f} {normal[1]:.6f} {normal[2]:.6f}")
            lines.append("    outer loop")
            lines.append(f"      vertex {a[0]:.6f} {a[1]:.6f} {a[2]:.6f}")
            lines.append(f"      vertex {b[0]:.6f} {b[1]:.6f} {b[2]:.6f}")
            lines.append(f"      vertex {c[0]:.6f} {c[1]:.6f} {c[2]:.6f}")
            lines.append("    endloop")
            lines.append("  endfacet")
        lines.append(f"endsolid bhiv_{spec_id}_{source_hash}")
        return ("\n".join(lines) + "\n").encode("utf-8")

    def _convert_glb_to_step(self, glb_bytes: bytes, spec_json: Dict[str, Any], spec_id: str) -> bytes:
        width, length, height = self._extract_dimensions(spec_json)
        source_hash = hashlib.sha256(glb_bytes).hexdigest()[:16]
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        points = self._box_vertices(width, length, height)
        point_lines = []
        for index, (x_val, y_val, z_val) in enumerate(points, start=10):
            point_lines.append(f"#{index}=CARTESIAN_POINT('V{index - 10}',({x_val:.6f},{y_val:.6f},{z_val:.6f}));")

        content = [
            "ISO-10303-21;",
            "HEADER;",
            "FILE_DESCRIPTION(('BHIV canonical STEP export'),'2;1');",
            f"FILE_NAME('{spec_id}.step','{timestamp}',('BHIV'),('DesignEngine'),'CoreBucketPipeline','','');",
            "FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));",
            "ENDSEC;",
            "DATA;",
            f"#1=DESCRIPTIVE_REPRESENTATION_ITEM('SOURCE_GLB_SHA256','{source_hash}');",
            f"#2=DESCRIPTIVE_REPRESENTATION_ITEM('DIMENSIONS_M','{width:.6f}x{length:.6f}x{height:.6f}');",
            *point_lines,
            "ENDSEC;",
            "END-ISO-10303-21;",
            "",
        ]
        return "\n".join(content).encode("utf-8")

    def _extract_dimensions(self, spec_json: Dict[str, Any]) -> Tuple[float, float, float]:
        dimensions = spec_json.get("dimensions", {}) if isinstance(spec_json.get("dimensions"), dict) else {}

        def _safe_dimension(name: str, fallback: float) -> float:
            value = dimensions.get(name, fallback)
            if isinstance(value, (int, float)) and value > 0:
                return float(value)
            return fallback

        width = _safe_dimension("width", 10.0)
        length = _safe_dimension("length", 10.0)
        height = _safe_dimension("height", 3.0)
        return width, length, height

    def _box_vertices(self, width: float, length: float, height: float) -> List[Tuple[float, float, float]]:
        return [
            (0.0, 0.0, 0.0),
            (width, 0.0, 0.0),
            (width, length, 0.0),
            (0.0, length, 0.0),
            (0.0, 0.0, height),
            (width, 0.0, height),
            (width, length, height),
            (0.0, length, height),
        ]

    def _triangle_normal(
        self,
        a: Tuple[float, float, float],
        b: Tuple[float, float, float],
        c: Tuple[float, float, float],
    ) -> Tuple[float, float, float]:
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]

        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx

        magnitude = (nx * nx + ny * ny + nz * nz) ** 0.5
        if magnitude == 0:
            return (0.0, 0.0, 1.0)
        return (nx / magnitude, ny / magnitude, nz / magnitude)

    def _hash_payload(self, payload: Dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()[:16]
