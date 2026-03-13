"""
Prompt Runner adapter bridge.

This module is the only allowed integration touchpoint for Prompt Runner.
When Siddhesh's repository is available, set:
- PROMPT_RUNNER_MODE=external
- PROMPT_RUNNER_REPO_PATH=<repo_path>
- PROMPT_RUNNER_MODULE=platform_adapter
- PROMPT_RUNNER_ENTRYPOINT=run_from_platform
"""

import hashlib
import importlib
import inspect
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class PromptRunnerUnavailableError(RuntimeError):
    """Raised when external Prompt Runner adapter is required but unavailable."""


class PromptRunnerAdapterBridge:
    """Bridge for Prompt Runner's `run_from_platform()` contract."""

    def __init__(self):
        self.mode = getattr(settings, "PROMPT_RUNNER_MODE", "stub").lower()
        self.repo_path = getattr(settings, "PROMPT_RUNNER_REPO_PATH", None)
        self.module_name = getattr(settings, "PROMPT_RUNNER_MODULE", "platform_adapter")
        self.entrypoint = getattr(settings, "PROMPT_RUNNER_ENTRYPOINT", "run_from_platform")

    async def run_from_platform(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Prompt Runner via canonical adapter contract.
        Falls back to deterministic stub mode when configured.
        """
        runner = self._load_external_runner()
        if runner:
            logger.info("Prompt Runner adapter loaded in external mode")
            result = runner(payload)
            if inspect.isawaitable(result):
                result = await result
            normalized = self._normalize_result(result, payload, provider="prompt_runner_external")
            return normalized

        if self.mode == "external":
            raise PromptRunnerUnavailableError(
                "Prompt Runner is configured as external but platform_adapter.run_from_platform() is unavailable"
            )

        logger.warning("Prompt Runner external adapter unavailable, using deterministic stub mode")
        return self._build_stub_result(payload)

    def _load_external_runner(self) -> Optional[Callable[..., Any]]:
        """Load external Prompt Runner adapter function."""
        try:
            # First try to import the platform_adapter with run_prompt function
            try:
                # Import from project root
                import sys
                from pathlib import Path

                project_root = Path(__file__).resolve().parents[2]  # Go up to Backend/
                if str(project_root) not in sys.path:
                    sys.path.insert(0, str(project_root))

                from platform_adapter import run_prompt

                logger.info("Successfully imported run_prompt from platform_adapter")
                return self._wrap_run_prompt(run_prompt)
            except ImportError as e:
                logger.info(f"platform_adapter.run_prompt not available: {e}, trying external path")

            # Fallback to original external loading logic
            if self.repo_path:
                repo = Path(self.repo_path).expanduser()
                if repo.exists():
                    repo_str = str(repo.resolve())
                    if repo_str not in sys.path:
                        sys.path.insert(0, repo_str)
                else:
                    logger.warning("PROMPT_RUNNER_REPO_PATH does not exist: %s", repo)

            module = importlib.import_module(self.module_name)
            runner = getattr(module, self.entrypoint, None)
            if not callable(runner):
                logger.warning("%s.%s is missing or not callable", self.module_name, self.entrypoint)
                return None
            return runner
        except Exception as exc:
            logger.warning("Unable to load Prompt Runner adapter: %s", exc)
            return None

    def _normalize_result(self, result: Any, payload: Dict[str, Any], provider: str) -> Dict[str, Any]:
        """Normalize adapter output to a strict response envelope."""
        if not isinstance(result, dict):
            raise PromptRunnerUnavailableError("Prompt Runner adapter returned non-dict payload")

        spec_json = result.get("spec_json")
        if not isinstance(spec_json, dict):
            raise PromptRunnerUnavailableError("Prompt Runner adapter response missing `spec_json`")

        dimensions = spec_json.setdefault("dimensions", {})
        for key, default in (("width", 10.0), ("length", 10.0), ("height", 3.0)):
            value = dimensions.get(key)
            if not isinstance(value, (int, float)) or value <= 0:
                dimensions[key] = default

        metadata = spec_json.setdefault("metadata", {})
        metadata["execution_source"] = provider
        metadata["deterministic_hash"] = self._deterministic_hash(payload)

        result.setdefault("provider", provider)
        result.setdefault("execution_mode", "canonical")
        return result

    def _build_stub_result(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Deterministic fallback until external Prompt Runner repo is available."""
        prompt = str(payload.get("prompt", "")).strip()
        city = payload.get("city") or "Mumbai"
        style = payload.get("style") or "modern"
        user_id = payload.get("user_id") or "unknown_user"
        constraints = payload.get("constraints") if isinstance(payload.get("constraints"), dict) else {}
        context = payload.get("context") if isinstance(payload.get("context"), dict) else {}

        design_type = self._detect_design_type(prompt)
        dims = self._extract_dimensions(prompt, constraints, context, design_type)
        digest = self._deterministic_hash(payload)

        objects = [
            {
                "id": "foundation_main",
                "type": "foundation",
                "material": "concrete",
                "dimensions": {"width": dims["width"], "length": dims["length"], "height": 0.5},
            },
            {
                "id": "wall_external",
                "type": "wall",
                "subtype": "external",
                "material": "brick",
                "dimensions": {"width": dims["width"], "length": 0.2, "height": dims["height"]},
            },
            {
                "id": "roof_main",
                "type": "roof",
                "material": "concrete",
                "dimensions": {"width": dims["width"], "length": dims["length"], "height": 0.2},
            },
            {
                "id": "main_door",
                "type": "door",
                "subtype": "entrance",
                "material": "wood_oak",
                "dimensions": {"width": 1.2, "length": 0.05, "height": 2.1},
            },
            {
                "id": "window_standard",
                "type": "window",
                "material": "glass",
                "count": 4,
                "dimensions": {"width": 1.2, "length": 0.1, "height": 1.5},
            },
        ]

        spec_json = {
            "design_type": design_type,
            "style": style,
            "city": city,
            "stories": 1,
            "dimensions": dims,
            "objects": objects,
            "metadata": {
                "execution_source": "prompt_runner_stub",
                "deterministic_hash": digest,
                "user_id": user_id,
                "constraints": constraints,
            },
        }

        return {
            "spec_json": spec_json,
            "provider": "prompt_runner_stub",
            "execution_mode": "canonical",
            "deterministic_hash": digest,
        }

    def _deterministic_hash(self, payload: Dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, default=str).encode("utf-8", errors="ignore")
        return hashlib.sha256(canonical).hexdigest()[:16]

    def _detect_design_type(self, prompt: str) -> str:
        lowered = prompt.lower()
        if "apartment" in lowered or "bhk" in lowered:
            return "apartment"
        if "kitchen" in lowered:
            return "kitchen"
        if "office" in lowered:
            return "office"
        if "villa" in lowered or "house" in lowered:
            return "house"
        return "building"

    def _extract_dimensions(
        self,
        prompt: str,
        constraints: Dict[str, Any],
        context: Dict[str, Any],
        design_type: str,
    ) -> Dict[str, float]:
        defaults = {
            "apartment": {"width": 12.0, "length": 18.0, "height": 3.0},
            "kitchen": {"width": 4.0, "length": 5.0, "height": 3.0},
            "office": {"width": 15.0, "length": 20.0, "height": 3.5},
            "house": {"width": 14.0, "length": 20.0, "height": 6.0},
            "building": {"width": 16.0, "length": 24.0, "height": 8.0},
        }
        dims = dict(defaults.get(design_type, defaults["building"]))

        merged = {}
        merged.update(context.get("dimensions", {}) if isinstance(context.get("dimensions"), dict) else {})
        merged.update(constraints.get("dimensions", {}) if isinstance(constraints.get("dimensions"), dict) else {})
        for key in ("width", "length", "height"):
            value = merged.get(key)
            if isinstance(value, (int, float)) and value > 0:
                dims[key] = float(value)

        match = re.search(r"(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)\s*(?:[xX]\s*(\d+(?:\.\d+)?))?", prompt)
        if match:
            dims["width"] = float(match.group(1))
            dims["length"] = float(match.group(2))
            if match.group(3):
                dims["height"] = float(match.group(3))

            if re.search(r"\b(ft|feet)\b", prompt.lower()):
                dims = {k: round(v * 0.3048, 3) for k, v in dims.items()}

        return dims

    def _wrap_run_prompt(self, run_prompt_func: Callable) -> Callable:
        """Wrap run_prompt function to match expected interface."""

        def wrapper(payload: Dict[str, Any]) -> Dict[str, Any]:
            # Extract prompt from payload
            prompt = payload.get("prompt", "")

            # Call run_prompt with the prompt
            result = run_prompt_func(prompt)

            # Extract instruction from platform adapter response
            if result.get("status") == "success":
                instruction = result.get("instruction", {})

                # Convert instruction to spec_json format
                spec_json = self._convert_instruction_to_spec(instruction, payload)

                return {
                    "spec_json": spec_json,
                    "provider": "platform_adapter",
                    "execution_mode": "canonical",
                    "deterministic_hash": self._deterministic_hash(payload),
                }
            else:
                # If platform adapter fails, fall back to stub
                logger.warning("Platform adapter failed: %s", result.get("error", "Unknown error"))
                return self._build_stub_result(payload)

        return wrapper

    def _convert_instruction_to_spec(self, instruction: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        """Convert platform adapter instruction to spec_json format."""
        data = instruction.get("data", {})
        parameters = data.get("parameters", {})

        # Extract basic info
        city = payload.get("city") or "Mumbai"
        style = payload.get("style") or "modern"

        # Determine design type from instruction
        module = instruction.get("module", "")
        intent = instruction.get("intent", "")
        topic = data.get("topic", "")

        design_type = self._infer_design_type(module, intent, topic, payload.get("prompt", ""))

        # Extract dimensions from parameters or use defaults
        dimensions = self._extract_dimensions_from_parameters(parameters, design_type)

        # Build objects based on design type and parameters
        objects = self._build_objects_from_parameters(parameters, dimensions, design_type)

        spec_json = {
            "design_type": design_type,
            "style": style,
            "city": city,
            "stories": parameters.get("floors") or parameters.get("stories") or 1,
            "dimensions": dimensions,
            "objects": objects,
            "metadata": {
                "execution_source": "platform_adapter",
                "platform_module": module,
                "platform_intent": intent,
                "platform_topic": topic,
                "original_instruction": instruction,
                "deterministic_hash": self._deterministic_hash(payload),
            },
        }

        return spec_json

    def _infer_design_type(self, module: str, intent: str, topic: str, prompt: str) -> str:
        """Infer design type from platform adapter instruction."""
        combined = f"{module} {intent} {topic} {prompt}".lower()

        if "apartment" in combined or "bhk" in combined:
            return "apartment"
        elif "kitchen" in combined:
            return "kitchen"
        elif "office" in combined:
            return "office"
        elif "villa" in combined or "house" in combined:
            return "house"
        elif "building" in combined:
            return "building"
        else:
            return "building"

    def _extract_dimensions_from_parameters(self, parameters: Dict[str, Any], design_type: str) -> Dict[str, float]:
        """Extract dimensions from platform adapter parameters."""
        defaults = {
            "apartment": {"width": 12.0, "length": 18.0, "height": 3.0},
            "kitchen": {"width": 4.0, "length": 5.0, "height": 3.0},
            "office": {"width": 15.0, "length": 20.0, "height": 3.5},
            "house": {"width": 14.0, "length": 20.0, "height": 6.0},
            "building": {"width": 16.0, "length": 24.0, "height": 8.0},
        }

        dims = dict(defaults.get(design_type, defaults["building"]))

        # Override with parameters if available
        for key in ["width", "length", "height"]:
            value = parameters.get(key)
            if isinstance(value, (int, float)) and value > 0:
                dims[key] = float(value)

        # Check for plot_area and derive dimensions
        plot_area = parameters.get("plot_area")
        if isinstance(plot_area, (int, float)) and plot_area > 0:
            # Assume square plot for simplicity
            side = plot_area**0.5
            dims["width"] = side
            dims["length"] = side

        return dims

    def _build_objects_from_parameters(
        self, parameters: Dict[str, Any], dimensions: Dict[str, float], design_type: str
    ) -> list:
        """Build objects list from parameters."""
        objects = [
            {
                "id": "foundation_main",
                "type": "foundation",
                "material": "concrete",
                "dimensions": {"width": dimensions["width"], "length": dimensions["length"], "height": 0.5},
            },
            {
                "id": "wall_external",
                "type": "wall",
                "subtype": "external",
                "material": "brick",
                "dimensions": {"width": dimensions["width"], "length": 0.2, "height": dimensions["height"]},
            },
            {
                "id": "roof_main",
                "type": "roof",
                "material": "concrete",
                "dimensions": {"width": dimensions["width"], "length": dimensions["length"], "height": 0.2},
            },
            {
                "id": "main_door",
                "type": "door",
                "subtype": "entrance",
                "material": "wood_oak",
                "dimensions": {"width": 1.2, "length": 0.05, "height": 2.1},
            },
            {
                "id": "window_standard",
                "type": "window",
                "material": "glass",
                "count": 4,
                "dimensions": {"width": 1.2, "length": 0.1, "height": 1.5},
            },
        ]

        # Add design-specific objects based on parameters
        if design_type == "apartment" and parameters.get("units"):
            units = int(parameters["units"])
            for i in range(units):
                objects.append(
                    {
                        "id": f"unit_{i+1}",
                        "type": "apartment_unit",
                        "material": "mixed",
                        "dimensions": {
                            "width": dimensions["width"] / 2,
                            "length": dimensions["length"] / 2,
                            "height": dimensions["height"],
                        },
                    }
                )

        return objects
