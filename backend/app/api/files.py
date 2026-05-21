"""
File Download API — Phase 1 enforcement.

/api/v1/files/<bucket>/<file_id> now proxies from the live Bucket service.
GridFS is NOT used for geometry/spec artifacts.
If the Bucket lookup fails → 404. No local fallback.
"""
import logging

import httpx
from app.storage import _BUCKET_BASE, _INTEGRATION_ID, _READ_ENDPOINT, _REQUESTER_ID
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

router = APIRouter()
logger = logging.getLogger(__name__)

CONTENT_TYPES = {
    "glb": "model/gltf-binary",
    "stl": "model/stl",
    "step": "application/step",
    "json": "application/json",
    "png": "image/png",
}


@router.get("/files/{bucket}/{file_id}")
async def download_file_endpoint(bucket: str, file_id: str):
    """
    Proxy file download from the live Bucket service.
    artifact_id = file_id (UUID stored during upload).
    No GridFS, no local disk — Bucket only.
    """
    payload = {
        "requester_id": _REQUESTER_ID,
        "integration_id": _INTEGRATION_ID,
        "artifact_id": file_id,
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(_READ_ENDPOINT, json=payload)
            if r.status_code == 404:
                raise HTTPException(status_code=404, detail="File not found in Bucket")
            r.raise_for_status()
            result = r.json()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Bucket proxy download failed: %s", exc)
        raise HTTPException(status_code=502, detail="Bucket service unavailable")

    if not result.get("success"):
        raise HTTPException(status_code=404, detail="Artifact not found")

    import base64

    artifact = result.get("data", {}).get("artifact", {})
    payload_data = artifact.get("payload", {})
    data_b64 = payload_data.get("data_base64")
    if not data_b64:
        raise HTTPException(status_code=404, detail="Artifact has no data")

    file_data = base64.b64decode(data_b64)
    content_type = payload_data.get("content_type", "application/octet-stream")
    path = payload_data.get("path", file_id)
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    content_type = content_type or CONTENT_TYPES.get(ext, "application/octet-stream")
    filename = path.split("/")[-1] if "/" in path else path

    return Response(
        content=file_data,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(file_data)),
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )
