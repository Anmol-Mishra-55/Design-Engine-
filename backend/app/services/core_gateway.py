"""
CoreGateway
===========
Enforces the TANTRA generation pipeline order:

    Prompt → CoreGateway → PromptRunnerClient → SemanticResolver

Rules:
  - PromptRunnerClient is NEVER called directly by external code.
  - CoreGateway must obtain Core authorization (execute_task status=success)
    before dispatching to PromptRunnerClient.
  - If Core rejects (status != success), PromptRunnerClient is never called
    and CoreGatewayAuthError is raised immediately.

Public API:
    gateway = CoreGateway()
    result  = await gateway.run(prompt="Design a 2BHK flat", trace_id="trace_001")

Returns:
    {
        "authorization":    CoreExecutionResponse   (Core auth receipt),
        "prompt_runner":    GenerateInstructionResponse,
        "semantic":         { domain, entity, generation_mode, geometry_family },
    }

Exceptions:
    CoreGatewayAuthError    — Core rejected or failed; Prompt Runner not called
    CoreGatewayError        — unexpected pipeline failure
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from ..contracts.core_execution_request import CoreExecutionRequest
from ..contracts.core_execution_response import CoreExecutionResponse
from ..design_semantics.semantic_resolver import SemanticResolutionError, SemanticResolver
from ..services.core_client import CoreClient, CoreError
from ..services.prompt_runner_client import GenerateInstructionResponse, PromptRunnerClient, PromptRunnerError

logger = logging.getLogger(__name__)

# ── Exceptions ────────────────────────────────────────────────────────────────


class CoreGatewayError(Exception):
    """Unexpected pipeline failure inside CoreGateway."""


class CoreGatewayAuthError(CoreGatewayError):
    """
    Core rejected or failed authorization.
    PromptRunnerClient was NOT called.
    """

    def __init__(self, message: str, core_response: Optional[CoreExecutionResponse] = None) -> None:
        super().__init__(message)
        self.core_response = core_response


# ── Gateway ───────────────────────────────────────────────────────────────────


class CoreGateway:
    """
    Single entry point for the TANTRA generation pipeline.

    PromptRunnerClient must never be instantiated or called outside this class.

    Usage::

        gateway = CoreGateway()
        result = await gateway.run("Design a 2BHK flat", trace_id="trace_001")

        print(result["semantic"]["domain"])          # architecture
        print(result["prompt_runner"].module)        # architecture
        print(result["authorization"].status)        # success
    """

    _AUTHORIZATION_AGENT = "prompt_runner_gateway"

    def __init__(
        self,
        core_client: Optional[CoreClient] = None,
        prompt_runner_client: Optional[PromptRunnerClient] = None,
        semantic_resolver: Optional[SemanticResolver] = None,
    ) -> None:
        self._core = core_client or CoreClient()
        self._prompt_runner = prompt_runner_client or PromptRunnerClient()
        self._resolver = semantic_resolver or SemanticResolver()

    # ── Public API ────────────────────────────────────────────────────────────

    async def run(
        self,
        prompt: str,
        trace_id: Optional[str] = None,
        task_id: Optional[str] = None,
        tags: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Execute the full generation pipeline.

        Step 1 — Authorize with Core (POST /execute_task).
                 If Core returns status != 'success', raise CoreGatewayAuthError.
                 PromptRunnerClient is NEVER called in this case.

        Step 2 — Call PromptRunnerClient.generate_instruction(prompt).
                 Only reached if Step 1 succeeded.

        Step 3 — Resolve semantic context via SemanticResolver.

        Args:
            prompt:   User's raw generation prompt.
            trace_id: Trace ID; auto-generated if not provided.
            task_id:  Task ID; auto-generated if not provided.
            tags:     Optional tags attached to the Core request.

        Returns:
            {
                "authorization": CoreExecutionResponse,
                "prompt_runner": GenerateInstructionResponse,
                "semantic":      { domain, entity, generation_mode, geometry_family },
            }

        Raises:
            CoreGatewayAuthError — Core rejected; Prompt Runner not called.
            CoreGatewayError     — Pipeline failure after authorization.
        """
        trace_id = trace_id or CoreExecutionRequest.generate_trace_id()
        task_id = task_id or f"task_{uuid.uuid4().hex[:12]}"

        # ── Step 1: Core authorization ────────────────────────────────────────
        auth_response = await self._authorize(prompt, trace_id, task_id, tags or [])

        # ── Step 2: Prompt Runner (only if authorized) ────────────────────────
        pr_response = await self._call_prompt_runner(prompt, trace_id, task_id)

        # ── Step 3: Semantic resolution ───────────────────────────────────────
        semantic = self._resolve_semantic(pr_response, trace_id, task_id)

        logger.info(
            "CoreGateway pipeline complete: trace=%s task=%s domain=%s entity=%s",
            trace_id,
            task_id,
            semantic.get("domain"),
            semantic.get("entity"),
        )

        return {
            "authorization": auth_response,
            "prompt_runner": pr_response,
            "semantic": semantic,
        }

    # ── Private pipeline steps ────────────────────────────────────────────────

    async def _authorize(
        self,
        prompt: str,
        trace_id: str,
        task_id: str,
        tags: list,
    ) -> CoreExecutionResponse:
        """
        POST to Core /execute_task for authorization.
        Raises CoreGatewayAuthError if Core does not return status='success'.
        """
        auth_request = CoreExecutionRequest(
            input=prompt,
            agent=self._AUTHORIZATION_AGENT,
            execution_token=CoreExecutionRequest.generate_token(),
            trace_id=trace_id,
            task_id=task_id,
            input_type="prompt",
            tags=tags,
            retries=3,
            fallback_agent="",
        )

        try:
            response = await self._core.execute_task(auth_request)
        except CoreError as exc:
            raise CoreGatewayAuthError(f"CoreGateway: Core authorization failed — {exc}") from exc

        if response.status != "success":
            raise CoreGatewayAuthError(
                f"CoreGateway: Core rejected with status='{response.status}'. " f"PromptRunner will not be called.",
                core_response=response,
            )

        logger.info(
            "CoreGateway: Core authorized trace=%s task=%s status=%s",
            trace_id,
            task_id,
            response.status,
        )
        return response

    async def _call_prompt_runner(
        self,
        prompt: str,
        trace_id: str,
        task_id: str,
    ) -> GenerateInstructionResponse:
        """Call PromptRunnerClient. Only reached after successful Core auth."""
        try:
            response = await self._prompt_runner.generate_instruction(prompt)
        except PromptRunnerError as exc:
            raise CoreGatewayError(
                f"CoreGateway: PromptRunner failed for trace={trace_id} task={task_id} — {exc}"
            ) from exc

        logger.info(
            "CoreGateway: PromptRunner responded module=%s topic=%s trace=%s",
            response.module,
            response.topic,
            trace_id,
        )
        return response

    def _resolve_semantic(
        self,
        pr_response: GenerateInstructionResponse,
        trace_id: str,
        task_id: str,
    ) -> Dict[str, str]:
        """Resolve semantic context from PromptRunner response."""
        try:
            return self._resolver.resolve(pr_response.to_dict())
        except SemanticResolutionError as exc:
            raise CoreGatewayError(
                f"CoreGateway: SemanticResolver failed for trace={trace_id} task={task_id} — {exc}"
            ) from exc
