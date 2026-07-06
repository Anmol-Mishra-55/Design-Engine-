"""
DKB Runtime Request Models

Wraps the Prompt Runner output contract into a typed input for DKBRuntime.

Prompt Runner returns:
    { module, intent, topic, tasks, output_format, product_context }

DKBRuntime accepts a PromptInstruction built from that response.
The runtime never calls Prompt Runner — it only consumes its output.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PromptInstruction(BaseModel):
    """
    Typed representation of a Prompt Runner instruction.

    Fields map directly to the confirmed Prompt Runner live response schema.
    The runtime uses `topic` as the DKB search query.

    Attributes
    ----------
    module:          Prompt Runner module (e.g. "architecture", "design")
    intent:          Prompt Runner intent (e.g. "generate", "create")
    topic:           The resolved topic — used as the DKB search query
    tasks:           List of task strings from Prompt Runner
    output_format:   Requested output format (e.g. "3d_model", "floor_plan")
    product_context: Always "creator_core" from Prompt Runner
    parameters:      Optional extra parameters passed alongside the instruction
    """

    module: str
    intent: str
    topic: str
    tasks: List[str] = Field(default_factory=list)
    output_format: str = "3d_model"
    product_context: str = "creator_core"
    parameters: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_prompt_runner(cls, raw: Dict[str, Any]) -> "PromptInstruction":
        """
        Build a PromptInstruction from a raw Prompt Runner response dict.

        Args:
            raw: The dict returned by Prompt Runner's /generate or /convert endpoint.

        Returns:
            PromptInstruction ready for DKBRuntime.execute().

        Raises:
            ValueError: if required fields (module, intent, topic) are missing.
        """
        missing = [f for f in ("module", "intent", "topic") if not raw.get(f)]
        if missing:
            raise ValueError(f"Prompt Runner response missing required fields: {missing}. Got: {list(raw.keys())}")
        return cls(
            module=raw["module"],
            intent=raw["intent"],
            topic=raw["topic"],
            tasks=raw.get("tasks", []),
            output_format=raw.get("output_format", "3d_model"),
            product_context=raw.get("product_context", "creator_core"),
            parameters=raw.get("parameters", {}),
        )
