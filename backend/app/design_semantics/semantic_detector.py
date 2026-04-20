"""
Design Semantics Layer - Semantic Detection Logic
==================================================
Single entry point: extract_semantics(prompt) -> SemanticResult

Detects from natural language prompt:
  - BHK type       → loads bhk_definitions.json
  - Style profile  → loads style_profiles.json
  - Layout rules   → loads layout_rules.json
  - Area / budget / stories / city
"""

import json
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

_SEMANTICS_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# JSON loaders (cached — files read once per process)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _load_bhk() -> Dict[str, Any]:
    with open(_SEMANTICS_DIR / "bhk_definitions.json", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_styles() -> Dict[str, Any]:
    with open(_SEMANTICS_DIR / "style_profiles.json", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_layout_rules() -> Dict[str, Any]:
    with open(_SEMANTICS_DIR / "layout_rules.json", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class SemanticResult:
    """Fully resolved semantic context extracted from a prompt."""

    # BHK
    bhk_key: Optional[str] = None  # e.g. "2BHK", "VILLA"
    bhk_definition: Optional[Dict] = None  # full entry from bhk_definitions.json

    # Style
    style_key: Optional[str] = None  # e.g. "modern", "luxury"
    style_profile: Optional[Dict] = None  # full entry from style_profiles.json

    # Layout
    layout_rules: Optional[Dict] = None  # full layout_rules.json

    # Extracted scalars
    area_sqft: Optional[float] = None
    area_sqm: Optional[float] = None
    budget_inr: Optional[float] = None
    stories: Optional[int] = None
    city: Optional[str] = None

    # Confidence
    bhk_confidence: float = 0.0
    style_confidence: float = 0.0

    # Raw signals (for debugging)
    matched_bhk_signals: List[str] = field(default_factory=list)
    matched_style_signals: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# BHK Detector
# ---------------------------------------------------------------------------

# Ordered from most-specific to least-specific
_BHK_PATTERNS: List[tuple] = [
    # explicit "NБHK" / "N BHK" patterns
    (r"\b5\s*bhk\b", "5BHK", 1.0),
    (r"\b4\s*bhk\b", "4BHK", 1.0),
    (r"\b3\s*bhk\b", "3BHK", 1.0),
    (r"\b2\s*bhk\b", "2BHK", 1.0),
    (r"\b1\s*bhk\b", "1BHK", 1.0),
    # word forms
    (r"\bfive\s+bedroom\b", "5BHK", 0.95),
    (r"\bfour\s+bedroom\b", "4BHK", 0.95),
    (r"\bthree\s+bedroom\b", "3BHK", 0.95),
    (r"\btwo\s+bedroom\b", "2BHK", 0.95),
    (r"\bone\s+bedroom\b", "1BHK", 0.95),
    # digit + bedroom
    (r"\b5\s+bedroom\b", "5BHK", 0.95),
    (r"\b4\s+bedroom\b", "4BHK", 0.95),
    (r"\b3\s+bedroom\b", "3BHK", 0.95),
    (r"\b2\s+bedroom\b", "2BHK", 0.95),
    (r"\b1\s+bedroom\b", "1BHK", 0.95),
    # special types
    (r"\bpenthouse\b", "PENTHOUSE", 1.0),
    (r"\bvilla\b", "VILLA", 0.9),
    (r"\bbungalow\b", "VILLA", 0.85),
    (r"\bindependent\s+house\b", "VILLA", 0.85),
    (r"\bduplex\b", "VILLA", 0.8),
    (r"\bfarmhouse\b", "VILLA", 0.8),
    # studio / compact → 1BHK
    (r"\bstudio\b", "1BHK", 0.85),
    (r"\bcompact\s+apartment\b", "1BHK", 0.8),
]


def detect_bhk(prompt: str) -> tuple:
    """
    Returns (bhk_key, confidence, matched_signals).
    Tries patterns in priority order; first match wins.
    When multiple BHK types appear in one prompt, the highest-priority
    (earliest in _BHK_PATTERNS) match is returned — not the last one found.
    """
    p = prompt.lower()
    bhk_data = _load_bhk()

    for pattern, key, conf in _BHK_PATTERNS:
        m = re.search(pattern, p, re.IGNORECASE)
        if m and key in bhk_data:
            return key, conf, [m.group(0).strip()]

    return None, 0.0, []


# ---------------------------------------------------------------------------
# Style Detector
# ---------------------------------------------------------------------------


def detect_style(prompt: str) -> tuple:
    """
    Returns (style_key, confidence, matched_signals).
    Scores every style by keyword hits; highest wins.
    """
    p = prompt.lower()
    styles = _load_styles()

    best_key: Optional[str] = None
    best_score = 0.0
    best_signals: List[str] = []

    for style_key, profile in styles.items():
        if not isinstance(profile, dict):
            continue
        keywords: List[str] = profile.get("keywords", [])
        hits = [kw for kw in keywords if re.search(r"\b" + re.escape(kw) + r"\b", p)]
        if hits:
            score = round(min(1.0, len(hits) / max(len(keywords), 1) * 2.0), 3)
            if score > best_score:
                best_score = score
                best_key = style_key
                best_signals = hits

    # Default to "modern" with low confidence if nothing matched
    if not best_key:
        best_key = "modern"
        best_score = 0.2
        best_signals = []

    return best_key, best_score, best_signals


# ---------------------------------------------------------------------------
# Area Detector
# ---------------------------------------------------------------------------

_AREA_PATTERNS = [
    # "1200 sq ft" / "1200 sqft" / "1200 square feet"
    (r"(\d+(?:\.\d+)?)\s*(?:sq\.?\s*ft|sqft|square\s*feet|square\s*foot)", "sqft"),
    # "120 sq m" / "120 sqm" / "120 square meters"
    (r"(\d+(?:\.\d+)?)\s*(?:sq\.?\s*m|sqm|square\s*met(?:er|re)s?)", "sqm"),
]


def detect_area(prompt: str) -> tuple:
    """Returns (area_sqft, area_sqm) — both or one may be None."""
    p = prompt.lower()
    sqft = sqm = None

    for pattern, unit in _AREA_PATTERNS:
        m = re.search(pattern, p)
        if m:
            val = float(m.group(1))
            if unit == "sqft":
                sqft = val
                sqm = round(val * 0.092903, 2)
            else:
                sqm = val
                sqft = round(val / 0.092903, 2)
            break

    return sqft, sqm


# ---------------------------------------------------------------------------
# Budget Detector
# ---------------------------------------------------------------------------

_BUDGET_PATTERNS = [
    # "50 lakh" / "50L" / "50 lac"
    (r"(\d+(?:\.\d+)?)\s*(?:lakh|lac|l)\b", 1e5),
    # "1.5 crore" / "1.5 cr"
    (r"(\d+(?:\.\d+)?)\s*(?:crore|cr)\b", 1e7),
    # plain number with "budget" nearby — treat as INR
    (r"budget\s+(?:of\s+)?(?:rs\.?\s*)?(\d+(?:,\d+)*(?:\.\d+)?)", 1.0),
    # "Rs 5000000" / "INR 5000000"
    (r"(?:rs\.?|inr)\s*(\d+(?:,\d+)*(?:\.\d+)?)", 1.0),
]


def detect_budget(prompt: str) -> Optional[float]:
    """Returns budget in INR or None."""
    p = prompt.lower()
    for pattern, multiplier in _BUDGET_PATTERNS:
        m = re.search(pattern, p)
        if m:
            raw = m.group(1).replace(",", "")
            return float(raw) * multiplier
    return None


# ---------------------------------------------------------------------------
# Stories Detector
# ---------------------------------------------------------------------------

_STORIES_PATTERNS = [
    (r"\b(\d+)\s*(?:stor(?:ey|y|ies)|floor(?:s)?)\b", None),
    (r"\bground\s+\+\s*(\d+)\b", None),  # "G+2"
    (r"\bg\s*\+\s*(\d+)\b", None),
    (r"\bsingle\s+stor(?:ey|y)\b", "1"),
    (r"\bdouble\s+stor(?:ey|y)\b", "2"),
    (r"\btwo\s+stor(?:ey|y|ies)\b", "2"),
    (r"\bthree\s+stor(?:ey|y|ies)\b", "3"),
]

_MAX_STORIES = 10  # hard cap — prevents memory exhaustion on extreme inputs


def detect_stories(prompt: str) -> Optional[int]:
    """Returns number of stories/floors (capped at _MAX_STORIES) or None."""
    p = prompt.lower()
    for pattern, fixed in _STORIES_PATTERNS:
        m = re.search(pattern, p, re.IGNORECASE)
        if m:
            val = fixed if fixed else m.group(1)
            try:
                return min(int(val), _MAX_STORIES)
            except (ValueError, IndexError):
                continue
    return None


# ---------------------------------------------------------------------------
# City Detector
# ---------------------------------------------------------------------------

_CITIES = [
    "mumbai",
    "pune",
    "ahmedabad",
    "nashik",
    "bangalore",
    "bengaluru",
    "delhi",
    "hyderabad",
    "chennai",
    "kolkata",
    "surat",
    "jaipur",
]


def detect_city(prompt: str) -> Optional[str]:
    """Returns title-cased city name or None."""
    p = prompt.lower()
    for city in _CITIES:
        if re.search(r"\b" + city + r"\b", p):
            # Normalise bengaluru → Bangalore
            return "Bangalore" if city == "bengaluru" else city.title()
    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def extract_semantics(prompt: str) -> SemanticResult:
    """
    Extract full design semantics from a natural language prompt.

    Usage:
        result = extract_semantics("Design a 3BHK modern apartment in Mumbai")
        result.bhk_key          # "3BHK"
        result.bhk_definition   # full dict from bhk_definitions.json
        result.style_key        # "modern"
        result.style_profile    # full dict from style_profiles.json
        result.layout_rules     # full layout_rules.json
        result.city             # "Mumbai"
    """
    if not prompt or not prompt.strip():
        return SemanticResult()

    bhk_key, bhk_conf, bhk_signals = detect_bhk(prompt)
    style_key, style_conf, style_sigs = detect_style(prompt)
    area_sqft, area_sqm = detect_area(prompt)
    budget_inr = detect_budget(prompt)
    stories = detect_stories(prompt)
    city = detect_city(prompt)

    bhk_data = _load_bhk()
    styles = _load_styles()
    layout = _load_layout_rules()

    return SemanticResult(
        bhk_key=bhk_key,
        bhk_definition=bhk_data.get(bhk_key) if bhk_key else None,
        style_key=style_key,
        style_profile=styles.get(style_key) if style_key else None,
        layout_rules=layout,
        area_sqft=area_sqft,
        area_sqm=area_sqm,
        budget_inr=budget_inr,
        stories=stories,
        city=city,
        bhk_confidence=bhk_conf,
        style_confidence=style_conf,
        matched_bhk_signals=bhk_signals,
        matched_style_signals=style_sigs,
    )
