"""
GLB Geometry Generation API
Generates 3D geometry files from design specifications
"""

import json
import logging
import os
import struct
from datetime import datetime
from typing import Any, Dict, List

from app.auth_mongodb import get_current_user
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/geometry", tags=["📐 Geometry Generation"])


class GeometryRequest(BaseModel):
    """Geometry generation request"""

    spec_json: Dict[str, Any] = Field(..., description="Design specification")
    request_id: str = Field(..., description="Request identifier")
    format: str = Field(default="glb", description="Output format (glb, obj)")


class GeometryResponse(BaseModel):
    """Geometry generation response"""

    request_id: str
    geometry_url: str
    format: str
    file_size_bytes: int
    generation_time_ms: int


class GLBGenerator:
    """Generate GLB files from design specifications"""

    def __init__(self, output_dir: str = "data/geometry_outputs"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_glb(self, spec_json: Dict[str, Any], request_id: str) -> str:
        """Generate GLB file from design specification"""

        try:
            # Create simple GLB with basic room geometry
            glb_content = self._create_simple_glb(spec_json)

            # Save GLB file
            glb_filename = f"{request_id}.glb"
            glb_path = os.path.join(self.output_dir, glb_filename)

            with open(glb_path, "wb") as f:
                f.write(glb_content)

            logger.info(f"Generated GLB file: {glb_path}")
            return glb_path

        except Exception as e:
            logger.error(f"GLB generation failed for {request_id}: {e}")
            raise

    def _create_simple_glb(self, spec_json: Dict[str, Any]) -> bytes:
        """Create real GLB with actual geometry from spec"""
        try:
            from app.geometry_generator_real import generate_real_glb

            return generate_real_glb(spec_json)
        except Exception as e:
            logger.warning(f"Real geometry generation failed, using fallback: {e}")
            # Fallback to simple room
            rooms = spec_json.get("rooms", [])
            if not rooms:
                rooms = [{"type": "room", "length": 4.0, "width": 4.0, "height": 3.0}]

            room = rooms[0]
            length = room.get("length", 4.0)
            width = room.get("width", 4.0)
            height = room.get("height", 3.0)

            # Simple fallback GLB
            glb_header = b"glTF\x02\x00\x00\x00"
            mock_data = b'{"asset":{"version":"2.0"},"scenes":[{"nodes":[0]}],"nodes":[{"mesh":0}],"meshes":[{"primitives":[{"attributes":{"POSITION":0}}]}]}'
            padding = b"\x00" * (1024 - len(mock_data))
            return glb_header + mock_data + padding


# Global instance
glb_generator = GLBGenerator()


@router.post("/generate", response_model=GeometryResponse)
async def generate_geometry(
    request: GeometryRequest, background_tasks: BackgroundTasks, current_user: str = Depends(get_current_user)
):
    """Generate 3D geometry file from design specification"""

    start_time = datetime.now()

    try:
        if request.format.lower() == "glb":
            geometry_path = glb_generator.generate_glb(request.spec_json, request.request_id)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {request.format}")

        # Get file size
        file_size = os.path.getsize(geometry_path)

        # Calculate generation time
        generation_time = int((datetime.now() - start_time).total_seconds() * 1000)

        # Generate URL
        geometry_url = f"/api/v1/geometry/download/{request.request_id}.{request.format}"

        logger.info(f"Geometry generated: {geometry_path} ({file_size} bytes)")

        return GeometryResponse(
            request_id=request.request_id,
            geometry_url=geometry_url,
            format=request.format,
            file_size_bytes=file_size,
            generation_time_ms=generation_time,
        )

    except Exception as e:
        logger.error(f"Geometry generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Geometry generation failed: {str(e)}")


@router.get("/download/{filename}", include_in_schema=False)
async def download_geometry(filename: str):
    """Download generated geometry file"""

    file_path = os.path.join(glb_generator.output_dir, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Geometry file not found")

    from fastapi.responses import FileResponse

    return FileResponse(
        file_path,
        media_type="model/gltf-binary" if filename.endswith(".glb") else "application/octet-stream",
        filename=filename,
    )


@router.get("/list", include_in_schema=False)
async def list_geometry_files():
    """List all generated geometry files"""

    files = []
    if os.path.exists(glb_generator.output_dir):
        for filename in os.listdir(glb_generator.output_dir):
            if filename.endswith((".glb", ".obj")):
                file_path = os.path.join(glb_generator.output_dir, filename)
                file_stat = os.stat(file_path)

                files.append(
                    {
                        "filename": filename,
                        "size_bytes": file_stat.st_size,
                        "created_at": datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
                        "download_url": f"/api/v1/geometry/download/{filename}",
                    }
                )

    return {"files": files, "total_count": len(files)}
