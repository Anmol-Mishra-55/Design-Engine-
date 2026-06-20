"""
CoreExecutionRequest
====================
TANTRA execution contract for inbound requests to Core.

Required fields (raise ValidationError if missing or empty):
  - execution_token
  - trace_id

All other fields have sensible defaults.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class ValidationError(Exception):
    """Raised when a required contract field is missing or invalid."""


@dataclass
class CoreExecutionRequest:
    """
    Inbound execution contract passed to TANTRA Core.

    Usage::

        req = CoreExecutionRequest(
            input="Design a 2BHK apartment",
            agent="architecture_generator",
            execution_token="tok_abc123",
            trace_id="trace_xyz789",
        )

    Raises:
        ValidationError: if execution_token or trace_id are missing/empty.
    """

    # ── Required ──────────────────────────────────────────────────────────────
    input: str
    agent: str
    execution_token: str
    trace_id: str

    # ── Optional with defaults ────────────────────────────────────────────────
    task_id: Optional[str] = field(default=None)
    input_type: str = field(default="text")
    tags: List[str] = field(default_factory=list)
    retries: int = field(default=0)
    fallback_agent: str = field(default="")

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if not self.execution_token or not str(self.execution_token).strip():
            raise ValidationError("CoreExecutionRequest: 'execution_token' is required and cannot be empty.")
        if not self.trace_id or not str(self.trace_id).strip():
            raise ValidationError("CoreExecutionRequest: 'trace_id' is required and cannot be empty.")
        if not isinstance(self.retries, int) or self.retries < 0:
            raise ValidationError(f"CoreExecutionRequest: 'retries' must be a non-negative int, got {self.retries!r}.")
        if not isinstance(self.tags, list):
            raise ValidationError(f"CoreExecutionRequest: 'tags' must be a list, got {type(self.tags).__name__}.")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input": self.input,
            "agent": self.agent,
            "task_id": self.task_id,
            "input_type": self.input_type,
            "tags": self.tags,
            "retries": self.retries,
            "fallback_agent": self.fallback_agent,
            "execution_token": self.execution_token,
            "trace_id": self.trace_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CoreExecutionRequest":
        return cls(
            input=data.get("input", ""),
            agent=data.get("agent", ""),
            execution_token=data.get("execution_token", ""),
            trace_id=data.get("trace_id", ""),
            task_id=data.get("task_id"),
            input_type=data.get("input_type", "text"),
            tags=data.get("tags", []),
            retries=data.get("retries", 0),
            fallback_agent=data.get("fallback_agent", ""),
        )

    @staticmethod
    def generate_token() -> str:
        """Generate a new unique execution token."""
        return f"tok_{uuid.uuid4().hex[:16]}"

    @staticmethod
    def generate_trace_id() -> str:
        """Generate a new unique trace ID."""
        return f"trace_{uuid.uuid4().hex[:16]}"
