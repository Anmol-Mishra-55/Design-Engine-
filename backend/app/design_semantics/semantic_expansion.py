"""
Semantic Expansion Layer
========================
Loads semantic_taxonomy.json, semantic_templates.json, generation_constraints.json
and exposes three public functions:

  get_domain_taxonomy(domain, subtype)   → dict
  get_generation_template(domain, subtype, slots) → dict with filled prompt
  validate_domain_constraints(generator, objects) → (ok: bool, violations: list)
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_DIR = Path(__file__).parent


@lru_cache(maxsize=1)
def _taxonomy() -> Dict[str, Any]:
    with open(_DIR / "semantic_taxonomy.json", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _templates() -> Dict[str, Any]:
    with open(_DIR / "semantic_templates.json", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _constraints() -> Dict[str, Any]:
    with open(_DIR / "generation_constraints.json", encoding="utf-8") as f:
        return json.load(f)


def get_domain_taxonomy(domain: str, subtype: str) -> Optional[Dict[str, Any]]:
    """
    Return the taxonomy entry for a domain+subtype pair.
    Returns None if domain or subtype not found.

    Example:
        get_domain_taxonomy("architecture", "2BHK")
        get_domain_taxonomy("vehicles", "drone")
    """
    domains = _taxonomy().get("domains", {})
    domain_entry = domains.get(domain)
    if not domain_entry:
        return None
    return domain_entry.get("subtypes", {}).get(subtype)


def get_generation_template(
    domain: str, subtype: str, slots: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Return the filled template for a domain+subtype with slot substitution applied.
    Missing optional slots are replaced with an empty string.
    Returns None if domain or subtype not found.

    Example:
        get_generation_template("architecture", "2BHK", {"city": "Mumbai", "style": "modern"})
    """
    domain_templates = _templates().get(domain)
    if not domain_templates:
        return None
    template = domain_templates.get(subtype)
    if not template:
        return None

    filled_slots = slots or {}
    result = dict(template)

    for key in ("system", "user"):
        text = result.get(key, "")
        for slot_name, slot_value in filled_slots.items():
            text = text.replace("{{" + slot_name + "}}", str(slot_value))
        # Clear any remaining unfilled optional slots
        import re

        text = re.sub(r"\{\{[^}]+\}\}", "", text)
        result[key] = text

    result["resolved_slots"] = filled_slots
    return result


def validate_domain_constraints(generator_name: str, candidate_objects: List[str]) -> Tuple[bool, List[Dict[str, str]]]:
    """
    Check a list of object class names against the generator's forbidden list.
    Returns (True, []) if clean, or (False, [list of violation dicts]) if contaminated.

    Example:
        ok, violations = validate_domain_constraints(
            "architecture_generator", ["wall", "door", "rotor"]
        )
        # → (False, [{"object": "rotor", "rule": "XD_002", ...}])
    """
    constraints = _constraints()
    gen_rules = constraints.get("generator_constraints", {}).get(generator_name)
    if not gen_rules:
        return True, []

    forbidden: List[str] = gen_rules.get("forbidden_object_classes", [])
    forbidden_set = set(forbidden)

    # Build a lookup from forbidden object → relevant cross-domain rule
    xd_rules = constraints.get("cross_domain_rules", [])
    obj_to_rule: Dict[str, str] = {}
    for rule in xd_rules:
        for obj in rule.get("blocked_object_classes", []):
            if obj not in obj_to_rule:
                obj_to_rule[obj] = rule["rule_id"]

    violations = []
    for obj in candidate_objects:
        if obj in forbidden_set:
            violations.append(
                {
                    "object": obj,
                    "generator": generator_name,
                    "rule": obj_to_rule.get(obj, "generator_constraints"),
                    "error_code": constraints["enforcement_policy"]["error_code"],
                }
            )

    return len(violations) == 0, violations
