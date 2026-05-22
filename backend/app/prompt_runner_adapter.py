"""
Prompt Runner Adapter - Canonical Implementation

Uses platform_adapter.py as the EXECUTION AUTHORITY:
  1. Call platform_adapter.process() for domain/intent/entity extraction
  2. Convert PromptInstruction → spec_json (deterministic, no direct LLM calls)
  3. Return deterministic spec_json to Core

Only allowed path: platform_adapter → Prompt Runner
"""

import hashlib
import json
import logging
import re
from typing import Any, Dict

from app.config import settings
from app.design_semantics import extract_semantics

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
        Convert PromptInstruction → spec_json with full semantic injection.

        Pipeline:
          1. extract_semantics(prompt)  → BHK definition + style profile + layout rules
          2. Resolve dimensions         → from semantics > parameters > prompt > defaults
          3. Build rooms list           → from BHK definition room_counts
          4. Build objects              → structural objects sized to dimensions
          5. Inject layout_rules        → adjacency + orientation + zoning rules
          6. Inject style_hints         → roof, windows, materials, colors from style profile
          7. Return fully enriched spec_json
        """
        data = instruction.get("data", {})
        parameters = data.get("parameters", {})
        module = instruction.get("module", "general_processor")
        intent = instruction.get("intent", "design_creation")

        # ── Step 1: Semantic extraction ──────────────────────────────────────
        sem = extract_semantics(prompt)
        logger.info(
            "Semantics: bhk=%s(%.2f) style=%s(%.2f) city=%s budget=%s area_sqft=%s",
            sem.bhk_key,
            sem.bhk_confidence,
            sem.style_key,
            sem.style_confidence,
            sem.city,
            sem.budget_inr,
            sem.area_sqft,
        )

        # ── Step 2: Resolve final values (semantics > payload > defaults) ────
        resolved_city = sem.city or city or "Mumbai"
        resolved_style = sem.style_key or style or "modern"
        constraints_dict = constraints if isinstance(constraints, dict) else {}
        resolved_stories = (
            int(constraints_dict.get("max_stories") or constraints_dict.get("stories") or 0)
            or sem.stories
            or self._extract_stories(parameters, prompt)
            or (sem.bhk_definition.get("stories", 1) if sem.bhk_definition else 1)
        )

        # ── Step 3: Resolve dimensions ───────────────────────────────────────
        has_area_constraint = bool(
            constraints_dict.get("max_area")
            or constraints_dict.get("area")
            or constraints_dict.get("width")
            or constraints_dict.get("length")
        )
        dimensions = await self._extract_dimensions(parameters, prompt, constraints_dict, context)

        # Override with BHK canonical dimensions ONLY when no area constraint and no explicit dims in prompt
        if sem.bhk_definition and not self._has_explicit_dimensions(prompt) and not has_area_constraint:
            bhk_dims = sem.bhk_definition.get("dimensions", {})
            dimensions["width"] = bhk_dims.get("width_m", dimensions["width"])
            dimensions["length"] = bhk_dims.get("length_m", dimensions["length"])
            dimensions["height"] = bhk_dims.get("height_m", dimensions["height"])

        # Override with detected area from prompt (e.g. "1500 sqft") — takes priority over BHK defaults
        if sem.area_sqm and not self._has_explicit_dimensions(prompt) and not has_area_constraint:
            side = sem.area_sqm**0.5
            dimensions["width"] = round(side, 2)
            dimensions["length"] = round(side, 2)

        # ── Step 4: Build rooms list from BHK definition ─────────────────────
        rooms = self._build_rooms(sem)

        # ── Step 5: Build structural objects ─────────────────────────────────
        design_type = sem.bhk_key or self._infer_design_type(module, intent, prompt, parameters)
        objects = self._build_objects(dimensions, resolved_style, sem)

        # ── Step 6: Build layout_rules subset (adjacency + orientation) ──────
        layout_rules = self._build_layout_rules(sem)

        # ── Step 7: Build style_hints from style profile ──────────────────────
        style_hints = self._build_style_hints(sem)

        # ── Assemble final spec_json ──────────────────────────────────────────
        spec_json: Dict[str, Any] = {
            "type": design_type,
            "design_type": design_type,
            "rooms": rooms,
            "layout_rules": layout_rules,
            "style": resolved_style,
            "style_hints": style_hints,
            "objects": objects,
            "city": resolved_city,
            "dimensions": dimensions,
            "units": "meters",
            "stories": resolved_stories,
        }

        # Carry semantic scalars into spec
        if sem.budget_inr:
            spec_json["budget_inr"] = sem.budget_inr
        if sem.area_sqft:
            spec_json["area_sqft"] = sem.area_sqft
        if sem.bhk_definition:
            spec_json["room_counts"] = sem.bhk_definition.get("room_counts", {})
            spec_json["adjacency"] = sem.bhk_definition.get("adjacency", {})
            spec_json["typical_budget_inr"] = sem.bhk_definition.get("typical_budget_inr", {})

            # Scale room_dimensions proportionally to actual floor area
            bhk_dims = sem.bhk_definition.get("dimensions", {})
            canonical_area = bhk_dims.get("width_m", 10.0) * bhk_dims.get("length_m", 10.0)
            actual_area = dimensions["width"] * dimensions["length"]
            scale = (actual_area / canonical_area) ** 0.5 if canonical_area > 0 else 1.0
            raw_room_dims = sem.bhk_definition.get("room_dimensions", {})
            spec_json["room_dimensions"] = {
                room: {
                    "width_m": round(v["width_m"] * scale, 2),
                    "length_m": round(v["length_m"] * scale, 2),
                }
                for room, v in raw_room_dims.items()
            }

        return spec_json

    # ------------------------------------------------------------------
    # Semantic injection helpers
    # ------------------------------------------------------------------

    def _has_explicit_dimensions(self, prompt: str) -> bool:
        """True if prompt contains explicit WxL or area dimensions."""
        return bool(
            re.search(r"\d+\s*(?:x|by)\s*\d+", prompt, re.IGNORECASE)
            or re.search(r"\d+\s*(?:sq\.?\s*ft|sqft|sq\.?\s*m|sqm)", prompt, re.IGNORECASE)
        )

    def _build_rooms(self, sem) -> list:
        """Return the canonical room list from bhk_definitions.json[bhk_key]["rooms"]."""
        if not sem.bhk_definition:
            return []
        return list(sem.bhk_definition.get("rooms", []))

    def _build_objects(self, dimensions: Dict, style: str, sem) -> list:
        """Build structural objects sized to resolved dimensions + style materials."""
        w = dimensions.get("width", 10.0)
        l = dimensions.get("length", 10.0)
        h = dimensions.get("height", 3.0)

        # Pick materials from style profile
        ext_wall_mat = "brick"
        floor_mat = "tile_ceramic"
        roof_type = "flat"
        if sem.style_profile:
            mats = sem.style_profile.get("materials", {})
            ext_walls = mats.get("exterior_wall", [])
            floors = mats.get("floor", [])
            ext_wall_mat = ext_walls[0] if ext_walls else "brick"
            floor_mat = floors[0] if floors else "tile_ceramic"
            roof_type = sem.style_profile.get("elevation", {}).get("roof", "flat")

        return [
            {
                "id": "foundation",
                "type": "foundation",
                "material": "concrete",
                "dimensions": {"width": w, "length": l, "height": 0.5},
            },
            {
                "id": "exterior_walls",
                "type": "wall",
                "subtype": "exterior",
                "material": ext_wall_mat,
                "dimensions": {"width": w, "length": l, "height": h},
            },
            {
                "id": "roof",
                "type": "roof",
                "subtype": roof_type,
                "material": "rcc_flat_slab" if "flat" in roof_type else "mangalore_tile",
                "dimensions": {"width": w + 0.6, "length": l + 0.6, "height": 0.2},
            },
            {
                "id": "floor",
                "type": "floor",
                "material": floor_mat,
                "dimensions": {"width": w, "length": l},
            },
        ]

    def _build_layout_rules(self, sem) -> list:
        """Extract adjacency + orientation rules relevant to detected BHK rooms."""
        if not sem.layout_rules:
            return []
        rules = []
        for rule in sem.layout_rules.get("adjacency_rules", []):
            rules.append(
                {
                    "rule_id": rule["rule_id"],
                    "description": rule["description"],
                    "relation": rule["relation"],
                    "priority": rule["priority"],
                }
            )
        for rule in sem.layout_rules.get("orientation_rules", []):
            rules.append(
                {
                    "rule_id": rule["rule_id"],
                    "description": rule["description"],
                    "priority": rule["priority"],
                }
            )
        return rules

    def _build_style_hints(self, sem) -> Dict[str, Any]:
        """Extract elevation + material + color hints from style profile."""
        if not sem.style_profile:
            return {}
        p = sem.style_profile
        return {
            "roof": p.get("elevation", {}).get("roof", "flat"),
            "windows": p.get("windows", {}).get("type", "standard"),
            "material": p.get("materials", {}).get("primary", ""),
            "facade": p.get("elevation", {}).get("facade", ""),
            "colors": p.get("colors", {}),
            "lighting": p.get("lighting", ""),
            "cost_multiplier": p.get("cost_multiplier", 1.0),
        }

    def _deterministic_hash(self, payload: Dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, default=str).encode("utf-8", errors="ignore")
        return hashlib.sha256(canonical).hexdigest()[:16]

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
        """Extract dimensions from parameters, constraints (max_area), or prompt"""
        dimensions = {}

        # Try explicit width/length/height from parameters first
        for key in ["width", "length", "height", "plot_area"]:
            val = parameters.get(key)
            if isinstance(val, (int, float)) and val > 0:
                dimensions[key] = float(val)

        # Try explicit width/length/height from constraints
        if not dimensions:
            for key in ["width", "length", "height"]:
                val = constraints.get(key)
                if isinstance(val, (int, float)) and val > 0:
                    dimensions[key] = float(val)

        # Handle max_area from constraints — convert to width x length
        if "width" not in dimensions and "length" not in dimensions:
            max_area = constraints.get("max_area") or constraints.get("area")
            if isinstance(max_area, (int, float)) and max_area > 0:
                # Treat values > 500 as sqft, <= 500 as sqm
                area_sqm = max_area / 10.764 if max_area > 500 else float(max_area)
                side = area_sqm**0.5
                dimensions["width"] = round(side, 2)
                dimensions["length"] = round(side, 2)

        # Parse WxL from prompt using regex
        if "width" not in dimensions:
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
