"""
Generate API — BLOCKED endpoint.

Direct POST /api/v1/generate is forbidden.
All design generation MUST go through /api/v1/core/generate.

Phase 3 enforcement: this route always returns 403.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.auth_mongodb import get_current_user
from app.database_mongodb import get_database
from app.schemas import GenerateRequest, GenerateResponse
from fastapi import APIRouter, Depends, HTTPException, Request, status

router = APIRouter()
logger = logging.getLogger(__name__)


def _extract_budget(request: GenerateRequest) -> Optional[float]:
    constraints = getattr(request, "constraints", None) or {}
    context = request.context or {}

    budget = constraints.get("budget") if isinstance(constraints, dict) else None
    if budget is None and isinstance(context, dict):
        budget = context.get("budget")

    if isinstance(budget, (int, float)) and budget > 0:
        return float(budget)
    return None


def calculate_estimated_cost(spec_json: Dict[str, Any], city: str, budget: Optional[float] = None) -> float:
    """Estimate cost in INR from dimensions, city and optional budget."""
    dimensions = spec_json.get("dimensions", {}) if isinstance(spec_json.get("dimensions"), dict) else {}
    width = float(dimensions.get("width", 10) or 10)
    length = float(dimensions.get("length", 10) or 10)
    stories = max(1, int(spec_json.get("stories", 1) or 1))

    area_sqm = max(1.0, width * length)
    area_sqft = area_sqm * 10.764

    city_rates = {
        "Mumbai": 2100,
        "Nashik": 1000,
        "Pune": 1450,
        "Ahmedabad": 1775,
        "Bangalore": 1800,
        "Delhi": 1700,
    }
    rate_per_sqft = city_rates.get(city or "Mumbai", 2100)
    calculated = int(area_sqft * rate_per_sqft * stories)

    if budget and budget > 0:
        return float(int(budget * 0.95))

    return float(max(calculated, 100000))


def _extract_export_urls(spec_json: Dict[str, Any], spec_id: str) -> Dict[str, str]:
    """
    Extract Bucket URLs from spec metadata.
    Phase 1: ONLY returns real Bucket URLs from metadata.
    If metadata has no export_urls, returns empty strings — callers must handle missing URLs.
    NO fallback to /api/v1/files/... local paths.
    """
    metadata = spec_json.get("metadata", {}) if isinstance(spec_json.get("metadata"), dict) else {}
    export_urls = metadata.get("export_urls", {}) if isinstance(metadata.get("export_urls"), dict) else {}

    return {
        "glb": export_urls.get("glb", ""),
        "stl": export_urls.get("stl", ""),
        "step": export_urls.get("step", ""),
    }


async def _persist_spec(
    spec_id: str,
    request: GenerateRequest,
    spec_json: Dict[str, Any],
    preview_url: str,
    estimated_cost: float,
    lm_provider: str,
    generation_time_ms: int,
) -> str:
    """Persist spec to MongoDB. Non-fatal — DB failure does not block the response."""
    from app.database_mongodb import get_database

    try:
        db = get_database()
        user = await db.users.find_one({"$or": [{"_id": request.user_id}, {"username": request.user_id}]})
        if not user:
            await db.users.insert_one(
                {
                    "_id": request.user_id,
                    "username": request.user_id,
                    "email": f"{request.user_id}@example.com",
                    "password_hash": "auto_generated_service_account",
                    "full_name": f"User {request.user_id}",
                    "is_active": True,
                    "created_at": datetime.now(timezone.utc),
                }
            )
        await db.specs.insert_one(
            {
                "_id": spec_id,
                "user_id": request.user_id,
                "project_id": request.project_id,
                "prompt": request.prompt,
                "city": request.city or "Mumbai",
                "spec_json": spec_json,
                "design_type": spec_json.get("design_type"),
                "preview_url": preview_url,
                "geometry_url": preview_url,
                "estimated_cost": estimated_cost,
                "currency": "INR",
                "compliance_status": "pending",
                "status": "final",
                "version": 1,
                "generation_time_ms": generation_time_ms,
                "lm_provider": lm_provider,
                "created_at": datetime.now(timezone.utc),
            }
        )
        logger.info("Spec %s persisted to database", spec_id)
    except Exception as db_err:
        logger.error("DB persist failed for %s (non-fatal): %s", spec_id, db_err)
    return request.user_id


def _absolute_url(base_url: str, path: str) -> str:
    """Return path as-is if it's already a full URL, otherwise skip (no local path construction)."""
    if not path:
        return path
    if path.startswith("http"):
        return path
    # Phase 1: do NOT construct local URLs — return empty so callers know it's missing
    return ""


@router.post("/generate", status_code=403)
async def generate_design_blocked():
    """
    Phase 3 — Direct access BLOCKED.
    All design generation requests MUST go through /api/v1/core/generate.
    """
    raise HTTPException(
        status_code=403,
        detail="Direct access not allowed. Use /api/v1/core/generate.",
    )


@router.get("/specs/{spec_id}", response_model=GenerateResponse)
async def get_spec(spec_id: str, current_user: str = Depends(get_current_user)):
    """Retrieve existing specification by ID."""
    from app.database_mongodb import get_database

    try:
        db = get_database()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        db_spec = await db.specs.find_one({"_id": spec_id})
        if not db_spec:
            raise HTTPException(
                status_code=404,
                detail=f"Specification '{spec_id}' not found.",
            )

        spec_json = db_spec.get("spec_json") or {}
        export_urls = _extract_export_urls(spec_json, spec_id)
        preview_url = db_spec.get("preview_url") or db_spec.get("geometry_url") or export_urls.get("glb", "")

        estimated_cost = db_spec.get("estimated_cost")
        if estimated_cost is None:
            estimated_cost = (
                spec_json.get("estimated_cost", {}).get("total")
                if isinstance(spec_json.get("estimated_cost"), dict)
                else None
            )
        if estimated_cost is None:
            estimated_cost = 0.0

        return GenerateResponse(
            spec_id=db_spec["_id"],
            spec_json=spec_json,
            preview_url=preview_url,
            estimated_cost=float(estimated_cost),
            compliance_check_id=f"check_{spec_id}",
            created_at=db_spec.get("created_at") or datetime.now(timezone.utc),
            spec_version=db_spec.get("version") or 1,
            user_id=db_spec["user_id"],
            city=db_spec["city"],
            lm_provider=db_spec.get("lm_provider"),
            generation_time_ms=db_spec.get("generation_time_ms"),
            export_urls=export_urls,
            glb_url=export_urls.get("glb"),
            stl_url=export_urls.get("stl"),
            step_url=export_urls.get("step"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving spec {spec_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error")
