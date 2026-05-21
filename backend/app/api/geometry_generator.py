"""
GLB Geometry Generation API — Phase 3 Enforcement

POST /api/v1/geometry/generate is BLOCKED.
All geometry generation MUST go through /api/v1/core/generate.
"""

import logging

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/geometry", tags=["Geometry Generation"])


@router.post("/generate", status_code=403)
async def generate_geometry_blocked():
    """
    Phase 3 — Direct geometry generation BLOCKED.
    All design generation MUST go through /api/v1/core/generate.
    """
    raise HTTPException(
        status_code=403,
        detail="Direct geometry generation not allowed. Use /api/v1/core/generate.",
    )
