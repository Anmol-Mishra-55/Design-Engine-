"""
GLB Geometry Generation API
All outputs go to bucket via upload_to_bucket().
Local file writes are NOT allowed.
"""

import logging
from datetime import datetime
from typing import Any, Dict

from app.auth_mongodb import get_current_user
from app.storage import upload_to_bucket
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/geometry", tags=["Geometry Generation"])


class GeometryRequest(BaseModel):
    spec_json: Dict[str, Any] = Field(..., description="Design specification")
    request_id: str = Field(..., description="Request identifier")
    format: str = Field(default="glb", description="Output format (glb only)")


class GeometryResponse(BaseModel):
    request_id: str
    geometry_url: str
    format: str
    file_size_bytes: int
    generation_time_ms: int


@router.post("/generate", response_model=GeometryResponse)
async def generate_geometry(
    request: GeometryRequest,
    current_user: str = Depends(get_current_user),
):
    """
    Generate GLB from spec_json["rooms"] and upload to bucket.
    Returns bucket URL — no local file is written.
    """
    if request.format.lower() != "glb":
        raise HTTPException(status_code=400, detail=f"Unsupported format: {request.format}")

    start = datetime.now()

    # 1. Generate GLB bytes from room-based geometry
    from app.geometry_generator_real import generate_real_glb

    glb_bytes = generate_real_glb(request.spec_json)

    # 2. Upload to bucket — returns canonical URL
    bucket_path = f"{request.request_id}.glb"
    bucket_url = await upload_to_bucket(
        bucket="geometry",
        path=bucket_path,
        data=glb_bytes,
        content_type="model/gltf-binary",
    )

    generation_time_ms = int((datetime.now() - start).total_seconds() * 1000)
    logger.info("Geometry uploaded: %s  %d bytes  %dms", bucket_url, len(glb_bytes), generation_time_ms)

    return GeometryResponse(
        request_id=request.request_id,
        geometry_url=bucket_url,
        format="glb",
        file_size_bytes=len(glb_bytes),
        generation_time_ms=generation_time_ms,
    )


@router.get("/download/{file_id}", include_in_schema=False)
async def download_geometry(
    file_id: str,
    current_user: str = Depends(get_current_user),
):
    """Stream a GLB file from the geometry bucket."""
    from app.storage import download_from_bucket
    from fastapi.responses import Response

    try:
        data = await download_from_bucket("geometry", file_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Geometry file not found in bucket")

    return Response(
        content=data,
        media_type="model/gltf-binary",
        headers={"Content-Disposition": f'attachment; filename="{file_id}.glb"'},
    )
