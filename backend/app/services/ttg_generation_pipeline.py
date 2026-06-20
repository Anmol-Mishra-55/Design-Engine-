"""
TTGGenerationPipeline
=====================
Runtime orchestrator for the full TANTRA asset generation pipeline.

Full flow::

    prompt
    → CoreGateway (Core auth + Prompt Runner + SemanticResolver)
    → ExecutionSchemaFactory (domain → executionSchema)
    → TTGPayloadBuilder (assemble TTGExecutePayload)
    → TTGClient POST /core/execute
    → TTGClient GET /core/execution/{id}  (poll until terminal)
    → BucketAssetRecord (record trace + hash)

No step can be skipped. The pipeline is fail-closed at every boundary:
- Core rejection → immediate halt, TTG never called
- TTG failure    → TTGGenerationError raised, bucket never written
- Polling timeout → TTGGenerationError raised

Usage::

    pipeline = TTGGenerationPipeline()
    result = await pipeline.run(
        prompt="Generate delivery drone",
        spec_json={"domain": "vehicle", "entity": "drone"},
        bucket_urls=["https://bhiv-bucket.onrender.com/bucket/artifact/drone-glb"],
        trace_id="trace_001",
    )
    print(result.bucket_record.bucket_url)
    print(result.execution_status.status)   # "completed"
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.adapters.ttg_payload_builder import TTGPayloadBuilder, TTGPayloadError
from app.contracts.bucket_asset_record import BucketAssetRecord, BucketAssetValidationError
from app.services.core_gateway import CoreGateway, CoreGatewayAuthError, CoreGatewayError
from app.services.ttg_client import (
    TTGClient,
    TTGError,
    TTGExecutionResponse,
    TTGExecutionStatus,
    TTGTimeoutError,
    TTGValidationError,
)

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

POLL_INTERVAL_SECONDS: float = 3.0  # seconds between GET /core/execution/{id} calls
POLL_MAX_ATTEMPTS: int = 20  # 20 × 3s = 60s max polling window

# ── Exceptions ────────────────────────────────────────────────────────────────


class TTGGenerationError(Exception):
    """Pipeline failure during TTG execution or polling."""


class TTGGenerationAuthError(TTGGenerationError):
    """Core rejected the request — TTG was never called."""


class TTGGenerationTimeoutError(TTGGenerationError):
    """Polling exceeded POLL_MAX_ATTEMPTS without a terminal status."""


# ── Result container ──────────────────────────────────────────────────────────


@dataclass
class TTGGenerationResult:
    """
    Complete result from a successful TTGGenerationPipeline.run() call.

    Fields:
        trace_id          — end-to-end trace ID propagated through every stage
        execution_id      — TTG execution ID from POST /core/execute
        domain            — resolved semantic domain
        entity            — resolved semantic entity
        execution_response — raw response from POST /core/execute
        execution_status   — final polled status from GET /core/execution/{id}
        bucket_record      — BucketAssetRecord recorded after completion
        semantic           — full semantic context dict
    """

    trace_id: str
    execution_id: str
    domain: str
    entity: str
    execution_response: TTGExecutionResponse
    execution_status: TTGExecutionStatus
    bucket_record: BucketAssetRecord
    semantic: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "execution_id": self.execution_id,
            "domain": self.domain,
            "entity": self.entity,
            "status": self.execution_status.status,
            "result": self.execution_status.result,
            "bucket_url": self.bucket_record.bucket_url,
            "payload_hash": self.bucket_record.payload_hash,
            "semantic": self.semantic,
        }


# ── Pipeline ──────────────────────────────────────────────────────────────────


class TTGGenerationPipeline:
    """
    Full end-to-end TANTRA asset generation pipeline.

    Wires together every sprint component into a single callable:

        CoreGateway → ExecutionSchemaFactory → TTGPayloadBuilder
        → TTGClient.execute() → TTGClient.get_execution_status() [poll]
        → BucketAssetRecord

    Dependency injection is supported for all sub-components (enables
    unit testing without real network calls).

    Usage::

        pipeline = TTGGenerationPipeline()
        result = await pipeline.run(
            prompt="Generate delivery drone",
            spec_json={"domain": "vehicle", "entity": "drone"},
            bucket_urls=["https://bhiv-bucket.onrender.com/bucket/artifact/drone-glb"],
        )
    """

    def __init__(
        self,
        core_gateway: Optional[CoreGateway] = None,
        payload_builder: Optional[TTGPayloadBuilder] = None,
        ttg_client: Optional[TTGClient] = None,
        poll_interval: float = POLL_INTERVAL_SECONDS,
        poll_max: int = POLL_MAX_ATTEMPTS,
    ) -> None:
        self._gateway = core_gateway or CoreGateway()
        self._builder = payload_builder or TTGPayloadBuilder()
        self._ttg = ttg_client or TTGClient()
        self._poll_interval = poll_interval
        self._poll_max = poll_max

    # ── Public API ─────────────────────────────────────────────────────────────

    async def run(
        self,
        prompt: str,
        spec_json: Dict[str, Any],
        bucket_urls: List[str],
        trace_id: Optional[str] = None,
        task_id: Optional[str] = None,
        asset_refs: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TTGGenerationResult:
        """
        Execute the full TANTRA generation pipeline.

        Steps:
            1. CoreGateway  — authorize with Core, classify via Prompt Runner,
                              resolve semantic context
            2. ExecutionSchemaFactory — build typed executionSchema from semantic
            3. TTGPayloadBuilder      — assemble full TTGExecutePayload
            4. TTGClient.execute()    — POST /core/execute
            5. TTGClient.get_execution_status() — poll GET /core/execution/{id}
            6. BucketAssetRecord      — record trace + execution_id + bucket_url

        Args:
            prompt:      User generation prompt (e.g. "Generate delivery drone").
            spec_json:   Prompt spec dict passed through to TTG payload.
            bucket_urls: Target bucket URLs for generated GLB/STL/STEP files.
            trace_id:    Optional trace ID; auto-generated if not provided.
            task_id:     Optional task ID; auto-generated if not provided.
            asset_refs:  Optional existing bucket artifact references.
            metadata:    Optional metadata merged into executionSchema.

        Returns:
            TTGGenerationResult with all pipeline outputs.

        Raises:
            TTGGenerationAuthError   — Core rejected; TTG never called.
            TTGGenerationError       — Pipeline failure during TTG execution.
            TTGGenerationTimeoutError — Polling exceeded max attempts.
        """
        trace_id = trace_id or f"trace_{uuid.uuid4().hex[:16]}"
        task_id = task_id or f"task_{uuid.uuid4().hex[:12]}"

        logger.info(
            "TTGGenerationPipeline.run start: trace=%s task=%s prompt=%r",
            trace_id,
            task_id,
            prompt[:80],
        )

        # ── Step 1: Core auth + Prompt Runner + SemanticResolver ──────────────
        semantic = await self._step_gateway(prompt, trace_id, task_id)

        # ── Step 2: Assemble TTG payload (builder calls factory internally) ──
        payload = self._step_payload(
            semantic,
            spec_json,
            bucket_urls,
            trace_id,
            asset_refs or [],
            metadata or {},
        )

        # ── Step 4: POST /core/execute ────────────────────────────────────────
        exec_response = await self._step_execute(payload, trace_id)

        # ── Step 5: Poll GET /core/execution/{id} ─────────────────────────────
        exec_status = await self._step_poll(exec_response.execution_id, trace_id)

        # ── Step 6: Record BucketAssetRecord ──────────────────────────────────
        bucket_record = self._step_record(
            trace_id=trace_id,
            execution_id=exec_response.execution_id,
            bucket_urls=bucket_urls,
            semantic=semantic,
            exec_status=exec_status,
        )

        result = TTGGenerationResult(
            trace_id=trace_id,
            execution_id=exec_response.execution_id,
            domain=semantic["domain"],
            entity=semantic["entity"],
            execution_response=exec_response,
            execution_status=exec_status,
            bucket_record=bucket_record,
            semantic=semantic,
        )

        logger.info(
            "TTGGenerationPipeline.run complete: trace=%s execution_id=%s " "domain=%s entity=%s status=%s",
            trace_id,
            exec_response.execution_id,
            semantic["domain"],
            semantic["entity"],
            exec_status.status,
        )

        return result

    # ── Pipeline steps ────────────────────────────────────────────────────────

    async def _step_gateway(self, prompt: str, trace_id: str, task_id: str) -> Dict[str, Any]:
        """Step 1: CoreGateway → semantic context."""
        try:
            gateway_result = await self._gateway.run(
                prompt=prompt,
                trace_id=trace_id,
                task_id=task_id,
            )
            return gateway_result["semantic"]
        except CoreGatewayAuthError as exc:
            raise TTGGenerationAuthError(f"TTGGenerationPipeline: Core rejected — {exc}. " f"trace={trace_id}") from exc
        except CoreGatewayError as exc:
            raise TTGGenerationError(f"TTGGenerationPipeline: gateway failure — {exc}. " f"trace={trace_id}") from exc

    def _step_payload(
        self,
        semantic: Dict[str, Any],
        spec_json: Dict[str, Any],
        bucket_urls: List[str],
        trace_id: str,
        asset_refs: List[str],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Step 2: TTGPayloadBuilder → TTGExecutePayload dict."""
        try:
            ttg_payload = self._builder.build(
                semantic_resolution=semantic,
                spec_json=spec_json,
                bucket_urls=bucket_urls,
                trace_id=trace_id,
                asset_refs=asset_refs,
                metadata=metadata,
            )
            return ttg_payload.to_dict()
        except TTGPayloadError as exc:
            raise TTGGenerationError(f"TTGGenerationPipeline: payload build failed — {exc}") from exc

    async def _step_execute(self, payload: Dict[str, Any], trace_id: str) -> TTGExecutionResponse:
        """Step 4: POST /core/execute via TTGClient."""
        try:
            response = await self._ttg.execute(payload)
            logger.info(
                "TTGGenerationPipeline: POST /core/execute → execution_id=%s status=%s trace=%s",
                response.execution_id,
                response.status,
                trace_id,
            )
            return response
        except (TTGValidationError, TTGError, TTGTimeoutError) as exc:
            raise TTGGenerationError(f"TTGGenerationPipeline: TTG execute failed — {exc}. trace={trace_id}") from exc

    async def _step_poll(self, execution_id: str, trace_id: str) -> TTGExecutionStatus:
        """
        Step 5: Poll GET /core/execution/{id} until terminal status.

        Polls every POLL_INTERVAL_SECONDS up to POLL_MAX_ATTEMPTS times.
        Terminal = status in {completed, failed, cancelled}.

        Raises:
            TTGGenerationTimeoutError — polling limit exceeded
            TTGGenerationError        — TTG returned a non-completed terminal status
        """
        for attempt in range(1, self._poll_max + 1):
            try:
                status = await self._ttg.get_execution_status(execution_id)
            except (TTGError, TTGTimeoutError) as exc:
                raise TTGGenerationError(
                    f"TTGGenerationPipeline: poll failed on attempt {attempt} "
                    f"for execution_id={execution_id} — {exc}. trace={trace_id}"
                ) from exc

            logger.debug(
                "TTGGenerationPipeline poll %d/%d: execution_id=%s status=%s trace=%s",
                attempt,
                self._poll_max,
                execution_id,
                status.status,
                trace_id,
            )

            if status.is_terminal:
                if status.is_failed:
                    raise TTGGenerationError(
                        f"TTGGenerationPipeline: TTG execution failed. "
                        f"execution_id={execution_id} status={status.status} "
                        f"error={status.error!r} trace={trace_id}"
                    )
                logger.info(
                    "TTGGenerationPipeline: execution completed. " "execution_id=%s trace=%s",
                    execution_id,
                    trace_id,
                )
                return status

            await asyncio.sleep(self._poll_interval)

        raise TTGGenerationTimeoutError(
            f"TTGGenerationPipeline: polling timed out after {self._poll_max} attempts "
            f"({self._poll_max * self._poll_interval:.0f}s). "
            f"execution_id={execution_id} trace={trace_id}"
        )

    @staticmethod
    def _step_record(
        trace_id: str,
        execution_id: str,
        bucket_urls: List[str],
        semantic: Dict[str, Any],
        exec_status: TTGExecutionStatus,
    ) -> BucketAssetRecord:
        """
        Step 6: Create BucketAssetRecord.

        Uses the first bucket_url as the primary artifact URL.
        payload_hash is derived from the execution result if available.
        """
        primary_url = bucket_urls[0] if bucket_urls else ""

        # Derive payload hash from TTG result bytes if available
        result_bytes = b""
        if exec_status.result:
            import json

            result_bytes = json.dumps(exec_status.result, sort_keys=True).encode()

        asset_type = _domain_to_asset_type(semantic.get("domain", ""))

        try:
            record = BucketAssetRecord.create(
                trace_id=trace_id,
                execution_id=execution_id,
                bucket_url=primary_url,
                asset_type=asset_type,
                asset_name=semantic.get("entity", ""),
                payload_hash=BucketAssetRecord.hash_bytes(result_bytes) if result_bytes else "",
            )
        except BucketAssetValidationError as exc:
            raise TTGGenerationError(
                f"TTGGenerationPipeline: BucketAssetRecord creation failed — {exc}. " f"trace={trace_id}"
            ) from exc

        logger.info(
            "TTGGenerationPipeline: BucketAssetRecord created. " "trace=%s execution_id=%s bucket_url=%s",
            trace_id,
            execution_id,
            primary_url,
        )
        return record


# ── Helpers ───────────────────────────────────────────────────────────────────


def _domain_to_asset_type(domain: str) -> str:
    """Map semantic domain to BucketAssetRecord asset_type."""
    return {
        "architecture": "step",
        "vehicle": "glb",
        "object": "glb",
        "environment": "glb",
        "gameplay": "glb",
    }.get(domain, "glb")
