"""
Core Entry Router — Phase 3
============================
/api/v1/core/generate  →  the ONLY public entry point for design generation.

Flow:
    Client → POST /api/v1/core/generate
           → injects X-Core-Token header internally
           → calls CoreBucketCanonicalOrchestrator.execute()
           → returns result

Direct POST /api/v1/generate without X-Core-Token → 403 (blocked by middleware).
"""

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.api.generate import (
    _absolute_url,
    _extract_budget,
    _extract_export_urls,
    _persist_spec,
    calculate_estimated_cost,
)
from app.auth_mongodb import get_current_user
from app.core_bucket_pipeline import CoreBucketCanonicalOrchestrator
from app.prompt_runner_adapter import PromptRunnerUnavailableError
from app.schemas import GenerateRequest, GenerateResponse
from app.spec_validator import SpecValidationError, validate_spec_json, validate_with_warnings
from fastapi import APIRouter, Depends, HTTPException, Request, status

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/core/generate", response_model=GenerateResponse, status_code=status.HTTP_201_CREATED)
async def core_generate(
    request: GenerateRequest,
    req: Request,
    current_user: str = Depends(get_current_user),
):
    """
    Public Core entry point.
    This is the ONLY route clients should call for design generation.
    Internally routes through CoreBucketCanonicalOrchestrator.
    Direct calls to /api/v1/generate are blocked (403).
    """
    start_time = time.time()

    if not request.prompt or len(request.prompt.strip()) < 10:
        raise HTTPException(status_code=400, detail="Prompt must be at least 10 characters")
    if not request.user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    req_city = request.city or "Mumbai"
    req_style = request.style or "modern"
    budget = _extract_budget(request)
    spec_id = f"spec_{uuid.uuid4().hex[:12]}"

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

    orchestrator = CoreBucketCanonicalOrchestrator()
    try:
        canonical_result = await orchestrator.execute(spec_id=spec_id, request_payload=core_payload)
    except PromptRunnerUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Core execution failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Core execution pipeline failed") from exc

    spec_json = canonical_result.spec_json

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
    metadata["entry_point"] = "core"
    if budget:
        metadata["budget_provided"] = budget

    spec_json["estimated_cost"] = {"total": estimated_cost, "currency": "INR"}

    base_url = str(req.base_url)
    export_urls = _extract_export_urls(spec_json, spec_id)
    export_urls_abs = {k: _absolute_url(base_url, v) for k, v in export_urls.items()}
    preview_url = export_urls_abs["glb"]
    compliance_check_id = f"check_{spec_id}"

    thumbnail_abs = _absolute_url(base_url, metadata.get("meshy_thumbnail_url", ""))
    meshy_video_url = metadata.get("meshy_video_url", "")

    metadata["export_urls"] = export_urls_abs
    if thumbnail_abs:
        metadata["meshy_thumbnail_url"] = thumbnail_abs

    effective_user_id = await _persist_spec(
        spec_id=spec_id,
        request=request,
        spec_json=spec_json,
        preview_url=preview_url,
        estimated_cost=estimated_cost,
        lm_provider=canonical_result.provider,
        generation_time_ms=generation_time_ms,
    )

    logger.info("Core generate complete: spec_id=%s provider=%s", spec_id, canonical_result.provider)

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
