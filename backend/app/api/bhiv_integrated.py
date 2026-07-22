"""
BHIV AI Assistant - Integrated
Phase 3: All design generation routes through /api/v1/core/generate (Core only).
Phase 4: No fake S3 URLs. All URLs come from Bucket.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

import httpx
from app.config import settings
from app.external_services import (
    ServiceStatus,
    get_service_health_status,
    ranjeet_client,
    service_manager,
    sohum_client,
)
from app.utils import create_new_spec_id
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bhiv/v1", tags=["BHIV Integrated"])


class DesignRequest(BaseModel):
    user_id: str
    prompt: str = Field(description="Natural language design prompt")
    city: str = Field(description="City for compliance (Mumbai, Pune, etc.)")
    project_id: Optional[str] = None
    context: Optional[Dict] = Field(default_factory=dict)


class ComplianceResult(BaseModel):
    compliant: bool
    violations: List[str] = Field(default_factory=list)
    geometry_url: Optional[str] = None
    case_id: Optional[str] = None


class RLOptimization(BaseModel):
    optimized_layout: Dict
    confidence: float
    reward_score: float


class BHIVResponse(BaseModel):
    request_id: str
    spec_id: str
    spec_json: Dict
    preview_url: str
    compliance: ComplianceResult
    rl_optimization: Optional[RLOptimization] = None
    processing_time_ms: int
    timestamp: datetime


async def call_sohum_compliance(spec_json: Dict, city: str, project_id: str) -> Dict:
    case_data = {"spec_json": spec_json, "city": city, "project_id": project_id}
    try:
        result = await sohum_client.run_compliance_case(case_data)
        service_manager.service_health["sohum_mcp"] = ServiceStatus.HEALTHY
        return result
    except Exception as e:
        logger.error(f"Sohum MCP service failed: {e}")
        service_manager.service_health["sohum_mcp"] = ServiceStatus.UNHEALTHY
        return {"compliant": False, "violations": [], "geometry_url": None, "case_id": None}


async def call_ranjeet_rl(spec_json: Dict, city: str) -> Optional[Dict]:
    try:
        result = await ranjeet_client.optimize_design(spec_json, city)
        service_manager.service_health["ranjeet_rl"] = ServiceStatus.HEALTHY
        return result
    except Exception as e:
        logger.error(f"Ranjeet RL service failed: {e}")
        service_manager.service_health["ranjeet_rl"] = ServiceStatus.UNHEALTHY
        mock = ranjeet_client.get_mock_rl_response(spec_json, city)
        mock["fallback_reason"] = str(e)
        return mock


@router.post("/design", response_model=BHIVResponse)
async def create_design(request: DesignRequest):
    """
    Generate complete design with compliance and RL optimization.
    Phase 3: design generation goes through Core pipeline only.
    Phase 4: preview_url comes from Bucket, not fake S3.
    """
    start_time = datetime.now()
    request_id = f"bhiv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    try:
        # Phase 3: call Core pipeline via internal HTTP — not platform_adapter directly
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Build a GenerateRequest-compatible payload and call core_generate directly
            from app.core_bucket_pipeline import CoreBucketCanonicalOrchestrator
            from app.prompt_runner_adapter import PromptRunnerAdapterBridge, PromptRunnerUnavailableError
            from app.schemas import GenerateRequest

            spec_id = create_new_spec_id()
            core_payload = {
                "spec_id": spec_id,
                "user_id": request.user_id,
                "project_id": request.project_id,
                "prompt": request.prompt,
                "city": request.city,
                "style": "modern",
                "context": request.context or {},
                "constraints": {},
            }

            orchestrator = CoreBucketCanonicalOrchestrator()
            canonical_result = await orchestrator.execute(spec_id=spec_id, request_payload=core_payload)

        spec_json = canonical_result.spec_json
        # Phase 4: preview_url from Bucket artifacts only
        preview_url = canonical_result.artifacts.get("glb", None)
        preview_url = preview_url.url if preview_url else ""

        if not preview_url:
            raise HTTPException(status_code=500, detail="Bucket did not return a GLB URL")

    except PromptRunnerUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{request_id}] Core pipeline failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Design generation failed: {str(e)}")

    # Compliance check
    compliance_result = await call_sohum_compliance(spec_json, request.city, request.project_id or request_id)

    # RL optimization (optional)
    rl_result = None
    try:
        rl_result = await call_ranjeet_rl(spec_json, request.city)
    except Exception as e:
        logger.warning(f"[{request_id}] RL optimization failed (non-blocking): {e}")

    processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

    return BHIVResponse(
        request_id=request_id,
        spec_id=spec_id,
        spec_json=spec_json,
        preview_url=preview_url,
        compliance=ComplianceResult(**compliance_result),
        rl_optimization=RLOptimization(**rl_result) if rl_result else None,
        processing_time_ms=processing_time,
        timestamp=datetime.now(),
    )


@router.post("/process_with_workflow")
async def process_with_workflow(request: DesignRequest):
    """Process design with workflow — delegates to /design."""
    return await create_design(request)
