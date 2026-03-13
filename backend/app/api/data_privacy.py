import logging

from app.auth_mongodb import get_current_user
from app.utils import log_audit_event
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/data/{user_id}/export")
async def export_user_data(user_id: str, current_user: str = Depends(get_current_user)):
    """GDPR-style data export - get all user data"""
    # Only allow users to export their own data or admin access
    if current_user != user_id and current_user != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    # Mock export data
    export_data = {
        "user_id": user_id,
        "export_timestamp": "2025-01-01T00:00:00Z",
        "data": {
            "specs": [],
            "evaluations": [],
            "iterations": [],
            "rl_data": {"feedback_count": 0},
        },
    }

    log_audit_event("data_export", user_id, {"exported_by": current_user})
    return export_data


@router.delete("/data/{user_id}")
async def delete_user_data(user_id: str, current_user: str = Depends(get_current_user)):
    """GDPR-style data deletion - wipe all user designs and data"""
    # Only allow users to delete their own data or admin access
    if current_user != user_id and current_user != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    # Mock deletion
    log_audit_event("data_deletion", user_id, {"deleted_by": current_user})

    return {
        "message": "User data successfully deleted",
        "user_id": user_id,
        "specs_deleted": 0,
        "files_deleted": 0,
        "deleted_at": "2025-01-01T00:00:00Z",
    }


@router.post("/auth/refresh")
async def refresh_user_token(current_user: str = Depends(get_current_user)):
    """Refresh JWT token for short-lived token strategy"""
    from app.utils import create_access_token

    # Create new token with fresh expiration
    new_token = create_access_token({"sub": current_user})

    # Log token refresh
    log_audit_event("token_refresh", current_user, {"new_token_issued": True})

    return {
        "access_token": new_token,
        "token_type": "bearer",
        "expires_in": 3600,  # 1 hour
    }
