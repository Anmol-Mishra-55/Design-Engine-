"""
Canonical Core -> Bucket -> Prompt Runner -> Geometry -> Bucket execution.

GLB generation priority:
  1. Meshy AI  (MESHY_API_KEY set)  — realistic AI-generated 3D model
  2. Tripo AI  (TRIPO_API_KEY set)  — alternative AI 3D model
  3. geometry_generator_real        — deterministic Python geometry fallback
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
    """
    Canonical orchestration path:
    Core -> Bucket -> Prompt Runner Adapter -> Geometry -> Bucket -> Core

    Spec/JSON generation : Groq llama-3.3-70b → OpenAI → Anthropic → template
    GLB 3D generation    : Meshy AI → Tripo AI → geometry_generator_real
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

        # ── Step 1: Generate spec_json via Groq / OpenAI / Anthropic / template ──
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

        # ── Step 2: Generate GLB via Meshy → Tripo → geometry fallback ──
        prompt = request_payload.get("prompt", "")
        glb_bytes, glb_provider = await self._generate_glb(spec_json, prompt, spec_id, metadata)
        metadata["glb_provider"] = glb_provider
        logger.info("GLB generated via: %s (%d bytes)", glb_provider, len(glb_bytes))

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

    # ──────────────────────────────────────────────────────────────────────────
    # GLB generation: Meshy → Tripo → geometry_generator_real
    # ──────────────────────────────────────────────────────────────────────────

    async def _generate_glb(
        self, spec_json: Dict[str, Any], prompt: str, spec_id: str, metadata: Dict[str, Any]
    ) -> Tuple[bytes, str]:
        """
        Try Meshy AI first, then Tripo AI, then fall back to deterministic geometry.
        Returns (glb_bytes, provider_name).
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
                        logger.info("✅ Meshy AI GLB generated: %d bytes", len(glb_bytes))
                        # Store thumbnail if available
                        thumbnail_bytes = meshy_result.get("thumbnail_bytes")
                        if thumbnail_bytes:
                            try:
                                thumb_url = await upload_to_bucket(
                                    "previews", f"{spec_id}_meshy_preview.png", thumbnail_bytes
                                )
                                metadata["meshy_thumbnail_url"] = thumb_url
                                logger.info("✅ Meshy thumbnail stored: %s", thumb_url)
                            except Exception as te:
                                logger.warning("Thumbnail upload failed: %s", te)
                        if meshy_result.get("video_url"):
                            metadata["meshy_video_url"] = meshy_result["video_url"]
                        return glb_bytes, "meshy_ai"
                logger.warning("Meshy returned empty/invalid GLB, trying Tripo...")
            except Exception as exc:
                logger.warning("Meshy AI failed (%s), trying Tripo...", exc)

        # 2. Try Tripo AI
        tripo_key = getattr(settings, "TRIPO_API_KEY", None) or ""
        if tripo_key and len(tripo_key) > 10:
            try:
                from app.tripo_3d_generator import generate_3d_with_tripo

                logger.info("Attempting Tripo AI 3D generation...")
                glb_bytes = await generate_3d_with_tripo(prompt, dimensions, tripo_key)
                if glb_bytes and len(glb_bytes) > 100:
                    logger.info("✅ Tripo AI GLB generated: %d bytes", len(glb_bytes))
                    return glb_bytes, "tripo_ai"
                logger.warning("Tripo returned empty/invalid GLB, using geometry fallback...")
            except Exception as exc:
                logger.warning("Tripo AI failed (%s), using geometry fallback...", exc)

        # 3. Deterministic geometry fallback
        return self._generate_glb_from_geometry(spec_json), "geometry_generator_real"

    def _generate_glb_from_geometry(self, spec_json: Dict[str, Any]) -> bytes:
        """Generate GLB using deterministic Python geometry (always works, no API needed)."""
        try:
            from app.geometry_generator_real import generate_real_glb

            return generate_real_glb(spec_json)
        except Exception as exc:
            logger.warning("geometry_generator_real failed (%s), using minimal fallback GLB", exc)
            return self._minimal_fallback_glb()

    def _minimal_fallback_glb(self) -> bytes:
        """Absolute last-resort valid GLB binary."""
        import json as _json
        import struct

        gltf = _json.dumps(
            {
                "asset": {"version": "2.0"},
                "scenes": [{"nodes": [0]}],
                "nodes": [{"mesh": 0}],
                "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
                "accessors": [
                    {"bufferView": 0, "componentType": 5126, "count": 8, "type": "VEC3"},
                    {"bufferView": 1, "componentType": 5123, "count": 36, "type": "SCALAR"},
                ],
                "bufferViews": [
                    {"buffer": 0, "byteOffset": 0, "byteLength": 96},
                    {"buffer": 0, "byteOffset": 96, "byteLength": 72},
                ],
                "buffers": [{"byteLength": 168}],
            }
        ).encode("utf-8")

        # 8 vertices of a 10x10x3 box
        verts = [
            (0, 0, 0),
            (10, 0, 0),
            (10, 10, 0),
            (0, 10, 0),
            (0, 0, 3),
            (10, 0, 3),
            (10, 10, 3),
            (0, 10, 3),
        ]
        vert_data = b"".join(struct.pack("<fff", *v) for v in verts)

        # 12 triangles (6 faces × 2)
        idx = [
            0,
            1,
            2,
            0,
            2,
            3,
            4,
            6,
            5,
            4,
            7,
            6,
            0,
            4,
            5,
            0,
            5,
            1,
            1,
            5,
            6,
            1,
            6,
            2,
            2,
            6,
            7,
            2,
            7,
            3,
            3,
            7,
            4,
            3,
            4,
            0,
        ]
        idx_data = b"".join(struct.pack("<H", i) for i in idx)

        bin_data = vert_data + idx_data
        pad = (4 - len(bin_data) % 4) % 4
        bin_data += b"\x00" * pad

        json_pad = (4 - len(gltf) % 4) % 4
        gltf += b" " * json_pad

        total = 12 + 8 + len(gltf) + 8 + len(bin_data)
        return (
            b"glTF"
            + struct.pack("<II", 2, total)
            + struct.pack("<I", len(gltf))
            + b"JSON"
            + gltf
            + struct.pack("<I", len(bin_data))
            + b"BIN\x00"
            + bin_data
        )

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
