"""
SemanticResolver
================
Maps a Prompt Runner response (module + topic + intent + tasks)
to a resolved semantic context:

    {
        "domain":          str,
        "entity":          str,
        "generation_mode": str,
        "geometry_family": str
    }

Resolution pipeline:
    1. Normalise module  → domain key  (vehicles → vehicle, objects → object)
    2. Tokenise topic    → candidate tokens
    3. Score each token against every entity in semantic_templates.json
       using exact match → alias match → substring match
    4. Confirm entity belongs to resolved domain (domain guard)
    5. Pull generation_mode + geometry_family from semantic_templates.json
    6. Raise SemanticResolutionError if nothing resolves
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────

_SEMANTICS_DIR = Path(__file__).parent
_TAXONOMY_PATH = _SEMANTICS_DIR / "semantic_taxonomy.json"
_TEMPLATES_PATH = _SEMANTICS_DIR / "semantic_templates.json"

# ── Exceptions ────────────────────────────────────────────────────────────────


class SemanticResolutionError(Exception):
    """Raised when neither domain nor entity can be resolved."""


# ── Module → domain normalisation map ─────────────────────────────────────────
#
# Prompt Runner uses its own module names which may differ from taxonomy keys.

_MODULE_TO_DOMAIN: Dict[str, str] = {
    # direct matches
    "architecture": "architecture",
    "vehicle": "vehicle",
    "vehicles": "vehicle",
    "object": "object",
    "objects": "object",
    "gameplay": "gameplay",
    "environment": "environment",
    # common aliases Prompt Runner may emit
    "arch": "architecture",
    "building": "architecture",
    "prop": "object",
    "props": "object",
    "game": "gameplay",
    "terrain": "environment",
    "biome": "environment",
    "scene": "environment",
}

# ── Entity alias map ──────────────────────────────────────────────────────────
#
# Maps topic tokens (or substrings) → canonical entity keys in templates.

_ENTITY_ALIASES: Dict[str, str] = {
    # architecture
    "1bhk": "1bhk",
    "1 bhk": "1bhk",
    "2bhk": "2bhk",
    "2 bhk": "2bhk",
    "3bhk": "2bhk",  # closest match
    "apartment": "2bhk",
    "flat": "2bhk",
    "villa": "villa",
    "bungalow": "villa",
    "house": "villa",
    "office": "office",
    "commercial": "office",
    "workspace": "office",
    "warehouse": "warehouse",
    "storage": "warehouse",
    "godown": "warehouse",
    # objects
    "box": "box",
    "crate": "crate",
    "barrel": "barrel",
    "wall": "wall",
    "door": "door",
    "staircase": "staircase",
    "stairs": "staircase",
    # vehicles
    "drone": "drone",
    "uav": "drone",
    "quadcopter": "drone",
    "combat_drone": "drone",
    "combat drone": "drone",
    "spy drone": "drone",
    "rover": "rover",
    "buggy": "rover",
    "truck": "truck",
    "lorry": "truck",
    "ship": "ship",
    "boat": "ship",
    "vessel": "ship",
    "spacecraft": "spacecraft",
    "rocket": "spacecraft",
    "satellite": "spacecraft",
    "capsule": "spacecraft",
    # gameplay
    "spawn": "spawn_point",
    "spawn_point": "spawn_point",
    "checkpoint": "checkpoint",
    "waypoint": "checkpoint",
    "obstacle": "obstacle",
    "barrier": "obstacle",
    "collectible": "collectible",
    "pickup": "collectible",
    "coin": "collectible",
    "interactable": "interactable",
    "switch": "interactable",
    "lever": "interactable",
    # environment
    "forest": "forest",
    "jungle": "forest",
    "woods": "forest",
    "desert": "desert",
    "dune": "desert",
    "city": "city_block",
    "city_block": "city_block",
    "urban": "city_block",
    "street": "city_block",
    "industrial": "industrial_zone",
    "industrial_zone": "industrial_zone",
    "factory": "industrial_zone",
    "ocean": "ocean_zone",
    "ocean_zone": "ocean_zone",
    "sea": "ocean_zone",
    "underwater": "ocean_zone",
}


# ── Loader ────────────────────────────────────────────────────────────────────


def _load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── SemanticResolver ──────────────────────────────────────────────────────────


class SemanticResolver:
    """
    Resolves a Prompt Runner response to a semantic context dict.

    Usage::

        resolver = SemanticResolver()
        ctx = resolver.resolve({"module": "vehicle", "topic": "combat_drone", ...})
        # {"domain": "vehicle", "entity": "drone",
        #  "generation_mode": "mesh", "geometry_family": "rotorcraft"}
    """

    def __init__(self) -> None:
        taxonomy = _load_json(_TAXONOMY_PATH)
        templates = _load_json(_TEMPLATES_PATH)
        self._templates: Dict[str, Dict[str, Any]] = templates["templates"]
        # Build domain → set of entity keys from taxonomy
        self._domain_entities: Dict[str, set] = {}
        for domain_key, domain_data in taxonomy["domains"].items():
            # taxonomy uses "vehicles"/"objects" — normalise to singular
            norm = _MODULE_TO_DOMAIN.get(domain_key, domain_key)
            entities = set(k.lower() for k in domain_data.get("subtypes", {}).keys())
            self._domain_entities.setdefault(norm, set()).update(entities)

    # ── Public ────────────────────────────────────────────────────────────────

    def resolve(self, prompt_runner_response: Dict[str, Any]) -> Dict[str, str]:
        """
        Resolve a Prompt Runner response dict to a semantic context.

        Args:
            prompt_runner_response: dict with at least ``module`` and ``topic``.
                                    ``intent`` and ``tasks`` are optional hints.

        Returns:
            dict with domain / entity / generation_mode / geometry_family

        Raises:
            SemanticResolutionError: if resolution fails completely.
        """
        module = str(prompt_runner_response.get("module", "")).strip().lower()
        topic = str(prompt_runner_response.get("topic", "")).strip().lower()
        intent = str(prompt_runner_response.get("intent", "")).strip().lower()

        domain = self._resolve_domain(module, topic, intent)
        entity = self._resolve_entity(topic, domain)

        template = self._templates.get(entity)
        if template is None:
            raise SemanticResolutionError(f"Entity '{entity}' has no template entry in semantic_templates.json")

        result = {
            "domain": domain,
            "entity": entity,
            "generation_mode": template["generation_mode"],
            "geometry_family": template["geometry_family"],
        }
        logger.info("SemanticResolver: module=%r topic=%r → %s", module, topic, result)
        return result

    # ── Domain resolution ─────────────────────────────────────────────────────

    def _resolve_domain(self, module: str, topic: str, intent: str) -> str:
        # 1. Direct module lookup
        domain = _MODULE_TO_DOMAIN.get(module)
        if domain:
            return domain

        # 2. Partial module match (skip if module is empty)
        if module:
            for key, val in _MODULE_TO_DOMAIN.items():
                if key in module or module in key:
                    return val

        # 3. Scan topic tokens against alias map → infer domain from entity
        #    Only succeed if topic is non-empty (avoid false positives on empty input)
        if topic:
            entity = self._entity_from_tokens(self._tokenise(topic), domain_hint=None)
            if entity and entity in self._templates:
                return self._templates[entity]["domain"]

        # 4. Scan intent
        if intent:
            entity = self._entity_from_tokens(self._tokenise(intent), domain_hint=None)
            if entity and entity in self._templates:
                return self._templates[entity]["domain"]

        raise SemanticResolutionError(f"Cannot resolve domain from module={module!r}, topic={topic!r}")

    # ── Entity resolution ─────────────────────────────────────────────────────

    def _resolve_entity(self, topic: str, domain: str) -> str:
        tokens = self._tokenise(topic)

        # Pass 1 — with domain guard
        entity = self._entity_from_tokens(tokens, domain_hint=domain)
        if entity:
            return entity

        # Pass 2 — relax domain guard (topic may describe entity from same domain)
        entity = self._entity_from_tokens(tokens, domain_hint=None)
        if entity and self._templates.get(entity, {}).get("domain") == domain:
            return entity

        # Pass 3 — fallback to domain default entity
        default = self._domain_default(domain)
        if default:
            logger.warning(
                "SemanticResolver: no entity match for topic=%r in domain=%r, " "falling back to default=%r",
                topic,
                domain,
                default,
            )
            return default

        raise SemanticResolutionError(f"Cannot resolve entity from topic={topic!r} in domain={domain!r}")

    def _entity_from_tokens(self, tokens: list, domain_hint: Optional[str]) -> Optional[str]:
        """Score tokens against alias map and template keys, return best match."""
        candidates = []

        for token in tokens:
            # Exact alias match
            if token in _ENTITY_ALIASES:
                entity = _ENTITY_ALIASES[token]
                if self._domain_ok(entity, domain_hint):
                    candidates.append((3, entity))
                    continue

            # Exact template key match
            if token in self._templates:
                if self._domain_ok(token, domain_hint):
                    candidates.append((3, token))
                    continue

            # Substring alias match
            for alias, entity in _ENTITY_ALIASES.items():
                if alias in token or token in alias:
                    if self._domain_ok(entity, domain_hint):
                        candidates.append((2, entity))
                        break

            # Substring template key match
            for key in self._templates:
                if key in token or token in key:
                    if self._domain_ok(key, domain_hint):
                        candidates.append((1, key))
                        break

        if not candidates:
            return None
        # Return highest-scored candidate (stable: first highest wins)
        candidates.sort(key=lambda x: -x[0])
        return candidates[0][1]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _domain_ok(self, entity: str, domain_hint: Optional[str]) -> bool:
        if domain_hint is None:
            return True
        template = self._templates.get(entity, {})
        return template.get("domain") == domain_hint

    def _domain_default(self, domain: str) -> Optional[str]:
        """Return the first entity for a domain as a last-resort fallback."""
        for key, tpl in self._templates.items():
            if tpl.get("domain") == domain:
                return key
        return None

    @staticmethod
    def _tokenise(text: str) -> list:
        """
        Split topic string into meaningful tokens.
        '2BHK_apartment' → ['2bhk', 'apartment', '2bhk apartment']
        'combat_drone'   → ['combat', 'drone', 'combat drone']
        """
        text = text.lower()
        # Split on spaces, underscores, hyphens, dots
        parts = re.split(r"[\s_\-\.]+", text)
        parts = [p for p in parts if p]
        tokens = list(parts)
        # Also add the full joined string and bigrams
        tokens.append(text.replace("_", " ").replace("-", " "))
        for i in range(len(parts) - 1):
            tokens.append(f"{parts[i]} {parts[i+1]}")
        return tokens
