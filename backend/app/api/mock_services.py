"""
Mock services for MCP and RL agents
Provides fallback responses when external services are unavailable
"""
import asyncio
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/mock", tags=["Mock Services"])


class MockComplianceResponse(BaseModel):
    case_id: str
    compliant: bool
    violations: list
    confidence_score: float
    geometry_url: Optional[str] = None


class MockRLResponse(BaseModel):
    optimized_layout: Dict[str, Any]
    confidence: float
    reward_score: float


@router.post("/compliance/run_case", response_model=MockComplianceResponse)
async def mock_compliance_check(payload: Dict[str, Any]):
    """Mock MCP compliance endpoint"""
    await asyncio.sleep(0.1)  # Simulate processing

    return MockComplianceResponse(
        case_id=f"mock_case_{uuid.uuid4().hex[:8]}",
        compliant=True,
        violations=[],
        confidence_score=0.85,
        geometry_url=None,
    )


@router.post("/rl/optimize", response_model=MockRLResponse)
async def mock_rl_optimize(payload: Dict[str, Any]):
    """Mock RL optimization endpoint"""
    await asyncio.sleep(0.1)  # Simulate processing

    return MockRLResponse(
        optimized_layout={"layout_type": "optimized", "efficiency_score": 0.92, "space_utilization": 0.88},
        confidence=0.87,
        reward_score=0.91,
    )
