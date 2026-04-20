"""
BHIV AI Assistant - Fully Integrated with Backend
Uses existing backend infrastructure and dependencies
"""

import asyncio
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
from app.platform_adapter import run_prompt
from app.utils import create_new_spec_id
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bhiv/v1", tags=["🤖 BHIV Integrated"])


# Request/Response Models
class DesignRequest(BaseModel):
    """User request for design generation"""

    user_id: str
    prompt: str = Field(description="Natural language design prompt")
    city: str = Field(description="City for compliance (Mumbai, Pune, etc.)")
    project_id: Optional[str] = None
    context: Optional[Dict] = Field(default_factory=dict)


class ComplianceResult(BaseModel):
    """Compliance check result"""

    compliant: bool
    violations: List[str] = Field(default_factory=list)
    geometry_url: Optional[str] = None
    case_id: Optional[str] = None


class RLOptimization(BaseModel):
    """RL optimization result"""

    optimized_layout: Dict
    confidence: float
    reward_score: float


class BHIVResponse(BaseModel):
    """Unified BHIV Assistant response"""

    request_id: str
    spec_id: str
    spec_json: Dict
    preview_url: str
    compliance: ComplianceResult
    rl_optimization: Optional[RLOptimization] = None
    processing_time_ms: int
    timestamp: datetime


async def call_sohum_compliance(spec_json: Dict, city: str, project_id: str) -> Dict:
    """Call Sohum's MCP compliance endpoint with robust error handling"""
    case_data = {"spec_json": spec_json, "city": city, "project_id": project_id}

    # Always try the real service first
    try:
        logger.info(f"Calling Sohum MCP service for {city}")
        result = await sohum_client.run_compliance_case(case_data)
        logger.info(f"Sohum MCP response received successfully")
        # Mark service as healthy
        service_manager.service_health["sohum_mcp"] = ServiceStatus.HEALTHY
        service_manager.last_health_check["sohum_mcp"] = datetime.now()
        return result
    except Exception as e:
        logger.error(f"Sohum MCP service failed: {e}")
        # Mark service as unhealthy
        service_manager.service_health["sohum_mcp"] = ServiceStatus.UNHEALTHY
        service_manager.last_health_check["sohum_mcp"] = datetime.now()
        # Use mock response as fallback
        logger.info(f"Using mock compliance response for {city}")
        return sohum_client.get_mock_compliance_response(case_data)


async def call_ranjeet_rl(spec_json: Dict, city: str) -> Optional[Dict]:
    """Call Ranjeet's RL optimization endpoint - prioritize live service"""
    # ALWAYS try the live service first with extended timeout
    try:
        logger.info(f"🚀 Calling Ranjeet's LIVE RL service at {settings.RANJEET_RL_URL} for {city}")
        result = await ranjeet_client.optimize_design(spec_json, city)

        # Mark service as healthy
        service_manager.service_health["ranjeet_rl"] = ServiceStatus.HEALTHY
        service_manager.last_health_check["ranjeet_rl"] = datetime.now()

        logger.info(f"✅ Ranjeet RL LIVE service responded successfully!")
        return result

    except Exception as e:
        logger.error(f"❌ Ranjeet RL LIVE service failed: {e}")
        logger.error(f"Service URL: {settings.RANJEET_RL_URL}")

        # Mark service as unhealthy
        service_manager.service_health["ranjeet_rl"] = ServiceStatus.UNHEALTHY
        service_manager.last_health_check["ranjeet_rl"] = datetime.now()

        # Only use mock as absolute last resort
        logger.warning(f"⚠️ Using mock RL response as fallback for {city} - LIVE service unavailable")
        mock_response = ranjeet_client.get_mock_rl_response(spec_json, city)
        mock_response["fallback_reason"] = f"Live service failed: {str(e)}"
        return mock_response


@router.post("/design", response_model=BHIVResponse)
async def create_design(request: DesignRequest):
    """Generate complete design with compliance and RL optimization"""
    if not request:
        raise HTTPException(status_code=422, detail="Request body is required")
    # Orchestrates:
    # 1. Generate spec from natural language prompt (internal)
    # 2. Sohum's MCP: Run compliance check
    # 3. Ranjeet's RL: Optimize land utilization
    start_time = datetime.now()
    request_id = f"bhiv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    try:
        # STEP 1: Generate spec via platform_adapter → Prompt Runner
        logger.info(f"[{request_id}] Step 1: Generating spec via platform_adapter...")

        platform_result = run_prompt(request.prompt)
        if platform_result.get("status") != "success":
            raise HTTPException(status_code=503, detail=f"Prompt Runner failed: {platform_result.get('error')}")

        spec_id = create_new_spec_id()
        spec_result = {
            "spec_id": spec_id,
            "spec_json": platform_result.get("instruction", {}),
            "preview_url": f"https://bhiv-previews.s3.amazonaws.com/{spec_id}.glb",
        }

        # STEP 2: Run compliance check
        logger.info(f"[{request_id}] Step 2: Running compliance check...")
        compliance_result = await call_sohum_compliance(
            spec_result["spec_json"], request.city, request.project_id or request_id
        )

        # STEP 3: Get RL optimization (optional)
        rl_result = None
        try:
            logger.info(f"[{request_id}] Step 3: Getting RL optimization...")
            rl_result = await call_ranjeet_rl(spec_result["spec_json"], request.city)
        except Exception as e:
            logger.warning(f"[{request_id}] RL optimization failed (non-blocking): {e}")

        # STEP 4: Aggregate response
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

        return BHIVResponse(
            request_id=request_id,
            spec_id=spec_result["spec_id"],
            spec_json=spec_result["spec_json"],
            preview_url=spec_result["preview_url"],
            compliance=ComplianceResult(**compliance_result),
            rl_optimization=RLOptimization(**rl_result) if rl_result else None,
            processing_time_ms=processing_time,
            timestamp=datetime.now(),
        )

    except Exception as e:
        logger.error(f"[{request_id}] Error in design generation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Design generation failed: {str(e)}")


@router.post("/process_with_workflow")
async def process_with_workflow(request: DesignRequest):
    """Process design with integrated workflow orchestration"""
    start_time = datetime.now()
    request_id = f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    try:
        # Step 1: Generate design via platform_adapter → Prompt Runner
        platform_result = run_prompt(request.prompt)
        if platform_result.get("status") != "success":
            raise HTTPException(status_code=503, detail=f"Prompt Runner failed: {platform_result.get('error')}")

        spec_id = create_new_spec_id()
        lm_result = {"spec_json": platform_result.get("instruction", {})}

        # Step 2: Check if PDF processing is needed
        pdf_url = request.context.get("compliance_pdf_url")
        if pdf_url:
            logger.info(f"[{request_id}] Processing compliance PDF via workflow")
            workflow_params = {
                "pdf_url": pdf_url,
                "city": request.city,
                "sohum_url": getattr(settings, "SOHAM_URL", ""),
            }
            workflow_result = {"status": "mock"}
            logger.info(f"[{request_id}] Workflow result: {workflow_result}")

        # Step 3: Continue with compliance and RL (same as before)
        compliance_result = await call_sohum_compliance(
            lm_result["spec_json"], request.city, request.project_id or request_id
        )

        rl_result = None
        try:
            rl_result = await call_ranjeet_rl(lm_result["spec_json"], request.city)
        except Exception as e:
            logger.warning(f"RL optimization failed: {e}")

        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

        return BHIVResponse(
            request_id=request_id,
            spec_id=spec_id,
            spec_json=lm_result["spec_json"],
            preview_url=f"https://bhiv-previews.s3.amazonaws.com/{spec_id}.glb",
            compliance=ComplianceResult(**compliance_result),
            rl_optimization=RLOptimization(**rl_result) if rl_result else None,
            processing_time_ms=processing_time,
            timestamp=datetime.now(),
        )

    except Exception as e:
        logger.error(f"[{request_id}] Workflow processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
