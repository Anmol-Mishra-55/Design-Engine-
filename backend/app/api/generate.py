"""
Generate API — thin HTTP boundary layer.

All execution is delegated to CoreBucketCanonicalOrchestrator.
This file MUST NOT call prompt_runner, geometry, or storage directly.

Canonical flow enforced here:
    Client → Core.execute() → Bucket → Prompt Runner → Bucket → Core → Client
"""

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.auth_mongodb import get_current_user
from app.core_bucket_pipeline import CoreBucketCanonicalOrchestrator
from app.prompt_runner_adapter import PromptRunnerUnavailableError

# Import schemas from app.schemas package
from app.schemas import GenerateRequest, GenerateResponse
from app.spec_validator import SpecValidationError, validate_spec_json, validate_with_warnings
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
    """Extract bucket URLs from spec metadata. Returns bucket API paths only."""
    metadata = spec_json.get("metadata", {}) if isinstance(spec_json.get("metadata"), dict) else {}
    export_urls = metadata.get("export_urls", {}) if isinstance(metadata.get("export_urls"), dict) else {}

    # All URLs must come from bucket
    return {
        "glb": export_urls.get("glb") or f"/api/v1/files/geometry/{spec_id}.glb",
        "stl": export_urls.get("stl") or f"/api/v1/files/geometry/exports/{spec_id}.stl",
        "step": export_urls.get("step") or f"/api/v1/files/geometry/exports/{spec_id}.step",
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
    """Convert a relative bucket path to a full clickable URL."""
    if not path:
        return path
    if path.startswith("http"):
        return path
    return f"{base_url.rstrip('/')}{path}"


@router.post("/generate", response_model=GenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate_design(request: GenerateRequest, req: Request, current_user: str = Depends(get_current_user)):
    """
    Canonical routing — ALL execution goes through Core:

        data   = bucket.store(request)
        result = prompt_runner.execute(data)
        output = bucket.store(result)
        return output

    Direct backend calls are NOT allowed from this endpoint.
    """
    # Core bypass guard — every request must carry a valid authenticated user
    # (enforced by get_current_user). Any call that bypasses auth is rejected
    # before reaching this point. Additional guard: spec_id must not be
    # pre-supplied by the caller (Core generates it internally).
    if getattr(request, "spec_id", None):
        raise HTTPException(
            status_code=403,
            detail="Forbidden: spec_id must not be supplied by caller. All requests must originate from Core.",
        )
    start_time = time.time()

    if not request.prompt or len(request.prompt.strip()) < 10:
        raise HTTPException(status_code=400, detail="Prompt must be at least 10 characters")
    if not request.user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    req_city = request.city or "Mumbai"
    req_style = request.style or "modern"
    budget = _extract_budget(request)
    spec_id = f"spec_{uuid.uuid4().hex[:12]}"

    # ── Build Core payload ──────────────────────────────────────────────────
    core_payload = {
        "spec_id": spec_id,
        "user_id": request.user_id,
        "project_id": request.project_id,
        "prompt": request.prompt,
        "city": req_city,
        "style": req_style,
        "context": request.context or {},
        "constraints": getattr(request, "constraints", None) or {},
    }

    # ── Delegate entirely to Core ──────────────────────────────────────────
    orchestrator = CoreBucketCanonicalOrchestrator()
    try:
        canonical_result = await orchestrator.execute(spec_id=spec_id, request_payload=core_payload)
    except PromptRunnerUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Core execution failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Core execution pipeline failed") from exc

    spec_json = canonical_result.spec_json

    # ── Validate spec ──────────────────────────────────────────────────────
    try:
        validate_spec_json(spec_json)
        warnings = validate_with_warnings(spec_json)
        if warnings:
            logger.info("Spec has %d non-critical warnings", len(warnings))
    except SpecValidationError as exc:
        logger.error("Spec validation failed: %s", exc)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid specification from Prompt Runner: {exc}",
        ) from exc

    # ── Enrich metadata ──────────────────────────────────────────────────
    estimated_cost = calculate_estimated_cost(spec_json=spec_json, city=req_city, budget=budget)
    generation_time_ms = int((time.time() - start_time) * 1000)

    metadata = spec_json.setdefault("metadata", {})
    metadata["estimated_cost"] = estimated_cost
    metadata["currency"] = "INR"
    metadata["generation_provider"] = canonical_result.provider
    metadata["city"] = req_city
    metadata["style"] = req_style
    metadata["generation_time_ms"] = generation_time_ms
    metadata["bucket_trace_id"] = canonical_result.bucket_trace_id
    if budget:
        metadata["budget_provided"] = budget

    spec_json["estimated_cost"] = {"total": estimated_cost, "currency": "INR"}

    # Extract bucket URLs and make them absolute + directly downloadable
    base_url = str(req.base_url)
    export_urls = _extract_export_urls(spec_json, spec_id)
    export_urls_abs = {k: _absolute_url(base_url, v) for k, v in export_urls.items()}
    preview_url = export_urls_abs["glb"]
    compliance_check_id = f"check_{spec_id}"

    thumbnail_abs = _absolute_url(base_url, metadata.get("meshy_thumbnail_url", ""))
    meshy_video_url = metadata.get("meshy_video_url", "")

    # Store absolute URLs in metadata so downloads gallery also gets them
    metadata["export_urls"] = export_urls_abs
    if thumbnail_abs:
        metadata["meshy_thumbnail_url"] = thumbnail_abs

    # ── Persist to DB via Core (non-fatal) ────────────────────────────────
    effective_user_id = await _persist_spec(
        spec_id=spec_id,
        request=request,
        spec_json=spec_json,
        preview_url=preview_url,
        estimated_cost=estimated_cost,
        lm_provider=canonical_result.provider,
        generation_time_ms=generation_time_ms,
    )

    return GenerateResponse(
        spec_id=spec_id,
        spec_json=spec_json,
        preview_url=preview_url,
        estimated_cost=estimated_cost,
        compliance_check_id=compliance_check_id,
        created_at=datetime.now(timezone.utc),
        spec_version=1,
        user_id=effective_user_id,
        city=req_city,
        lm_provider=canonical_result.provider,
        generation_time_ms=generation_time_ms,
        export_urls=export_urls_abs,
        glb_url=export_urls_abs.get("glb"),
        stl_url=export_urls_abs.get("stl"),
        step_url=export_urls_abs.get("step"),
        thumbnail_url=thumbnail_abs or None,
        meshy_video_url=meshy_video_url or None,
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
                detail=f"Specification '{spec_id}' not found. Generate a design first using /api/v1/generate",
            )

        spec_json = db_spec.get("spec_json") or {}
        export_urls = _extract_export_urls(spec_json, spec_id)
        preview_url = db_spec.get("preview_url") or db_spec.get("geometry_url") or export_urls["glb"]

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
