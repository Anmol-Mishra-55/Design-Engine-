"""
BHIV AI Assistant API
Phase 3: All design generation routes through Core pipeline only.
Phase 4: All URLs come from Bucket, no fake S3 paths.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

import httpx
from app.config import settings
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bhiv/v1", tags=["BHIV Assistant"])


class DesignRequest(BaseModel):
    user_id: str
    prompt: str = Field(description="Natural language design prompt")
    city: str = Field(description="City for compliance (Mumbai, Pune, etc.)")
    project_id: Optional[str] = None
    context: Optional[Dict] = {}


class ComplianceResult(BaseModel):
    compliant: bool
    violations: List[str] = []
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


class BHIVAssistant:
    """BHIV AI Assistant orchestration layer"""

    def __init__(self):
        self.http_client = None

    async def _get_client(self) -> httpx.AsyncClient:
        if not self.http_client:
            self.http_client = httpx.AsyncClient(timeout=60.0)
        return self.http_client

    async def _run_pipeline(self, request: DesignRequest) -> BHIVResponse:
        """
        Phase 3: routes through CoreBucketCanonicalOrchestrator only.
        Phase 4: preview_url is a real Bucket URL.
        """
        start_time = datetime.now()
        request_id = f"bhiv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        client = await self._get_client()

        try:
            spec_result = await self._call_core_pipeline(request)

            compliance_result = await self._call_sohum_compliance(
                client, spec_result["spec_json"], request.city, request.project_id or request_id
            )

            rl_result = None
            try:
                rl_result = await self._call_ranjeet_rl(client, spec_result["spec_json"], request.city)
            except Exception as e:
                logger.warning(f"[{request_id}] RL optimization failed (non-blocking): {e}")

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

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[{request_id}] Error in design pipeline: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Design generation failed: {str(e)}")

    async def _call_core_pipeline(self, request: DesignRequest) -> Dict:
        """Phase 3+4: Route through Core. Returns Bucket URL."""
        from app.core_bucket_pipeline import CoreBucketCanonicalOrchestrator
        from app.utils import create_new_spec_id

        spec_id = create_new_spec_id()
        core_payload = {
            "spec_id": spec_id,
            "user_id": request.user_id,
            "project_id": request.project_id,
            "prompt": request.prompt,
            "city": request.city,
            "style": request.context.get("style", "modern") if request.context else "modern",
            "context": request.context or {},
            "constraints": {},
        }
        orchestrator = CoreBucketCanonicalOrchestrator()
        result = await orchestrator.execute(spec_id=spec_id, request_payload=core_payload)
        glb_artifact = result.artifacts.get("glb")
        preview_url = glb_artifact.url if glb_artifact else ""
        if not preview_url:
            raise RuntimeError("Core pipeline did not return a Bucket GLB URL")
        return {"spec_id": spec_id, "spec_json": result.spec_json, "preview_url": preview_url}

    async def _call_sohum_compliance(
        self, client: httpx.AsyncClient, spec_json: Dict, city: str, project_id: str
    ) -> Dict:
        sohum_url = getattr(settings, "SOHAM_URL", "https://ai-rule-api-w7z5.onrender.com")
        payload = {"spec_json": spec_json, "city": city, "project_id": project_id}
        try:
            response = await client.post(f"{sohum_url}/compliance/run_case", json=payload, timeout=90.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Sohum compliance check failed: {e}")
            return {
                "compliant": False,
                "violations": [f"Service unavailable: {e}"],
                "geometry_url": None,
                "case_id": None,
            }

    async def _call_ranjeet_rl(self, client: httpx.AsyncClient, spec_json: Dict, city: str) -> Optional[Dict]:
        yotta_url = getattr(settings, "YOTTA_URL", "https://api.yotta.com")
        headers = {}
        yotta_key = getattr(settings, "YOTTA_API_KEY_RL", None)
        if yotta_key:
            headers["Authorization"] = f"Bearer {yotta_key}"
        try:
            response = await client.post(
                f"{yotta_url}/rl/predict", json={"spec_json": spec_json, "city": city}, headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.warning(f"RL optimization failed: {e}")
            return None


assistant = BHIVAssistant()


@router.post("/design", response_model=BHIVResponse)
async def create_design(request: DesignRequest):
    """Generate complete design — routes through Core only."""
    return await assistant._run_pipeline(request)


@router.get("/health")
async def health_check():
    client = await assistant._get_client()
    health = {"bhiv": "ok", "sohum_mcp": "unknown", "ranjeet_rl": "unknown"}
    try:
        sohum_url = getattr(settings, "SOHAM_URL", "https://ai-rule-api-w7z5.onrender.com")
        r = await client.get(f"{sohum_url}/health", timeout=5.0)
        health["sohum_mcp"] = "ok" if r.status_code == 200 else "error"
    except:
        health["sohum_mcp"] = "unreachable"
    try:
        yotta_url = getattr(settings, "YOTTA_URL", "https://api.yotta.com")
        r = await client.get(f"{yotta_url}/health", timeout=5.0)
        health["ranjeet_rl"] = "ok" if r.status_code == 200 else "error"
    except:
        health["ranjeet_rl"] = "unreachable"
    return health
