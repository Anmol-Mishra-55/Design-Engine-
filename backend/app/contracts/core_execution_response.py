"""
CoreExecutionResponse
=====================
TANTRA execution contract for outbound responses from Core.

Required fields (raise ValidationError if missing or empty):
  - task_id
  - trace_id

status must be one of: success | failed | pending | rejected
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from .core_execution_request import ValidationError

VALID_STATUSES = {"success", "failed", "pending", "rejected"}


@dataclass
class CoreExecutionResponse:
    """
    Outbound execution contract returned by TANTRA Core.

    Usage::

        resp = CoreExecutionResponse(
            task_id="task_001",
            agent_output={"spec": {...}},
            status="success",
            trace_id="trace_xyz789",
            bucket_write="bucket://outputs/task_001.glb",
        )

    Raises:
        ValidationError: if task_id or trace_id are missing/empty,
                         or status is not a recognised value.
    """

    # ── Required ──────────────────────────────────────────────────────────────
    task_id: str
    trace_id: str
    status: str

    # ── Optional with defaults ────────────────────────────────────────────────
    agent_output: Dict[str, Any] = field(default_factory=dict)
    bucket_write: str = field(default="")

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if not self.task_id or not str(self.task_id).strip():
            raise ValidationError("CoreExecutionResponse: 'task_id' is required and cannot be empty.")
        if not self.trace_id or not str(self.trace_id).strip():
            raise ValidationError("CoreExecutionResponse: 'trace_id' is required and cannot be empty.")
        if self.status not in VALID_STATUSES:
            raise ValidationError(
                f"CoreExecutionResponse: 'status' must be one of {sorted(VALID_STATUSES)}, " f"got {self.status!r}."
            )
        if not isinstance(self.agent_output, dict):
            raise ValidationError(
                f"CoreExecutionResponse: 'agent_output' must be a dict, " f"got {type(self.agent_output).__name__}."
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_output": self.agent_output,
            "status": self.status,
            "trace_id": self.trace_id,
            "bucket_write": self.bucket_write,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CoreExecutionResponse":
        return cls(
            task_id=data.get("task_id", ""),
            agent_output=data.get("agent_output", {}),
            status=data.get("status", ""),
            trace_id=data.get("trace_id", ""),
            bucket_write=data.get("bucket_write", ""),
        )

    @classmethod
    def success(
        cls,
        task_id: str,
        trace_id: str,
        agent_output: Dict[str, Any],
        bucket_write: str = "",
    ) -> "CoreExecutionResponse":
        """Convenience constructor for a successful response."""
        return cls(
            task_id=task_id,
            trace_id=trace_id,
            status="success",
            agent_output=agent_output,
            bucket_write=bucket_write,
        )

    @classmethod
    def failed(
        cls,
        task_id: str,
        trace_id: str,
        reason: str = "",
    ) -> "CoreExecutionResponse":
        """Convenience constructor for a failed response."""
        return cls(
            task_id=task_id,
            trace_id=trace_id,
            status="failed",
            agent_output={"error": reason},
            bucket_write="",
        )
