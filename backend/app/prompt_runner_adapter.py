"""
Prompt Runner Adapter - Multi-Domain Canonical Implementation

Handles all 5 domains from semantic_taxonomy.json:
  architecture  → BHK/villa/office/warehouse   → rooms + layout
  vehicles      → drone/rover/truck/ship/spacecraft → mesh components
  objects       → box/crate/barrel/wall/door/staircase → mesh
  gameplay      → spawn_point/checkpoint/obstacle/collectible/interactable
  environment   → forest/desert/city_block/industrial_zone/ocean_zone

Flow: platform_adapter.process() → domain detection → spec_json assembly
"""

import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.config import settings
from app.design_semantics import extract_semantics

logger = logging.getLogger(__name__)


class PromptRunnerUnavailableError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Domain detection helpers (taxonomy-driven)
# ---------------------------------------------------------------------------

# Keyword → (domain, subtype) — ordered most-specific first
_DOMAIN_PATTERNS: List[tuple] = [
    # --- Architecture (BHK handled by semantic_detector; these are fallbacks) ---
    (r"\b(office|commercial\s+space|coworking)\b", "architecture", "office"),
    (r"\b(warehouse|storage\s+facility|godown)\b", "architecture", "warehouse"),
    (r"\b(villa|bungalow|independent\s+house|duplex|farmhouse)\b", "architecture", "villa"),
    (r"\b(penthouse)\b", "architecture", "penthouse"),
    (r"\b(apartment|flat|house|home|residence|bhk)\b", "architecture", "house"),
    # --- Vehicles ---
    (r"\b(drone|quadcopter|uav|multirotor)\b", "vehicles", "drone"),
    (r"\b(rover|mars\s+rover|lunar\s+rover)\b", "vehicles", "rover"),
    (r"\b(truck|lorry|semi[-\s]truck|cargo\s+vehicle)\b", "vehicles", "truck"),
    (r"\b(ship|vessel|boat|yacht|tanker|cargo\s+ship)\b", "vehicles", "ship"),
    (r"\b(spacecraft|rocket|satellite|space\s+station|starship)\b", "vehicles", "spacecraft"),
    # --- Objects ---
    (r"\b(box|crate|barrel|container)\b", "objects", "box"),
    (r"\b(barrel|drum)\b", "objects", "barrel"),
    (r"\b(crate)\b", "objects", "crate"),
    (r"\b(wall|partition)\b", "objects", "wall"),
    (r"\b(door|gate|entrance)\b", "objects", "door"),
    (r"\b(staircase|stair|stairway)\b", "objects", "staircase"),
    # --- Gameplay ---
    (r"\b(spawn\s+point|spawn\s+zone|player\s+spawn)\b", "gameplay", "spawn_point"),
    (r"\b(checkpoint|finish\s+line|waypoint)\b", "gameplay", "checkpoint"),
    (r"\b(obstacle|barrier|hurdle)\b", "gameplay", "obstacle"),
    (r"\b(collectible|pickup|powerup|coin|gem)\b", "gameplay", "collectible"),
    (r"\b(interactable|interactive\s+object|trigger)\b", "gameplay", "interactable"),
    # --- Environment ---
    (r"\b(forest|jungle|woodland|woods)\b", "environment", "forest"),
    (r"\b(desert|dune|sahara|arid)\b", "environment", "desert"),
    (r"\b(city\s+block|urban\s+area|street\s+scene|city\s+street)\b", "environment", "city_block"),
    (r"\b(industrial\s+zone|factory\s+area|industrial\s+complex)\b", "environment", "industrial_zone"),
    (r"\b(ocean|sea\s+zone|underwater|marine\s+environment)\b", "environment", "ocean_zone"),
]

# BHK subtype → architecture domain name
_BHK_TO_SUBTYPE = {
    "1BHK": "1BHK",
    "2BHK": "2BHK",
    "3BHK": "3BHK",
    "4BHK": "4BHK",
    "5BHK": "5BHK",
    "VILLA": "villa",
    "PENTHOUSE": "penthouse",
}

# Default rooms/dimensions for non-architecture domains (geometry_generator_real compatibility)
_DOMAIN_SPECS: Dict[str, Dict] = {
    "vehicles": {
        "drone": {"rooms": ["frame", "rotor_assembly", "landing_gear"], "w": 1.0, "l": 1.0, "h": 0.3},
        "rover": {"rooms": ["chassis", "wheel_assembly", "sensor_array"], "w": 1.5, "l": 2.0, "h": 0.8},
        "truck": {"rooms": ["cab", "chassis", "cargo_bed"], "w": 2.5, "l": 7.0, "h": 3.0},
        "ship": {"rooms": ["hull", "deck", "bridge"], "w": 15.0, "l": 60.0, "h": 8.0},
        "spacecraft": {"rooms": ["fuselage", "engine_bay", "docking_port"], "w": 5.0, "l": 20.0, "h": 5.0},
    },
    "objects": {
        "box": {"rooms": ["body"], "w": 0.6, "l": 0.6, "h": 0.6},
        "crate": {"rooms": ["body"], "w": 1.0, "l": 1.0, "h": 1.0},
        "barrel": {"rooms": ["body"], "w": 0.6, "l": 0.6, "h": 1.0},
        "wall": {"rooms": ["face"], "w": 3.0, "l": 0.2, "h": 2.7},
        "door": {"rooms": ["frame", "panel"], "w": 0.9, "l": 0.1, "h": 2.1},
        "staircase": {"rooms": ["steps", "landing"], "w": 1.2, "l": 3.0, "h": 3.0},
    },
    "gameplay": {
        "spawn_point": {"rooms": ["marker_zone"], "w": 2.0, "l": 2.0, "h": 0.1},
        "checkpoint": {"rooms": ["trigger_zone"], "w": 3.0, "l": 1.0, "h": 3.0},
        "obstacle": {"rooms": ["body"], "w": 1.0, "l": 1.0, "h": 1.0},
        "collectible": {"rooms": ["body"], "w": 0.5, "l": 0.5, "h": 0.5},
        "interactable": {"rooms": ["body", "trigger_zone"], "w": 1.0, "l": 1.0, "h": 1.5},
    },
    "environment": {
        "forest": {"rooms": ["canopy_zone", "undergrowth_zone", "path"], "w": 50.0, "l": 50.0, "h": 20.0},
        "desert": {"rooms": ["dune_zone", "rock_zone", "oasis"], "w": 100.0, "l": 100.0, "h": 15.0},
        "city_block": {"rooms": ["road", "sidewalk", "building_shell"], "w": 40.0, "l": 60.0, "h": 10.0},
        "industrial_zone": {
            "rooms": ["factory_shell", "storage_area", "loading_dock"],
            "w": 60.0,
            "l": 80.0,
            "h": 12.0,
        },
        "ocean_zone": {"rooms": ["surface_plane", "ocean_floor", "reef_zone"], "w": 100.0, "l": 100.0, "h": 20.0},
    },
}


# Canonical domain names accepted from context payload
_VALID_DOMAINS = {"architecture", "vehicles", "objects", "gameplay", "environment"}

# Maps platform_adapter module names → taxonomy domain
_MODULE_TO_DOMAIN = {
    "architecture": "architecture",
    "vehicles": "vehicles",
    "vehicle": "vehicles",
    "objects": "objects",
    "object": "objects",
    "gameplay": "gameplay",
    "game": "gameplay",
    "environment": "environment",
    "terrain": "environment",
    "biome": "environment",
}


def _detect_domain_and_subtype(prompt: str, instruction: Dict, context: Dict = None) -> tuple:
    """
    Returns (domain, subtype, sem) by checking in priority order:
    1. Explicit domain/subtype in context payload (highest priority)
    2. BHK detection via extract_semantics
    3. Taxonomy _DOMAIN_PATTERNS on prompt
    4. platform_adapter module/intent mapping
    5. Default: architecture/house
    """
    sem = extract_semantics(prompt)
    ctx = context or {}

    # 1. Explicit domain + subtype in request context
    ctx_domain = str(ctx.get("domain", "")).strip().lower()
    ctx_subtype = str(ctx.get("subtype", "")).strip()
    if ctx_domain in _VALID_DOMAINS and ctx_subtype:
        return ctx_domain, ctx_subtype, sem
    if ctx_domain in _VALID_DOMAINS:
        # domain given but no subtype — fall through to detect subtype from prompt
        pass

    # 2. BHK detected — architecture domain
    if sem.bhk_key:
        subtype = _BHK_TO_SUBTYPE.get(sem.bhk_key, "house")
        return "architecture", subtype, sem

    # 3. Taxonomy pattern matching on prompt
    prompt_lower = prompt.lower()
    for pattern, domain, subtype in _DOMAIN_PATTERNS:
        if re.search(pattern, prompt_lower, re.IGNORECASE):
            return domain, subtype, sem

    # 4. platform_adapter module → domain mapping
    module = instruction.get("module", "").lower()
    intent = instruction.get("intent", "").lower()
    mapped_domain = _MODULE_TO_DOMAIN.get(module)
    if mapped_domain:
        # detect subtype from prompt within that domain
        for pattern, domain, subtype in _DOMAIN_PATTERNS:
            if domain == mapped_domain and re.search(pattern, prompt_lower, re.IGNORECASE):
                return domain, subtype, sem
        # module matched but no subtype pattern — use domain default subtype
        _domain_defaults = {
            "vehicles": "drone",
            "objects": "box",
            "gameplay": "obstacle",
            "environment": "forest",
        }
        return mapped_domain, _domain_defaults.get(mapped_domain, "house"), sem

    # 5. Default
    return "architecture", "house", sem


# ---------------------------------------------------------------------------
# Spec builders per domain
# ---------------------------------------------------------------------------


def _build_architecture_spec(subtype: str, sem, dimensions: Dict, style: str, stories: int, city: str) -> Dict:
    """Build spec_json for architecture domain."""
    from app.design_semantics.semantic_detector import _load_bhk

    bhk_data = _load_bhk()

    # Map subtype → BHK key
    bhk_key_map = {
        "1BHK": "1BHK",
        "2BHK": "2BHK",
        "3BHK": "3BHK",
        "4BHK": "4BHK",
        "5BHK": "5BHK",
        "villa": "VILLA",
        "penthouse": "PENTHOUSE",
    }
    # For generic house/apartment/office/warehouse — pick best match or default 2BHK
    generic_fallback_map = {
        "house": "2BHK",
        "apartment": "2BHK",
        "flat": "2BHK",
        "office": "2BHK",
        "warehouse": "2BHK",
    }

    bhk_key = bhk_key_map.get(subtype) or generic_fallback_map.get(subtype, "2BHK")
    bhk_def = sem.bhk_definition if sem.bhk_definition else bhk_data.get(bhk_key, bhk_data["2BHK"])

    rooms = list(bhk_def.get("rooms", []))
    room_counts = bhk_def.get("room_counts", {})
    adjacency = bhk_def.get("adjacency", {})

    # Scale room_dimensions to actual floor area
    bhk_dims = bhk_def.get("dimensions", {})
    canonical_area = bhk_dims.get("width_m", 10.0) * bhk_dims.get("length_m", 10.0)
    actual_area = dimensions["width"] * dimensions["length"]
    scale = (actual_area / canonical_area) ** 0.5 if canonical_area > 0 else 1.0
    room_dimensions = {
        room: {
            "width_m": round(v["width_m"] * scale, 2),
            "length_m": round(v["length_m"] * scale, 2),
        }
        for room, v in bhk_def.get("room_dimensions", {}).items()
    }

    style_hints = _build_style_hints(sem)
    objects = _build_arch_objects(dimensions, style, sem)
    layout_rules = _build_layout_rules(sem)

    spec: Dict = {
        "type": subtype,
        "design_type": subtype,
        "domain": "architecture",
        "rooms": rooms,
        "room_counts": room_counts,
        "room_dimensions": room_dimensions,
        "adjacency": adjacency,
        "layout_rules": layout_rules,
        "style": style,
        "style_hints": style_hints,
        "objects": objects,
        "city": city,
        "dimensions": dimensions,
        "units": "meters",
        "stories": stories,
        "typical_budget_inr": bhk_def.get("typical_budget_inr", {}),
    }
    if sem.budget_inr:
        spec["budget_inr"] = sem.budget_inr
    if sem.area_sqft:
        spec["area_sqft"] = sem.area_sqft
    return spec


def _build_non_architecture_spec(domain: str, subtype: str, dimensions: Dict, prompt: str) -> Dict:
    """Build spec_json for vehicles, objects, gameplay, environment domains."""
    domain_data = _DOMAIN_SPECS.get(domain, {})
    subtype_data = domain_data.get(subtype, {})

    if not subtype_data:
        # Unknown subtype — create a minimal safe spec
        subtype_data = {
            "rooms": ["main_body"],
            "w": dimensions["width"],
            "l": dimensions["length"],
            "h": dimensions["height"],
        }

    rooms = list(subtype_data["rooms"])

    # Override dimensions if prompt has explicit values, else use domain defaults
    if dimensions["width"] == 10.0 and dimensions["length"] == 10.0:
        dimensions = {
            "width": subtype_data["w"],
            "length": subtype_data["l"],
            "height": subtype_data["h"],
        }

    # room_dimensions: every room gets equal share of floor area
    n = max(len(rooms), 1)
    room_w = round(dimensions["width"] / n, 2)
    room_l = round(dimensions["length"], 2)
    room_dimensions = {room: {"width_m": room_w, "length_m": room_l} for room in rooms}

    return {
        "type": subtype,
        "design_type": subtype,
        "domain": domain,
        "rooms": rooms,
        "room_counts": {room: 1 for room in rooms},
        "room_dimensions": room_dimensions,
        "adjacency": {},
        "layout_rules": [],
        "style": "default",
        "style_hints": {},
        "objects": [
            {
                "id": "main_body",
                "type": subtype,
                "material": "default",
                "dimensions": {
                    "width": dimensions["width"],
                    "length": dimensions["length"],
                    "height": dimensions["height"],
                },
            }
        ],
        "city": "global",
        "dimensions": dimensions,
        "units": "meters",
        "stories": 1,
    }


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _build_arch_objects(dimensions: Dict, style: str, sem) -> list:
    w, l, h = dimensions.get("width", 10.0), dimensions.get("length", 10.0), dimensions.get("height", 3.0)
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
        {"id": "floor", "type": "floor", "material": floor_mat, "dimensions": {"width": w, "length": l}},
    ]


def _build_layout_rules(sem) -> list:
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
        rules.append({"rule_id": rule["rule_id"], "description": rule["description"], "priority": rule["priority"]})
    return rules


def _build_style_hints(sem) -> Dict:
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


def _extract_dimensions(parameters: Dict, prompt: str, constraints: Dict) -> Dict:
    dims = {}
    for key in ["width", "length", "height"]:
        v = parameters.get(key) or constraints.get(key)
        if isinstance(v, (int, float)) and v > 0:
            dims[key] = float(v)

    if "width" not in dims:
        max_area = constraints.get("max_area") or constraints.get("area")
        if isinstance(max_area, (int, float)) and max_area > 0:
            area_sqm = max_area / 10.764 if max_area > 500 else float(max_area)
            side = area_sqm**0.5
            dims["width"] = round(side, 2)
            dims["length"] = round(side, 2)

    if "width" not in dims:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:x|by|×)\s*(\d+(?:\.\d+)?)", prompt.lower())
        if m:
            dims["width"] = float(m.group(1))
            dims["length"] = float(m.group(2))

    dims.setdefault("width", 10.0)
    dims.setdefault("length", 10.0)
    dims.setdefault("height", 3.0)
    return dims


def _extract_stories(parameters: Dict, prompt: str, sem) -> int:
    v = parameters.get("stories") or parameters.get("floors")
    if isinstance(v, int) and v > 0:
        return v
    if sem.stories:
        return sem.stories
    m = re.search(r"(\d+)\s*(?:stor(?:ey|y|ies)|floor)", prompt.lower())
    if m:
        return int(m.group(1))
    return 1


def _deterministic_hash(payload: Dict) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Main adapter
# ---------------------------------------------------------------------------


class PromptRunnerAdapterBridge:
    """
    Multi-domain canonical adapter.
    Handles architecture, vehicles, objects, gameplay, environment.
    """

    def __init__(self):
        self.platform_adapter = None
        self._initialize_platform_adapter()

    def _initialize_platform_adapter(self):
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
        prompt = str(payload.get("prompt", "")).strip()
        city = payload.get("city") or "Mumbai"
        style = payload.get("style") or "modern"
        constraints = payload.get("constraints") if isinstance(payload.get("constraints"), dict) else {}
        context = payload.get("context") if isinstance(payload.get("context"), dict) else {}

        logger.info("🎯 Day 1 Flow: Calling platform_adapter.run_from_platform()")

        # Step 1: Call platform_adapter
        try:
            platform_result = self.platform_adapter.process(prompt)
            if platform_result.get("status") != "success":
                raise PromptRunnerUnavailableError(f"Platform adapter failed: {platform_result.get('error')}")
            instruction = platform_result.get("instruction", {})
            logger.info(f"✅ Platform adapter: module={instruction.get('module')}, intent={instruction.get('intent')}")
        except Exception as exc:
            logger.error(f"❌ Platform adapter failed: {exc}")
            raise PromptRunnerUnavailableError(f"Platform adapter execution failed: {exc}")

        # Step 2: Detect domain + subtype
        data = instruction.get("data", {})
        parameters = data.get("parameters", {})
        domain, subtype, sem = _detect_domain_and_subtype(prompt, instruction, context)
        logger.info(
            f"Semantics: domain={domain} subtype={subtype} bhk={sem.bhk_key}({sem.bhk_confidence:.2f}) style={sem.style_key}({sem.style_confidence:.2f}) city={sem.city} budget={sem.budget_inr} area_sqft={sem.area_sqft}"
        )

        # Step 3: Resolve dimensions
        dimensions = _extract_dimensions(parameters, prompt, constraints)

        # BHK canonical dimensions override (when no explicit dims in prompt)
        has_explicit = bool(
            re.search(r"\d+\s*(?:x|by)\s*\d+", prompt, re.IGNORECASE)
            or re.search(r"\d+\s*(?:sq\.?\s*ft|sqft|sq\.?\s*m|sqm)", prompt, re.IGNORECASE)
        )
        if sem.bhk_definition and not has_explicit and not (constraints.get("max_area") or constraints.get("width")):
            bd = sem.bhk_definition.get("dimensions", {})
            dimensions["width"] = bd.get("width_m", dimensions["width"])
            dimensions["length"] = bd.get("length_m", dimensions["length"])
            dimensions["height"] = bd.get("height_m", dimensions["height"])

        if sem.area_sqm and not has_explicit:
            side = sem.area_sqm**0.5
            dimensions["width"] = round(side, 2)
            dimensions["length"] = round(side, 2)

        # Step 4: Resolve other scalars
        resolved_city = sem.city or city
        resolved_style = sem.style_key or style
        stories = _extract_stories(parameters, prompt, sem)

        logger.info(f"✅ Day 1 complete: domain={domain} design_type={subtype}")

        # Step 5: Build domain-specific spec_json
        if domain == "architecture":
            spec_json = _build_architecture_spec(subtype, sem, dimensions, resolved_style, stories, resolved_city)
        else:
            spec_json = _build_non_architecture_spec(domain, subtype, dimensions, prompt)

        # Attach metadata
        digest = _deterministic_hash(payload)
        spec_json.setdefault("metadata", {}).update(
            {
                "execution_authority": "platform_adapter",
                "prompt_runner_module": instruction.get("module"),
                "prompt_runner_intent": instruction.get("intent"),
                "deterministic_hash": digest,
            }
        )

        return {
            "spec_json": spec_json,
            "provider": "platform_adapter",
            "execution_mode": "canonical",
            "deterministic_hash": digest,
        }
