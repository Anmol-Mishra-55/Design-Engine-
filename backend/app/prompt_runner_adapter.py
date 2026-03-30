"""
Prompt Runner Adapter - Day 1 Canonical Implementation

Uses Siddhesh's platform_adapter.py as the EXECUTION AUTHORITY:
  1. Call platform_adapter.run_from_platform() for domain/intent/entity extraction
  2. Convert PromptInstruction → spec_json
  3. Use AI (Groq/OpenAI/Anthropic) to enrich the spec_json
  4. Return deterministic spec_json to Core

Design Engine NO LONGER generates designs independently.
Prompt Runner (via platform_adapter) is the execution authority.
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
    """
    Day 1 Canonical Adapter: Uses Siddhesh's platform_adapter.py
    as the execution authority for all design generation.
    """

    def __init__(self):
        self.platform_adapter = None
        self._initialize_platform_adapter()

    def _initialize_platform_adapter(self):
        """Initialize Siddhesh's platform_adapter.py"""
        try:
            import sys
            from pathlib import Path

            project_root = Path(__file__).resolve().parents[2]
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))

            from platform_adapter import PlatformAdapter

            self.platform_adapter = PlatformAdapter()
            logger.info("✅ Prompt Runner: Siddhesh's platform_adapter initialized")

        except ImportError as e:
            logger.error(f"❌ Failed to import platform_adapter.py: {e}")
            raise PromptRunnerUnavailableError(f"Cannot load platform_adapter.py: {e}")

    async def run_from_platform(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        DAY 1 CANONICAL FLOW:
        1. Call Siddhesh's platform_adapter.run_from_platform() (execution authority)
        2. Extract PromptInstruction (domain/intent/entities)
        3. Convert to spec_json using AI enrichment
        4. Return deterministic spec_json
        """
        prompt = str(payload.get("prompt", "")).strip()
        city = payload.get("city") or "Mumbai"
        style = payload.get("style") or "modern"
        user_id = payload.get("user_id") or "unknown"
        constraints = payload.get("constraints") if isinstance(payload.get("constraints"), dict) else {}
        context = payload.get("context") if isinstance(payload.get("context"), dict) else {}

        logger.info(f"🎯 Day 1 Flow: Calling platform_adapter.run_from_platform()")

        # STEP 1: Call Siddhesh's platform_adapter (EXECUTION AUTHORITY)
        try:
            platform_result = self.platform_adapter.process(prompt)

            if platform_result.get("status") != "success":
                raise PromptRunnerUnavailableError(f"Platform adapter failed: {platform_result.get('error')}")

            instruction = platform_result.get("instruction", {})
            logger.info(f"✅ Platform adapter: module={instruction.get('module')}, intent={instruction.get('intent')}")

        except Exception as exc:
            logger.error(f"❌ Platform adapter failed: {exc}")
            raise PromptRunnerUnavailableError(f"Platform adapter execution failed: {exc}")

        # STEP 2: Convert PromptInstruction → spec_json
        spec_json = await self._instruction_to_spec_json(
            instruction=instruction, prompt=prompt, city=city, style=style, constraints=constraints, context=context
        )

        digest = self._deterministic_hash(payload)

        metadata = spec_json.setdefault("metadata", {})
        metadata["execution_authority"] = "platform_adapter"
        metadata["prompt_runner_module"] = instruction.get("module")
        metadata["prompt_runner_intent"] = instruction.get("intent")
        metadata["deterministic_hash"] = digest

        logger.info(f"✅ Day 1 complete: design_type={spec_json.get('design_type')}")

        return {
            "spec_json": spec_json,
            "provider": "platform_adapter",
            "execution_mode": "canonical",
            "deterministic_hash": digest,
        }

    # ------------------------------------------------------------------
    # Convert PromptInstruction → spec_json (with AI enrichment)
    # ------------------------------------------------------------------

    async def _instruction_to_spec_json(
        self,
        instruction: Dict[str, Any],
        prompt: str,
        city: str,
        style: str,
        constraints: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Convert Siddhesh's PromptInstruction to Design Engine spec_json format.
        Uses AI (Groq/OpenAI/Anthropic) to enrich the specification.
        """
        # Extract from PromptInstruction
        data = instruction.get("data", {})
        parameters = data.get("parameters", {})
        module = instruction.get("module", "general_processor")
        intent = instruction.get("intent", "design_creation")

        # Determine design_type from module/intent
        design_type = self._infer_design_type(module, intent, prompt, parameters)

        # Extract dimensions from parameters or use AI
        dimensions = await self._extract_dimensions(parameters, prompt, constraints, context)

        # Build base spec_json
        spec_json = {
            "design_type": design_type,
            "city": city,
            "style": style,
            "dimensions": dimensions,
            "units": "meters",
            "stories": self._extract_stories(parameters, prompt),
        }

        # Use AI to enrich with rooms/objects if architecture domain
        if module == "architecture" or "architecture" in str(instruction.get("module", "")):
            enriched = await self._ai_enrich_spec(spec_json, prompt, parameters)
            spec_json.update(enriched)
        else:
            # Basic rooms/objects for non-architecture
            spec_json["rooms"] = []
            spec_json["objects"] = [
                {"type": "wall", "id": "walls", "count": 4},
                {"type": "floor", "id": "floor", "dimensions": dimensions},
            ]

        return spec_json

    def _infer_design_type(self, module: str, intent: str, prompt: str, parameters: Dict) -> str:
        """Infer design_type from PromptInstruction"""
        prompt_lower = prompt.lower()

        # Check parameters first
        if "design_type" in parameters:
            return str(parameters["design_type"])

        # Pattern matching
        if any(word in prompt_lower for word in ["apartment", "flat", "bhk"]):
            return "apartment"
        elif any(word in prompt_lower for word in ["house", "villa", "bungalow"]):
            return "house"
        elif "office" in prompt_lower:
            return "office"
        elif "kitchen" in prompt_lower:
            return "kitchen"
        else:
            return "house"  # default

    async def _extract_dimensions(
        self, parameters: Dict[str, Any], prompt: str, constraints: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, float]:
        """Extract dimensions from parameters or prompt"""
        dimensions = {}

        # Try parameters first (from platform_adapter)
        for key in ["width", "length", "height", "plot_area"]:
            val = parameters.get(key)
            if isinstance(val, (int, float)) and val > 0:
                dimensions[key] = float(val)

        # Try constraints
        if not dimensions:
            for key in ["width", "length", "height"]:
                val = constraints.get(key)
                if isinstance(val, (int, float)) and val > 0:
                    dimensions[key] = float(val)

        # Parse from prompt using regex
        if not dimensions:
            pattern = r"(\d+(?:\.\d+)?)\s*(?:x|by|×)\s*(\d+(?:\.\d+)?)"
            match = re.search(pattern, prompt.lower())
            if match:
                dimensions["width"] = float(match.group(1))
                dimensions["length"] = float(match.group(2))

        # Defaults
        dimensions.setdefault("width", 10.0)
        dimensions.setdefault("length", 10.0)
        dimensions.setdefault("height", 3.0)

        return dimensions

    def _extract_stories(self, parameters: Dict[str, Any], prompt: str) -> int:
        """Extract number of stories"""
        stories = parameters.get("stories") or parameters.get("floors")
        if isinstance(stories, int) and stories > 0:
            return stories

        # Parse from prompt
        match = re.search(r"(\d+)\s*(?:stor(?:ey|y|ies)|floor)", prompt.lower())
        if match:
            return int(match.group(1))

        return 1

    async def _ai_enrich_spec(self, base_spec: Dict[str, Any], prompt: str, parameters: Dict) -> Dict[str, Any]:
        """Use AI (Groq/OpenAI/Anthropic) to enrich spec with rooms/objects"""
        try:
            from app.lm_adapter import run_local_lm

            enrichment_prompt = f"""Based on this design request: {prompt}

Generate rooms and objects for a {base_spec['design_type']} design."""

            result = await run_local_lm(enrichment_prompt, parameters)
            ai_spec = result.get("spec_json", {})

            return {
                "rooms": ai_spec.get("rooms", []),
                "objects": ai_spec.get("objects", []),
            }
        except Exception as e:
            logger.warning(f"AI enrichment failed: {e}, using basic structure")
            return {
                "rooms": [],
                "objects": [{"type": "wall", "id": "walls", "count": 4}],
            }

    def _deterministic_hash(self, payload: Dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, default=str).encode("utf-8", errors="ignore")
        return hashlib.sha256(canonical).hexdigest()[:16]
