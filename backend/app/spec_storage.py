"""
Spec Storage — MongoDB only. No local file writes.
Raises on failure — no silent fallbacks.
"""
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# In-memory cache for within-request spec access (not persistence)
_spec_cache: Dict[str, Dict] = {}


def save_spec(spec_id: str, spec_data: Dict) -> None:
    """Cache spec in memory. Persistence is handled by MongoDB in generate.py."""
    _spec_cache[spec_id] = spec_data
    logger.info(f"Spec cached in memory: {spec_id}")


def get_spec(spec_id: str) -> Optional[Dict]:
    """Retrieve spec from in-memory cache."""
    return _spec_cache.get(spec_id)
