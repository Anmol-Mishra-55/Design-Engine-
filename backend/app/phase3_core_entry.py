"""
PHASE 3: Core Entry Enforcement
=======  ========================

RULE: Client → Core ONLY → Engine

Direct /api/v1/generate is BLOCKED (403).
Only /api/v1/core/generate works.

Proof:
- Attempt direct call → rejected
- Same call via Core → works
"""

from fastapi import HTTPException, status


async def enforce_core_entry_only():
    """
    Block direct access to internal endpoints.
    Force all generation through Core.
    """
    pass  # Enforcement is in core_entry.py


def block_direct_generate():
    """
    This function is called by /api/v1/generate handler.
    Always raises 403 - no exceptions.
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Direct access not allowed. Use /api/v1/core/generate (Phase 3 enforcement).",
    )
