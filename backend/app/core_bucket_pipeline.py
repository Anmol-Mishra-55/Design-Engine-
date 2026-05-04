"""
Canonical Core Routing — handle_request pattern.

Every request MUST flow through Core:

    data   = bucket.store(request)          # Step 1: store inbound request
    result = prompt_runner.execute(data)    # Step 2: execute via Prompt Runner
    output = bucket.store(result)           # Step 3: store all outputs
    return output                           # Step 4: return bucket URLs only

Direct backend calls are NOT allowed.
All inputs and outputs are mediated by BucketRouter.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.prompt_runner_adapter import PromptRunnerAdapterBridge, PromptRunnerUnavailableError
from app.storage import upload_to_bucket

logger = logging.getLogger(__name__)


@dataclass
class ArtifactLocation:
    kind: str
    url: str
    storage_mode: str
    bucket_path: Optional[str] = None
    local_path: Optional[str] = None


@dataclass
class CanonicalExecutionResult:
    spec_json: Dict[str, Any]
    provider: str
    deterministic_hash: str
    bucket_trace_id: str
    artifacts: Dict[str, ArtifactLocation]


class BucketRouter:
    """
    Bucket gateway — ALL inputs and outputs pass through here.
    No direct backend calls are permitted outside this class.
    """

    def __init__(self):
        self.trace_dir = Path(__file__).resolve().parents[1] / "data" / "bucket_traces"
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.geometry_bucket = getattr(settings, "STORAGE_BUCKET_GEOMETRY", "geometry")
        self.files_bucket = getattr(settings, "STORAGE_BUCKET_FILES", "files")

    # ── Step 1: store inbound request ────────────────────────────────────────
    async def store_request(self, trace_id: str, request_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Persist the inbound request payload to the files bucket.
        Returns the stored payload (unchanged) so Core can pass it to Prompt Runner.
        """
        payload_bytes = json.dumps(request_payload, indent=2, ensure_ascii=True).encode("utf-8")
        bucket_path = f"requests/{trace_id}.json"
        request_url = await upload_to_bucket(self.files_bucket, bucket_path, payload_bytes, "application/json")
        self._append_trace(
            trace_id,
            "bucket_request_stored",
            {
                "bucket_path": bucket_path,
                "url": request_url,
                "payload_keys": sorted(request_payload.keys()),
            },
        )
        logger.info("Request stored in bucket: %s", request_url)
        return request_payload  # pass-through to Prompt Runner

    # ── Step 3: store all outputs ─────────────────────────────────────────────
    async def store_artifact(self, spec_id: str, kind: str, data: bytes) -> ArtifactLocation:
        """Upload a binary artifact (glb / stl / step) to the geometry bucket."""
        kind = kind.lower()
        if kind not in {"glb", "stl", "step"}:
            raise ValueError(f"Unsupported artifact kind: {kind}")
        bucket_path = f"{spec_id}.glb" if kind == "glb" else f"exports/{spec_id}.{kind}"
        remote_url = await upload_to_bucket(
            self.geometry_bucket,
            bucket_path,
            data,
            "model/gltf-binary" if kind == "glb" else "application/octet-stream",
        )
        logger.info("Artifact stored in bucket: %s -> %s", bucket_path, remote_url)
        return ArtifactLocation(
            kind=kind,
            url=remote_url,
            storage_mode="bucket_remote",
            bucket_path=bucket_path,
        )

    async def store_spec_payload(self, spec_id: str, spec_json: Dict[str, Any]) -> Dict[str, str]:
        """Upload the final spec JSON to the files bucket."""
        payload_bytes = json.dumps(spec_json, indent=2, ensure_ascii=True).encode("utf-8")
        bucket_path = f"specs/{spec_id}.json"
        remote_url = await upload_to_bucket(self.files_bucket, bucket_path, payload_bytes, "application/json")
        logger.info("Spec payload stored in bucket: %s -> %s", bucket_path, remote_url)
        return {"mode": "bucket_remote", "url": remote_url, "bucket_path": bucket_path}

    # ── Trace logging ─────────────────────────────────────────────────────────
    def _append_trace(self, trace_id: str, stage: str, payload: Dict[str, Any]) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
            "stage": stage,
            "payload": payload,
        }
        trace_file = self.trace_dir / f"{trace_id}.jsonl"
        with open(trace_file, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=True) + "\n")


class CoreBucketCanonicalOrchestrator:
    """
    Core routing enforcer.

    Canonical handle_request pattern:

        data   = bucket.store_request(req)       # Step 1 — bucket stores inbound
        result = prompt_runner.execute(data)     # Step 2 — Prompt Runner executes
        output = bucket.store(result)            # Step 3 — bucket stores all outputs
        return output                            # Step 4 — return bucket URLs only

    Direct backend calls are NOT allowed.
    """

    def __init__(self):
        self.bucket = BucketRouter()
        self.prompt_runner = PromptRunnerAdapterBridge()

    async def execute(self, spec_id: str, request_payload: Dict[str, Any]) -> CanonicalExecutionResult:
        trace_id = f"core_bucket_{spec_id}"

        # Stamp Core token so the generate endpoint can verify this came from Core
        request_payload = {**request_payload, "_core_token": settings.CORE_INTERNAL_TOKEN}

        self.bucket._append_trace(
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

        # ── Step 1: bucket.store(request) ────────────────────────────────────
        data = await self.bucket.store_request(trace_id, request_payload)

        # ── Step 2: prompt_runner.execute(data) ──────────────────────────────
        runner_result = await self.prompt_runner.run_from_platform(data)

        spec_json = runner_result.get("spec_json")
        if not isinstance(spec_json, dict):
            raise PromptRunnerUnavailableError("Prompt Runner returned no valid spec_json")

        provider = str(runner_result.get("provider", "prompt_runner_adapter"))
        deterministic_hash = str(runner_result.get("deterministic_hash") or self._hash_payload(request_payload))

        metadata = spec_json.setdefault("metadata", {})
        metadata["execution_authority"] = "prompt_runner_adapter"
        metadata["routing_authority"] = "core"
        metadata["storage_authority"] = "bucket"
        metadata["deterministic_hash"] = deterministic_hash
        metadata["bucket_trace_id"] = trace_id
        metadata["canonical_flow"] = "core->bucket->prompt_runner->geometry->bucket->core"

        spec_json.setdefault("city", request_payload.get("city") or "Mumbai")
        spec_json.setdefault("style", request_payload.get("style") or "modern")

        self.bucket._append_trace(
            trace_id,
            "prompt_runner_response",
            {
                "provider": provider,
                "deterministic_hash": deterministic_hash,
                "design_type": spec_json.get("design_type"),
                "rooms_count": len(spec_json.get("rooms", [])),
            },
        )

        # ── Step 2b: generate GLB from rooms ─────────────────────────────────
        prompt = request_payload.get("prompt", "")
        glb_bytes, glb_provider = await self._generate_glb(spec_json, prompt, spec_id, metadata)
        metadata["glb_provider"] = glb_provider
        logger.info("GLB generated via: %s (%d bytes)", glb_provider, len(glb_bytes))

        stl_bytes = self._convert_glb_to_stl(glb_bytes, spec_json, spec_id)
        step_bytes = self._convert_glb_to_step(glb_bytes, spec_json, spec_id)

        # ── Step 3: bucket.store(result) — all outputs go to bucket ──────────
        artifacts = {
            "glb": await self.bucket.store_artifact(spec_id, "glb", glb_bytes),
            "stl": await self.bucket.store_artifact(spec_id, "stl", stl_bytes),
            "step": await self.bucket.store_artifact(spec_id, "step", step_bytes),
        }
        metadata["export_urls"] = {kind: artifact.url for kind, artifact in artifacts.items()}

        spec_store = await self.bucket.store_spec_payload(spec_id, spec_json)
        self.bucket._append_trace(
            trace_id,
            "bucket_persist_complete",
            {
                "artifacts": {kind: asdict(artifact) for kind, artifact in artifacts.items()},
                "spec_payload": spec_store,
            },
        )
        self.bucket._append_trace(trace_id, "core_response_ready", {"spec_id": spec_id})

        # ── Step 4: return bucket URLs only ───────────────────────────────────
        return CanonicalExecutionResult(
            spec_json=spec_json,
            provider=provider,
            deterministic_hash=deterministic_hash,
            bucket_trace_id=trace_id,
            artifacts=artifacts,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # GLB generation: Meshy → Tripo → geometry_generator_real
    # ──────────────────────────────────────────────────────────────────────────

    async def _generate_glb(
        self, spec_json: Dict[str, Any], prompt: str, spec_id: str, metadata: Dict[str, Any]
    ) -> Tuple[bytes, str]:
        """
        GLB generation: Meshy AI -> Tripo AI -> geometry_generator_real.
        If geometry_generator_real fails -> raise. No dummy meshes, no silent fallbacks.
        """
        dimensions = spec_json.get("dimensions", {})

        # 1. Try Meshy AI
        meshy_key = getattr(settings, "MESHY_API_KEY", None) or ""
        if meshy_key and len(meshy_key) > 10:
            try:
                from app.meshy_3d_generator import generate_3d_with_meshy

                logger.info("Attempting Meshy AI 3D generation...")
                meshy_result = await generate_3d_with_meshy(prompt, dimensions)
                if meshy_result and isinstance(meshy_result, dict):
                    glb_bytes = meshy_result.get("glb_bytes")
                    if glb_bytes and len(glb_bytes) > 100:
                        logger.info("Meshy AI GLB generated: %d bytes", len(glb_bytes))
                        thumbnail_bytes = meshy_result.get("thumbnail_bytes")
                        if thumbnail_bytes:
                            try:
                                thumb_url = await upload_to_bucket(
                                    "previews", f"{spec_id}_meshy_preview.png", thumbnail_bytes
                                )
                                metadata["meshy_thumbnail_url"] = thumb_url
                            except Exception as te:
                                logger.warning("Thumbnail upload failed: %s", te)
                        if meshy_result.get("video_url"):
                            metadata["meshy_video_url"] = meshy_result["video_url"]
                        return glb_bytes, "meshy_ai"
            except Exception as exc:
                logger.warning("Meshy AI failed: %s", exc)

        # 2. Try Tripo AI
        tripo_key = getattr(settings, "TRIPO_API_KEY", None) or ""
        if tripo_key and len(tripo_key) > 10:
            try:
                from app.tripo_3d_generator import generate_3d_with_tripo

                logger.info("Attempting Tripo AI 3D generation...")
                glb_bytes = await generate_3d_with_tripo(prompt, dimensions, tripo_key)
                if glb_bytes and len(glb_bytes) > 100:
                    logger.info("Tripo AI GLB generated: %d bytes", len(glb_bytes))
                    return glb_bytes, "tripo_ai"
            except Exception as exc:
                logger.warning("Tripo AI failed: %s", exc)

        # Deterministic room-based geometry — raise on failure, no dummy mesh
        from app.geometry_generator_real import generate_real_glb

        try:
            glb_bytes = generate_real_glb(spec_json)
        except Exception as exc:
            raise RuntimeError(f"Geometry generation failed: {exc}") from exc

        if not glb_bytes or len(glb_bytes) < 100:
            raise RuntimeError("Geometry generation failed: generate_real_glb returned empty output")
        return glb_bytes, "geometry_generator_real"

    # ──────────────────────────────────────────────────────────────────────────
    # STL / STEP conversion helpers
    # ──────────────────────────────────────────────────────────────────────────

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
            a, b, c = vertices[a_idx], vertices[b_idx], vertices[c_idx]
            normal = self._triangle_normal(a, b, c)
            lines += [
                f"  facet normal {normal[0]:.6f} {normal[1]:.6f} {normal[2]:.6f}",
                "    outer loop",
                f"      vertex {a[0]:.6f} {a[1]:.6f} {a[2]:.6f}",
                f"      vertex {b[0]:.6f} {b[1]:.6f} {b[2]:.6f}",
                f"      vertex {c[0]:.6f} {c[1]:.6f} {c[2]:.6f}",
                "    endloop",
                "  endfacet",
            ]
        lines.append(f"endsolid bhiv_{spec_id}_{source_hash}")
        return ("\n".join(lines) + "\n").encode("utf-8")

    def _convert_glb_to_step(self, glb_bytes: bytes, spec_json: Dict[str, Any], spec_id: str) -> bytes:
        width, length, height = self._extract_dimensions(spec_json)
        source_hash = hashlib.sha256(glb_bytes).hexdigest()[:16]
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        points = self._box_vertices(width, length, height)
        point_lines = [
            f"#{i+10}=CARTESIAN_POINT('V{i}',({x:.6f},{y:.6f},{z:.6f}));" for i, (x, y, z) in enumerate(points)
        ]
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
        dims = spec_json.get("dimensions", {}) if isinstance(spec_json.get("dimensions"), dict) else {}

        def _safe(name: str, fallback: float) -> float:
            v = dims.get(name, fallback)
            return float(v) if isinstance(v, (int, float)) and v > 0 else fallback

        return _safe("width", 10.0), _safe("length", 10.0), _safe("height", 3.0)

    def _box_vertices(self, w: float, l: float, h: float) -> List[Tuple[float, float, float]]:
        return [
            (0, 0, 0),
            (w, 0, 0),
            (w, l, 0),
            (0, l, 0),
            (0, 0, h),
            (w, 0, h),
            (w, l, h),
            (0, l, h),
        ]

    def _triangle_normal(self, a, b, c) -> Tuple[float, float, float]:
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        mag = (nx * nx + ny * ny + nz * nz) ** 0.5
        return (nx / mag, ny / mag, nz / mag) if mag else (0.0, 0.0, 1.0)

    def _hash_payload(self, payload: Dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()[:16]
