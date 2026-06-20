"""
PromptRunnerClient
==================
HTTP client for Siddhesh's Prompt Runner service.
Base URL : https://prompt-runner.onrender.com

Endpoints:
  POST /generate  — converts prompt → {prompt, module, intent, topic, tasks, output_format, product_context}
  POST /convert   — compatibility alias for /generate, same response shape

Retry  : 3 attempts with exponential back-off
Timeout: 30 s per request

Live response schema (confirmed against https://prompt-runner.onrender.com/docs):
  {
    "prompt":          str,
    "module":          str,
    "intent":          str,
    "topic":           str,
    "tasks":           [str, ...],
    "output_format":   str,
    "product_context": str   # always "creator_core"
  }
"""

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

BASE_URL = "https://prompt-runner.onrender.com"
TIMEOUT_SECONDS = 30
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds  (2, 4, 8 …)

# ── Exceptions ───────────────────────────────────────────────────────────────


class PromptRunnerError(Exception):
    """Raised when the Prompt Runner returns an error or unreachable."""


class PromptRunnerValidationError(PromptRunnerError):
    """Raised when the response schema is invalid."""


class PromptRunnerTimeoutError(PromptRunnerError):
    """Raised when the request times out after all retries."""


# ── Response model (lightweight, no pydantic dependency required) ────────────


class GenerateInstructionResponse:
    """
    Validated wrapper around /generate and /convert response.

    Confirmed live schema from https://prompt-runner.onrender.com/docs:
      prompt, module, intent, topic, tasks, output_format, product_context
    """

    REQUIRED_FIELDS = ("module", "intent", "topic", "tasks", "output_format")

    def __init__(self, raw: Dict[str, Any]):
        self._validate(raw)
        self.prompt: str = raw.get("prompt", "")
        self.module: str = raw["module"]
        self.intent: str = raw["intent"]
        self.topic: str = raw["topic"]
        self.tasks: List[str] = raw["tasks"]
        self.output_format: str = raw["output_format"]
        self.product_context: str = raw.get("product_context", "creator_core")
        self._raw = raw

    def _validate(self, raw: Dict[str, Any]) -> None:
        missing = [f for f in self.REQUIRED_FIELDS if f not in raw]
        if missing:
            raise PromptRunnerValidationError(f"Response missing required fields: {missing}. Got: {list(raw.keys())}")
        if not isinstance(raw["tasks"], list):
            raise PromptRunnerValidationError(f"'tasks' must be a list, got {type(raw['tasks']).__name__}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt": self.prompt,
            "module": self.module,
            "intent": self.intent,
            "topic": self.topic,
            "tasks": self.tasks,
            "output_format": self.output_format,
            "product_context": self.product_context,
        }

    def __repr__(self) -> str:
        return (
            f"GenerateInstructionResponse("
            f"module={self.module!r}, intent={self.intent!r}, "
            f"topic={self.topic!r}, tasks={self.tasks}, "
            f"output_format={self.output_format!r})"
        )


# ── Client ───────────────────────────────────────────────────────────────────


class PromptRunnerClient:
    """
    Stateless HTTP client for the Prompt Runner service.

    Usage::

        client = PromptRunnerClient()
        result = await client.generate_instruction("Design a 2BHK apartment in Mumbai")
        print(result.module, result.intent, result.topic, result.tasks)
    """

    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: float = TIMEOUT_SECONDS,
        max_retries: int = MAX_RETRIES,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    # ── Public API ───────────────────────────────────────────────────────────

    async def generate_instruction(self, prompt: str, model: Optional[str] = None) -> GenerateInstructionResponse:
        """
        POST /generate

        Sends {"prompt": prompt, "model": model} and returns a validated
        GenerateInstructionResponse.

        Live response fields: prompt, module, intent, topic, tasks,
                              output_format, product_context

        Raises:
            PromptRunnerTimeoutError    – all retries exhausted due to timeout
            PromptRunnerError           – HTTP error or unexpected failure
            PromptRunnerValidationError – response schema mismatch
        """
        payload: Dict[str, Any] = {"prompt": prompt}
        if model is not None:
            payload["model"] = model
        raw = await self._post_with_retry("/generate", payload)
        return GenerateInstructionResponse(raw)

    async def convert(self, prompt: str, model: Optional[str] = None) -> GenerateInstructionResponse:
        """
        POST /convert

        Compatibility alias for /generate — same request/response shape.
        Returns a validated GenerateInstructionResponse.

        Raises:
            PromptRunnerTimeoutError
            PromptRunnerError
            PromptRunnerValidationError
        """
        payload: Dict[str, Any] = {"prompt": prompt}
        if model is not None:
            payload["model"] = model
        raw = await self._post_with_retry("/convert", payload)
        return GenerateInstructionResponse(raw)

    # ── Internal helpers ─────────────────────────────────────────────────────

    async def _post_with_retry(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        POST ``payload`` to ``self.base_url + path`` with retry logic.

        Retry policy:
          - Retries on httpx.TimeoutException and 5xx responses
          - Exponential back-off: RETRY_BACKOFF_BASE ** attempt seconds
          - Does NOT retry on 4xx (client errors)
        """
        url = f"{self.base_url}{path}"
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug("PromptRunner %s attempt %d/%d", path, attempt, self.max_retries)
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, json=payload)

                # 4xx → do not retry, raise immediately
                if 400 <= response.status_code < 500:
                    raise PromptRunnerError(f"Client error {response.status_code} from {url}: {response.text}")

                # 5xx → retry
                if response.status_code >= 500:
                    last_error = PromptRunnerError(f"Server error {response.status_code} from {url}: {response.text}")
                    logger.warning(
                        "PromptRunner %s → %d (attempt %d), retrying…",
                        path,
                        response.status_code,
                        attempt,
                    )
                    self._backoff(attempt)
                    continue

                # 2xx → parse and return
                return response.json()

            except httpx.TimeoutException as exc:
                last_error = PromptRunnerTimeoutError(f"Timeout on {url} (attempt {attempt}/{self.max_retries}): {exc}")
                logger.warning(str(last_error))
                self._backoff(attempt)

            except httpx.RequestError as exc:
                last_error = PromptRunnerError(f"Request error on {url} (attempt {attempt}/{self.max_retries}): {exc}")
                logger.warning(str(last_error))
                self._backoff(attempt)

        # All retries exhausted
        if isinstance(last_error, PromptRunnerTimeoutError):
            raise last_error
        raise PromptRunnerError(f"All {self.max_retries} retries failed for {url}. Last error: {last_error}")

    @staticmethod
    def _backoff(attempt: int) -> None:
        """Exponential back-off sleep between retries."""
        sleep_time = RETRY_BACKOFF_BASE**attempt
        logger.debug("Back-off: sleeping %.1fs before next retry", sleep_time)
        time.sleep(sleep_time)
