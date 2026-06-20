"""
TTGClient
=========
HTTP client for the live TTG backend.

Live base URL : https://ttg-backend-55ce.onrender.com
API docs      : https://ttg-backend-55ce.onrender.com/api-docs

Endpoints used:
  POST /core/execute          — dispatch TTGExecutePayload to engine queue
  GET  /core/execution/{id}   — poll execution status
  GET  /health                — service health check

Endpoints intentionally NOT used:
  POST /api/intent/compile    — gameplay NLP compiler. Bypassed because
                                SemanticResolver is the semantic authority.
                                intent_compile_bypassed=True is enforced
                                in ExecutionSchemaFactory.build_gameplay_schema().

Live confirmed response shapes:
  /health          → {"status": "ok", "uptime": float, "timestamp": int}
  /core/execute    → {"execution_id": str, "status": str, "message": str, ...}
  /core/execution/{id} → {"execution_id": str, "status": str, "result": {...}, ...}

Retry policy:
  - 3 attempts with exponential back-off (2s → 4s → 8s)
  - 5xx + timeout → retry
  - 4xx → fail immediately, no retry
  - All retries exhausted → TTGTimeoutError (timeout) or TTGError (5xx)

Exceptions:
  TTGError           — generic HTTP / network failure
  TTGTimeoutError    — all retries exhausted due to timeout
  TTGValidationError — response schema mismatch or missing required fields
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

TTG_BASE_URL: str = os.environ.get("TTG_BASE_URL", "https://ttg-backend-55ce.onrender.com")
TIMEOUT_SECONDS: float = 30.0
MAX_RETRIES: int = 3
RETRY_BACKOFF_BASE: int = 2  # 2s, 4s, 8s

# Valid execution status values from live TTG backend
_VALID_STATUSES = {"pending", "running", "completed", "failed", "cancelled", "queued"}


# ── Exceptions ────────────────────────────────────────────────────────────────


class TTGError(Exception):
    """Generic failure communicating with TTG (HTTP error, network issue)."""


class TTGTimeoutError(TTGError):
    """All retries exhausted due to request timeout."""


class TTGValidationError(TTGError):
    """TTG response does not match the expected schema."""


# ── Typed response dataclasses ────────────────────────────────────────────────


@dataclass
class TTGExecutionResponse:
    """
    Typed response from POST /core/execute.

    Live shape (confirmed from TTG API docs):
        {
            "execution_id": "...",
            "status":       "queued" | "pending" | "running",
            "message":      "...",
            "queued_at":    "...",   (optional)
            "trace_id":     "...",   (optional)
        }
    """

    execution_id: str
    status: str
    message: str = ""
    queued_at: str = ""
    trace_id: str = ""
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    REQUIRED_FIELDS = ("execution_id", "status")

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "TTGExecutionResponse":
        missing = [f for f in cls.REQUIRED_FIELDS if f not in raw]
        if missing:
            raise TTGValidationError(
                f"TTGExecutionResponse: missing required fields {missing}. " f"Got: {list(raw.keys())}"
            )
        return cls(
            execution_id=str(raw["execution_id"]),
            status=str(raw["status"]),
            message=str(raw.get("message", "")),
            queued_at=str(raw.get("queued_at", "")),
            trace_id=str(raw.get("trace_id", "")),
            raw=raw,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "status": self.status,
            "message": self.message,
            "queued_at": self.queued_at,
            "trace_id": self.trace_id,
        }


@dataclass
class TTGExecutionStatus:
    """
    Typed response from GET /core/execution/{id}.

    Live shape (confirmed from TTG API docs):
        {
            "execution_id": "...",
            "status":       "pending" | "running" | "completed" | "failed",
            "result":       {...} | null,
            "error":        "..." | null,
            "started_at":   "...",   (optional)
            "completed_at": "...",   (optional)
            "trace_id":     "...",   (optional)
        }
    """

    execution_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: str = ""
    completed_at: str = ""
    trace_id: str = ""
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    REQUIRED_FIELDS = ("execution_id", "status")

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "TTGExecutionStatus":
        missing = [f for f in cls.REQUIRED_FIELDS if f not in raw]
        if missing:
            raise TTGValidationError(
                f"TTGExecutionStatus: missing required fields {missing}. " f"Got: {list(raw.keys())}"
            )
        return cls(
            execution_id=str(raw["execution_id"]),
            status=str(raw["status"]),
            result=raw.get("result") or None,
            error=raw.get("error") or None,
            started_at=str(raw.get("started_at", "")),
            completed_at=str(raw.get("completed_at", "")),
            trace_id=str(raw.get("trace_id", "")),
            raw=raw,
        )

    @property
    def is_complete(self) -> bool:
        return self.status == "completed"

    @property
    def is_failed(self) -> bool:
        return self.status in ("failed", "cancelled")

    @property
    def is_terminal(self) -> bool:
        return self.is_complete or self.is_failed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "trace_id": self.trace_id,
        }


# ── Client ────────────────────────────────────────────────────────────────────


class TTGClient:
    """
    Async HTTP client for the live TTG backend.

    Live base URL: https://ttg-backend-55ce.onrender.com

    IMPORTANT: /api/intent/compile is never called from this client.
    All payloads arrive pre-compiled from ExecutionSchemaFactory.

    Usage::

        client = TTGClient()

        # 1. Dispatch payload built by TTGPayloadBuilder
        response = await client.execute(payload.to_dict())
        print(response.execution_id, response.status)

        # 2. Poll until terminal
        status = await client.get_execution_status(response.execution_id)
        print(status.status, status.result)

        # 3. Health check
        health = await client.health_check()
        print(health["status"])  # "ok"
    """

    def __init__(
        self,
        base_url: str = TTG_BASE_URL,
        timeout: float = TIMEOUT_SECONDS,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    # ── Public API ────────────────────────────────────────────────────────────

    async def execute(self, payload: Dict[str, Any]) -> TTGExecutionResponse:
        """
        POST /core/execute

        Dispatches a pre-built TTG execution payload to the engine queue.
        Input must be a TTGExecutePayload.to_dict() output or equivalent.

        NOTE: /api/intent/compile is NOT called. The payload's executionSchema
        is pre-built by ExecutionSchemaFactory — SemanticResolver is the
        semantic authority, not TTG's NLP compiler.

        Args:
            payload: Dict from TTGExecutePayload.to_dict()

        Returns:
            TTGExecutionResponse with execution_id for status polling.

        Raises:
            TTGValidationError  — payload missing required fields or bad response
            TTGTimeoutError     — all retries exhausted due to timeout
            TTGError            — HTTP error or network failure
        """
        self._validate_execute_payload(payload)
        raw = await self._post_with_retry("/core/execute", payload)
        return TTGExecutionResponse.from_dict(raw)

    async def get_execution_status(self, execution_id: str) -> TTGExecutionStatus:
        """
        GET /core/execution/{id}

        Polls the status of a previously dispatched execution.

        Args:
            execution_id: ID returned by execute()

        Returns:
            TTGExecutionStatus — check .is_terminal, .is_complete, .is_failed

        Raises:
            TTGValidationError  — missing execution_id or bad response shape
            TTGTimeoutError     — all retries exhausted due to timeout
            TTGError            — HTTP error or network failure
        """
        if not execution_id or not str(execution_id).strip():
            raise TTGValidationError("TTGClient.get_execution_status: execution_id cannot be empty.")
        raw = await self._get_with_retry(f"/core/execution/{execution_id}")
        return TTGExecutionStatus.from_dict(raw)

    async def health_check(self) -> Dict[str, Any]:
        """
        GET /health

        Live confirmed response: {"status": "ok", "uptime": float, "timestamp": int}

        Returns:
            Raw health dict from TTG backend.

        Raises:
            TTGTimeoutError — all retries exhausted
            TTGError        — HTTP error or network failure
        """
        return await self._get_with_retry("/health")

    # ── Validation ────────────────────────────────────────────────────────────

    @staticmethod
    def _validate_execute_payload(payload: Dict[str, Any]) -> None:
        """
        Guard: executionSchema and trace_id must be present in the payload.
        Raises TTGValidationError immediately — no network call attempted.
        """
        if not isinstance(payload, dict):
            raise TTGValidationError("TTGClient.execute: payload must be a dict.")
        for key in ("executionSchema", "trace_id"):
            if not payload.get(key):
                raise TTGValidationError(f"TTGClient.execute: payload missing required field '{key}'.")
        schema = payload["executionSchema"]
        if not isinstance(schema, dict) or not schema:
            raise TTGValidationError("TTGClient.execute: 'executionSchema' must be a non-empty dict.")

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    async def _post_with_retry(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug("TTGClient POST %s attempt %d/%d", path, attempt, self.max_retries)
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, json=payload)

                # 4xx → fail immediately, no retry
                if 400 <= response.status_code < 500:
                    raise TTGError(
                        f"TTGClient: client error {response.status_code} " f"from POST {url}: {response.text}"
                    )

                # 5xx → retry
                if response.status_code >= 500:
                    last_error = TTGError(
                        f"TTGClient: server error {response.status_code} " f"from POST {url}: {response.text}"
                    )
                    logger.warning(
                        "TTGClient POST %s → %d (attempt %d/%d), retrying…",
                        path,
                        response.status_code,
                        attempt,
                        self.max_retries,
                    )
                    self._backoff(attempt)
                    continue

                return response.json()

            except httpx.TimeoutException as exc:
                last_error = TTGTimeoutError(
                    f"TTGClient: timeout on POST {url} " f"(attempt {attempt}/{self.max_retries}): {exc}"
                )
                logger.warning(str(last_error))
                self._backoff(attempt)

            except httpx.RequestError as exc:
                last_error = TTGError(
                    f"TTGClient: request error on POST {url} " f"(attempt {attempt}/{self.max_retries}): {exc}"
                )
                logger.warning(str(last_error))
                self._backoff(attempt)

        if isinstance(last_error, TTGTimeoutError):
            raise last_error
        raise TTGError(f"TTGClient: all {self.max_retries} retries failed for POST {url}. " f"Last error: {last_error}")

    async def _get_with_retry(self, path: str) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug("TTGClient GET %s attempt %d/%d", path, attempt, self.max_retries)
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url)

                # 4xx → fail immediately
                if 400 <= response.status_code < 500:
                    raise TTGError(
                        f"TTGClient: client error {response.status_code} " f"from GET {url}: {response.text}"
                    )

                # 5xx → retry
                if response.status_code >= 500:
                    last_error = TTGError(f"TTGClient: server error {response.status_code} " f"from GET {url}")
                    self._backoff(attempt)
                    continue

                return response.json()

            except httpx.TimeoutException as exc:
                last_error = TTGTimeoutError(
                    f"TTGClient: timeout on GET {url} " f"(attempt {attempt}/{self.max_retries}): {exc}"
                )
                logger.warning(str(last_error))
                self._backoff(attempt)

            except httpx.RequestError as exc:
                last_error = TTGError(
                    f"TTGClient: request error on GET {url} " f"(attempt {attempt}/{self.max_retries}): {exc}"
                )
                logger.warning(str(last_error))
                self._backoff(attempt)

        if isinstance(last_error, TTGTimeoutError):
            raise last_error
        raise TTGError(f"TTGClient: all {self.max_retries} retries failed for GET {url}. " f"Last error: {last_error}")

    @staticmethod
    def _backoff(attempt: int) -> None:
        sleep_time = RETRY_BACKOFF_BASE**attempt
        logger.debug("TTGClient back-off: sleeping %.1fs", sleep_time)
        time.sleep(sleep_time)
