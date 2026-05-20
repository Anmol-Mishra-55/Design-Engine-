"""
PHASE 1: Storage Enforcement
===========================

RULE: All outputs go to Bucket ONLY.
No local file writes. No fallbacks.

If Bucket fails → ERROR (no local copy).
If local file exists → DELETED.
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Paths to REMOVE
FORBIDDEN_PATHS = [
    "data/geometry_outputs/",
    "data/exports/",
    "data/static/geometry/",
    "/static/geometry/",
    "/static/exports/",
]


def kill_false_paths():
    """
    PHASE 1: Remove all local storage paths.
    Enforce Bucket-only storage.
    """
    logger.warning("=" * 70)
    logger.warning("PHASE 1: KILLING FALSE PATHS")
    logger.warning("=" * 70)
    
    for path in FORBIDDEN_PATHS:
        p = Path(path)
        if p.exists():
            try:
                import shutil
                if p.is_dir():
                    shutil.rmtree(p)
                    logger.warning(f"REMOVED directory: {path}")
                else:
                    p.unlink()
                    logger.warning(f"REMOVED file: {path}")
            except Exception as e:
                logger.error(f"Failed to remove {path}: {e}")
    
    logger.warning("FALSE PATHS KILLED - BUCKET ONLY MODE ACTIVE")
    logger.warning("=" * 70)


async def enforce_bucket_only():
    """
    Enforce that NO local files are written.
    All storage goes through Bucket API.
    """
    # Verify no local geometry output directory
    if Path("data/geometry_outputs/").exists():
        raise RuntimeError(
            "FATAL: Local geometry output directory exists. "
            "PHASE 1 enforcement failed. Delete /data/geometry_outputs/ and restart."
        )
    
    logger.info("✓ Bucket-only enforcement active")
