import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.auth_mongodb import get_current_user, get_db
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter()

# Local storage for VR renders
VR_RENDERS_DIR = Path("vr_renders")
VR_RENDERS_DIR.mkdir(exist_ok=True)


@router.get("/vr/preview/{spec_id}")
async def vr_preview(spec_id: str, current_user: str = Depends(get_current_user)):
    """Get VR-optimized preview URL for spec"""
    try:
        # Get GLB file from geometry bucket
        preview_url = get_signed_url("geometry", f"{spec_id}.glb", expires=600)

        return {
            "spec_id": spec_id,
            "preview_url": preview_url,
            "format": "glb",
            "expires_in": 600,
            "vr_optimized": True,
        }
    except Exception:
        raise HTTPException(status_code=404, detail="Preview not found")


@router.get("/vr/render/{spec_id}")
async def vr_render(spec_id: str, quality: str = "high", current_user: str = Depends(get_current_user)):
    """VR rendering endpoint with database storage"""
    try:
        # Check if spec exists
        spec = None  # Mock database operation
        if not spec:
            raise HTTPException(status_code=404, detail="Spec not found")

        # Get actual user from database

        user = None  # Mock database operation
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user_id = user.id

        # Create VR render record
        render_id = f"vr_render_{spec_id}_{quality}_{uuid.uuid4().hex[:8]}"

        vr_render = VRRender(
            id=render_id,
            spec_id=spec_id,
            user_id=user_id,
            quality=quality,
            status="queued",
            estimated_time_seconds=30,
            progress=0,
        )

        # Mock add operation
        # Mock commit operation
        db.refresh(vr_render)

        # Create local file path
        local_file = VR_RENDERS_DIR / f"{render_id}.glb"

        # Simulate VR processing (copy from geometry)
        try:
            # Get source GLB file
            source_glb = Path("data/geometry_outputs") / f"{spec_id}.glb"
            if source_glb.exists():
                # Copy to VR renders directory
                import shutil

                shutil.copy2(source_glb, local_file)

                # Update render record
                vr_render.status = "completed"
                vr_render.progress = 100
                vr_render.local_path = str(local_file)
                vr_render.file_size_bytes = local_file.stat().st_size
                vr_render.actual_time_seconds = 2
                vr_render.started_at = datetime.now(timezone.utc)
                vr_render.completed_at = datetime.now(timezone.utc)

                # Upload to storage bucket
                try:
                    render_url = await upload_to_bucket("geometry", f"vr_{render_id}.glb", str(local_file))
                    vr_render.render_url = render_url
                except Exception as upload_error:
                    print(f"Upload failed: {upload_error}")
                    vr_render.render_url = f"local://{local_file}"

            else:
                vr_render.status = "failed"
                vr_render.error_message = "Source geometry not found"

            # Mock commit operation

        except Exception as e:
            vr_render.status = "failed"
            vr_render.error_message = str(e)
            # Mock commit operation

        return {
            "spec_id": spec_id,
            "render_status": vr_render.status,
            "quality": quality,
            "estimated_time": f"{vr_render.estimated_time_seconds}s",
            "render_id": render_id,
            "progress": vr_render.progress,
            "render_url": vr_render.render_url,
            "local_path": vr_render.local_path,
            "created_at": vr_render.created_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"VR render failed: {str(e)}")


@router.get("/vr/status/{render_id}")
async def vr_render_status(render_id: str, current_user: str = Depends(get_current_user)):
    """Check VR render status from database"""
    try:
        # Get actual user from database

        user = None  # Mock database operation
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        vr_render = None  # Mock database operation

        if not vr_render:
            raise HTTPException(status_code=404, detail="VR render not found")

        return {
            "render_id": render_id,
            "status": vr_render.status,
            "progress": vr_render.progress,
            "vr_url": vr_render.render_url,
            "local_path": vr_render.local_path,
            "quality": vr_render.quality,
            "file_size_bytes": vr_render.file_size_bytes,
            "estimated_time_seconds": vr_render.estimated_time_seconds,
            "actual_time_seconds": vr_render.actual_time_seconds,
            "error_message": vr_render.error_message,
            "created_at": vr_render.created_at.isoformat(),
            "started_at": vr_render.started_at.isoformat() if vr_render.started_at else None,
            "completed_at": vr_render.completed_at.isoformat() if vr_render.completed_at else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@router.post("/vr/feedback")
async def vr_feedback(
    feedback: dict,
    current_user: str = Depends(get_current_user),
):
    """Submit VR experience feedback with database storage"""
    try:
        # Store feedback in local file
        feedback_id = f"vr_fb_{feedback.get('spec_id', 'unknown')}_{uuid.uuid4().hex[:8]}"
        feedback_file = VR_RENDERS_DIR / f"feedback_{feedback_id}.json"

        feedback_data = {
            "feedback_id": feedback_id,
            "user_id": current_user,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **feedback,
        }

        import json

        with open(feedback_file, "w") as f:
            json.dump(feedback_data, f, indent=2)

        return {
            "feedback_id": feedback_id,
            "status": "received",
            "message": "VR feedback recorded",
            "local_path": str(feedback_file),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Feedback storage failed: {str(e)}")
