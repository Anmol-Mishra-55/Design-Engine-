from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel


class GenerateRequest(BaseModel):
    user_id: str
    prompt: str
    city: Optional[str] = "Mumbai"
    style: Optional[str] = "modern"
    project_id: Optional[str] = None
    context: Optional[Dict] = None
    constraints: Optional[Dict] = None


class GenerateResponse(BaseModel):
    spec_id: str
    spec_json: Dict
    preview_url: str = ""
    estimated_cost: float
    compliance_check_id: str
    created_at: datetime
    spec_version: int = 1
    user_id: str
    city: Optional[str] = None
    lm_provider: Optional[str] = None
    generation_time_ms: Optional[int] = None
    export_urls: Optional[Dict[str, str]] = None
    glb_url: Optional[str] = None
    stl_url: Optional[str] = None
    step_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    meshy_video_url: Optional[str] = None
