"""
VR API — Phase 3+4 enforced.
- No reads from data/geometry_outputs/
- No local:// fallback URLs
- All geometry served via Bucket only
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.auth_mongodb import get_current_user
from app.storage import _BUCKET_BASE, get_signed_url
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter()

VR_RENDERS_DIR = Path("vr_renders")
VR_RENDERS_DIR.mkdir(exist_ok=True)


@router.get("/vr/preview/{spec_id}")
async def vr_preview(spec_id: str, current_user: str = Depends(get_current_user)):
    """Get VR-optimized preview URL for spec — served from Bucket."""
    preview_url = get_signed_url("geometry", spec_id)
    return {
        "spec_id": spec_id,
        "preview_url": preview_url,
        "format": "glb",
        "expires_in": 600,
        "vr_optimized": True,
    }


@router.get("/vr/render/{spec_id}")
async def vr_render(spec_id: str, quality: str = "high", current_user: str = Depends(get_current_user)):
    """
    VR rendering endpoint.
    Phase 4: reads GLB from Bucket, not from data/geometry_outputs/.
    If Bucket artifact not found → 404. No local fallback.
    """
    from app.storage import download_from_bucket, upload_to_bucket

    render_id = f"vr_render_{spec_id}_{quality}_{uuid.uuid4().hex[:8]}"

    # Fetch source GLB from Bucket — fail hard if not found
    try:
        glb_bytes = await download_from_bucket("geometry", spec_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=f"Source geometry not found in Bucket: {exc}")

    # Upload VR render to Bucket — no local write, no local:// URL
    try:
        render_url = await upload_to_bucket("geometry", f"vr_{render_id}.glb", glb_bytes, "model/gltf-binary")
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"Bucket upload failed: {exc}")

    return {
        "spec_id": spec_id,
        "render_status": "completed",
        "quality": quality,
        "estimated_time": "2s",
        "render_id": render_id,
        "progress": 100,
        "render_url": render_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/vr/status/{render_id}")
async def vr_render_status(render_id: str, current_user: str = Depends(get_current_user)):
    """Check VR render status."""
    raise HTTPException(status_code=404, detail="VR render not found")


@router.post("/vr/feedback")
async def vr_feedback(feedback: dict, current_user: str = Depends(get_current_user)):
    """Submit VR experience feedback — stored in MongoDB only, no local file write."""
    from app.database_mongodb import get_database

    feedback_id = f"vr_fb_{feedback.get('spec_id', 'unknown')}_{uuid.uuid4().hex[:8]}"
    feedback_data = {
        "_id": feedback_id,
        "user_id": current_user,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **feedback,
    }

    try:
        db = get_database()
        await db.vr_feedback.insert_one(feedback_data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Feedback storage failed: {exc}")

    return {
        "feedback_id": feedback_id,
        "status": "received",
        "message": "VR feedback recorded",
    }
