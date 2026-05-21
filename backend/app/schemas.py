from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


# Enhanced Generate endpoint schemas
class GenerateRequest(BaseModel):
    """Enhanced design generation request"""

    user_id: str = Field(..., description="User ID")
    prompt: str = Field(..., min_length=10, max_length=2048, description="Design description")
    city: str = Field("Mumbai", description="City for compliance")
    project_id: Optional[str] = Field(None, description="Project grouping")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")
    constraints: Optional[Dict] = Field(default_factory=dict, description="Budget, area, etc.")
    style: Optional[str] = Field("modern", description="Design style")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_123",
                "prompt": "Modern 2BHK apartment with open kitchen and balcony",
                "city": "Mumbai",
                "constraints": {"budget": 5000000, "area": 850, "floors": 1},
                "style": "modern",
            }
        }


class GenerateResponse(BaseModel):
    """Enhanced design generation response"""

    spec_id: str
    spec_json: Dict[str, Any]
    preview_url: str
    compliance_check_id: Optional[str] = None
    estimated_cost: Optional[float] = None
    generation_time_ms: Optional[int] = None
    created_at: datetime
    spec_version: int = 1
    user_id: str
    city: Optional[str] = None
    lm_provider: Optional[str] = None
    glb_url: Optional[str] = None
    stl_url: Optional[str] = None
    step_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    meshy_video_url: Optional[str] = None
    export_urls: Optional[Dict[str, str]] = None
    download_urls: Optional[Dict[str, str]] = None


# Switch endpoint schemas (material switching)
class SwitchTarget(BaseModel):
    object_id: Optional[str] = None
    object_query: Optional[Dict[str, Any]] = None


class SwitchUpdate(BaseModel):
    material: Optional[str] = None
    color_hex: Optional[str] = None
    texture_override: Optional[str] = None


class SwitchRequest(BaseModel):
    user_id: str
    spec_id: str
    target: SwitchTarget
    update: SwitchUpdate
    note: Optional[str] = None


class SwitchChanged(BaseModel):
    object_id: str
    field: str
    before: str
    after: str


class SwitchResponse(BaseModel):
    spec_id: str
    iteration_id: str
    updated_spec_json: Dict[str, Any]
    preview_url: str
    changed: SwitchChanged
    saved_at: datetime


# Provider switch schemas
class ProviderSwitchRequest(BaseModel):
    provider: str


# Evaluate endpoint schemas
class EvaluateRequest(BaseModel):
    spec_id: str
    user_id: str
    rating: int
    notes: Optional[str] = None


class EvaluateResponse(BaseModel):
    ok: bool
    saved_id: str


# Iterate endpoint schemas
class IterateRequest(BaseModel):
    spec_id: str
    strategy: str  # e.g., "improve_materials"
    user_id: str


class IterateResponse(BaseModel):
    before: Dict[str, Any]
    after: Dict[str, Any]
    feedback: str


# Compliance endpoint schemas
class ComplianceRequest(BaseModel):
    spec_id: str
    user_id: str


class ComplianceResponse(BaseModel):
    compliance_url: str
    status: str


# Core run endpoint schemas
class CoreRunRequest(BaseModel):
    pipeline: List[str]  # e.g., ["generate", "evaluate", "iterate"]
    input: Dict[str, Any]  # input data for pipeline steps

    class Config:
        extra = "forbid"  # Don't allow extra fields


class CoreRunResponse(BaseModel):
    outputs: Dict[str, Any]  # aggregated outputs from all steps


# Report schema
class Report(BaseModel):
    report_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    spec: Dict[str, Any]
    iterations: List[Dict[str, Any]]
    evaluations: List[Dict[str, Any]]
    preview_urls: List[str]


# Generic response
class MessageResponse(BaseModel):
    message: str


# Health check schema
class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
    database: str
    storage: str
    lm_provider: str


# Error response schemas
class ErrorDetail(BaseModel):
    field: Optional[str] = None
    message: str
    value: Optional[Any] = None


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    field_errors: Optional[List[ErrorDetail]] = None
    timestamp: datetime
