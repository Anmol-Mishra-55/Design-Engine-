"""
Prompt Runner adapter bridge.

Execution priority:
  1. Real AI generation via lm_adapter (Groq llama-3.3-70b → OpenAI gpt-4o-mini → Anthropic claude)
  2. Enhanced template fallback (lm_adapter_enhanced) if all AI keys are missing/exhausted
  3. Basic template fallback as last resort

Platform adapter (platform_adapter.py) is used for domain/intent/entity extraction
to enrich the AI prompt context — it is NOT the spec generator.
"""

import hashlib
import json
import logging
import re
from typing import Any, Dict

from app.config import settings

logger = logging.getLogger(__name__)


class PromptRunnerUnavailableError(RuntimeError):
    """Raised when the prompt runner pipeline fails unrecoverably."""


class PromptRunnerAdapterBridge:
    """Bridge that routes generate requests through the real AI pipeline."""

    def __init__(self):
        self.mode = getattr(settings, "PROMPT_RUNNER_MODE", "ai").lower()

    async def run_from_platform(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a spec_json from the request payload.

        Priority:
          1. Groq llama-3.3-70b  (if GROQ_API_KEY set)
          2. OpenAI gpt-4o-mini  (if OPENAI_API_KEY set)
          3. Anthropic claude    (if ANTHROPIC_API_KEY set)
          4. Enhanced template fallback
          5. Basic template fallback
        """
        prompt = str(payload.get("prompt", "")).strip()
        city = payload.get("city") or "Mumbai"
        style = payload.get("style") or "modern"
        user_id = payload.get("user_id") or "unknown"
        constraints = payload.get("constraints") if isinstance(payload.get("constraints"), dict) else {}
        context = payload.get("context") if isinstance(payload.get("context"), dict) else {}

        # Enrich params with platform adapter entities (domain/intent/dimensions)
        enriched_params = self._enrich_with_platform_adapter(prompt, city, style, user_id, constraints, context)

        # Call the real AI pipeline
        from app.lm_adapter import run_local_lm

        try:
            lm_result = await run_local_lm(prompt, enriched_params)
        except Exception as exc:
            logger.error("lm_adapter.run_local_lm failed: %s", exc)
            raise PromptRunnerUnavailableError(f"AI generation pipeline failed: {exc}") from exc

        spec_json = lm_result.get("spec_json")
        if not isinstance(spec_json, dict):
            raise PromptRunnerUnavailableError("AI pipeline returned invalid spec_json")

        provider = lm_result.get("provider", "unknown")
        digest = self._deterministic_hash(payload)

        # Ensure required structural fields
        spec_json.setdefault("city", city)
        spec_json.setdefault("style", style)
        spec_json.setdefault("stories", 1)

        dimensions = spec_json.setdefault("dimensions", {})
        for key, default in (("width", 10.0), ("length", 10.0), ("height", 3.0)):
            if not isinstance(dimensions.get(key), (int, float)) or dimensions[key] <= 0:
                dimensions[key] = default

        metadata = spec_json.setdefault("metadata", {})
        metadata["execution_source"] = provider
        metadata["deterministic_hash"] = digest

        logger.info("✅ generate pipeline complete — provider=%s", provider)

        return {
            "spec_json": spec_json,
            "provider": provider,
            "execution_mode": "canonical",
            "deterministic_hash": digest,
        }

    # ------------------------------------------------------------------
    # Platform adapter enrichment (domain/intent/entity extraction only)
    # ------------------------------------------------------------------

    def _enrich_with_platform_adapter(
        self,
        prompt: str,
        city: str,
        style: str,
        user_id: str,
        constraints: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Use platform_adapter for NLP entity extraction to enrich the params
        passed to the AI model. Never used as the spec generator.
        """
        params: Dict[str, Any] = {
            "city": city,
            "style": style,
            "user_id": user_id,
            "constraints": constraints,
            "context": context,
        }

        try:
            import sys
            from pathlib import Path

            project_root = Path(__file__).resolve().parents[2]
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))

            from platform_adapter import run_prompt

            result = run_prompt(prompt)
            if result.get("status") == "success":
                instruction = result.get("instruction", {})
                data = instruction.get("data", {})
                extracted_params = data.get("parameters", {})

                # Pull out dimensions if the platform adapter found them
                dims = {}
                for key in ("width", "length", "height", "plot_area", "floors", "stories"):
                    val = extracted_params.get(key)
                    if isinstance(val, (int, float)) and val > 0:
                        dims[key] = val

                if dims:
                    params["extracted_dimensions"] = dims
                    logger.info("Platform adapter extracted dimensions: %s", dims)

                # Merge any budget/style hints
                budget = extracted_params.get("budget")
                if isinstance(budget, (int, float)) and budget > 0:
                    params.setdefault("context", {})["budget"] = budget

        except Exception as exc:
            logger.debug("Platform adapter enrichment skipped: %s", exc)

        return params

    def _deterministic_hash(self, payload: Dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, default=str).encode("utf-8", errors="ignore")
        return hashlib.sha256(canonical).hexdigest()[:16]
