"""
CoreClient
==========
HTTP client for TANTRA Core service.

Base URL : configured via CORE_BASE_URL (default: http://localhost:8000)
Endpoints:
  POST /execute_task  — accepts CoreExecutionRequest, returns CoreExecutionResponse
  GET  /health        — returns {"status": "ok", ...}

Requirements:
  - execution_token mandatory (validated before dispatch)
  - trace_id mandatory (validated before dispatch)
  - 30 s timeout per request
  - 3 retries with exponential back-off on 5xx / timeout
  - Full response validation via CoreExecutionResponse contract

Exceptions:
  CoreError           — generic HTTP / network failure
  CoreValidationError — response schema mismatch or missing required fields
  CoreTimeoutError    — all retries exhausted due to timeout
"""

import logging
import os
import time
from typing import Any, Dict, Optional

import httpx
from app.contracts.core_execution_request import CoreExecutionRequest, ValidationError
from app.contracts.core_execution_response import CoreExecutionResponse

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

CORE_BASE_URL: str = os.environ.get("CORE_BASE_URL", "http://localhost:8000")
TIMEOUT_SECONDS: float = 30.0
MAX_RETRIES: int = 3
RETRY_BACKOFF_BASE: int = 2  # seconds: 2, 4, 8

# ── Exceptions ────────────────────────────────────────────────────────────────


class CoreError(Exception):
    """Generic failure communicating with Core (HTTP error, network issue)."""


class CoreValidationError(CoreError):
    """Response from Core does not match the expected contract schema."""


class CoreTimeoutError(CoreError):
    """All retries exhausted due to request timeout."""


# ── Client ────────────────────────────────────────────────────────────────────


class CoreClient:
    """
    Stateless HTTP client for TANTRA Core.

    Usage::

        client = CoreClient()

        request = CoreExecutionRequest(
            input="Design a 2BHK apartment",
            agent="architecture_generator",
            execution_token="tok_abc123",
            trace_id="trace_xyz789",
        )
        response = await client.execute_task(request)
        print(response.status, response.agent_output)

        health = await client.health_check()
        print(health)
    """

    def __init__(
        self,
        base_url: str = CORE_BASE_URL,
        timeout: float = TIMEOUT_SECONDS,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    # ── Public API ────────────────────────────────────────────────────────────

    async def execute_task(self, request: CoreExecutionRequest) -> CoreExecutionResponse:
        """
        POST /execute_task

        Validates that execution_token and trace_id are present before
        dispatching. Returns a validated CoreExecutionResponse.

        Raises:
            CoreValidationError  — missing execution_token / trace_id,
                                   or response schema mismatch
            CoreTimeoutError     — all retries exhausted due to timeout
            CoreError            — HTTP error or network failure
        """
        self._validate_request(request)

        raw = await self._post_with_retry("/execute_task", request.to_dict())

        return self._parse_response(raw)

    async def health_check(self) -> Dict[str, Any]:
        """
        GET /health

        Returns the raw health response dict from Core.

        Raises:
            CoreTimeoutError — all retries exhausted due to timeout
            CoreError        — HTTP error or network failure
        """
        return await self._get_with_retry("/health")

    # ── Validation ────────────────────────────────────────────────────────────

    @staticmethod
    def _validate_request(request: CoreExecutionRequest) -> None:
        """
        Guard: execution_token and trace_id must be present.
        CoreExecutionRequest.__post_init__ already checks this, but we
        re-check here in case a mutated object is passed.
        """
        if not request.execution_token or not str(request.execution_token).strip():
            raise CoreValidationError("CoreClient: 'execution_token' is required and cannot be empty.")
        if not request.trace_id or not str(request.trace_id).strip():
            raise CoreValidationError("CoreClient: 'trace_id' is required and cannot be empty.")

    @staticmethod
    def _parse_response(raw: Dict[str, Any]) -> CoreExecutionResponse:
        """
        Build and validate a CoreExecutionResponse from the raw dict.
        Wraps contract ValidationError → CoreValidationError.
        """
        try:
            return CoreExecutionResponse.from_dict(raw)
        except ValidationError as exc:
            raise CoreValidationError(f"CoreClient: response validation failed — {exc}") from exc
        except Exception as exc:
            raise CoreValidationError(f"CoreClient: unexpected response format — {exc}") from exc

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    async def _post_with_retry(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug("CoreClient POST %s attempt %d/%d", path, attempt, self.max_retries)
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, json=payload)

                if 400 <= response.status_code < 500:
                    raise CoreError(f"CoreClient: client error {response.status_code} " f"from {url}: {response.text}")
                if response.status_code >= 500:
                    last_error = CoreError(
                        f"CoreClient: server error {response.status_code} " f"from {url}: {response.text}"
                    )
                    logger.warning(
                        "CoreClient POST %s → %d (attempt %d), retrying…",
                        path,
                        response.status_code,
                        attempt,
                    )
                    self._backoff(attempt)
                    continue

                return response.json()

            except httpx.TimeoutException as exc:
                last_error = CoreTimeoutError(
                    f"CoreClient: timeout on {url} " f"(attempt {attempt}/{self.max_retries}): {exc}"
                )
                logger.warning(str(last_error))
                self._backoff(attempt)

            except httpx.RequestError as exc:
                last_error = CoreError(
                    f"CoreClient: request error on {url} " f"(attempt {attempt}/{self.max_retries}): {exc}"
                )
                logger.warning(str(last_error))
                self._backoff(attempt)

        if isinstance(last_error, CoreTimeoutError):
            raise last_error
        raise CoreError(f"CoreClient: all {self.max_retries} retries failed for {url}. " f"Last error: {last_error}")

    async def _get_with_retry(self, path: str) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug("CoreClient GET %s attempt %d/%d", path, attempt, self.max_retries)
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url)

                if 400 <= response.status_code < 500:
                    raise CoreError(f"CoreClient: client error {response.status_code} " f"from {url}: {response.text}")
                if response.status_code >= 500:
                    last_error = CoreError(f"CoreClient: server error {response.status_code} from {url}")
                    self._backoff(attempt)
                    continue

                return response.json()

            except httpx.TimeoutException as exc:
                last_error = CoreTimeoutError(
                    f"CoreClient: timeout on {url} " f"(attempt {attempt}/{self.max_retries}): {exc}"
                )
                logger.warning(str(last_error))
                self._backoff(attempt)

            except httpx.RequestError as exc:
                last_error = CoreError(
                    f"CoreClient: request error on {url} " f"(attempt {attempt}/{self.max_retries}): {exc}"
                )
                logger.warning(str(last_error))
                self._backoff(attempt)

        if isinstance(last_error, CoreTimeoutError):
            raise last_error
        raise CoreError(f"CoreClient: all {self.max_retries} retries failed for {url}. " f"Last error: {last_error}")

    @staticmethod
    def _backoff(attempt: int) -> None:
        sleep_time = RETRY_BACKOFF_BASE**attempt
        logger.debug("CoreClient back-off: sleeping %.1fs", sleep_time)
        time.sleep(sleep_time)
