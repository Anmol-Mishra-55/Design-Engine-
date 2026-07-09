"""
Replay API — Task 2 Production Hardening

Endpoints:
  GET  /api/v1/replay/                     — list replayable spec_ids
  GET  /api/v1/replay/{spec_id}/trace      — return stored trace summary
  POST /api/v1/replay/{spec_id}            — re-execute the pipeline
"""
import logging

from app.auth_mongodb import get_current_user
from app.replay.replay_service import ReplayService
from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/replay/", tags=["Replay"])
async def list_replayable(current_user: str = Depends(get_current_user)):
    """List all spec_ids that have both a trace file and a spec file stored."""
    spec_ids = ReplayService.list_replayable_specs()
    return {"replayable_specs": spec_ids, "count": len(spec_ids)}


@router.get("/replay/{spec_id}/trace", tags=["Replay"])
async def get_trace_summary(spec_id: str, current_user: str = Depends(get_current_user)):
    """Return the stored trace summary for a spec_id without re-executing."""
    summary = ReplayService.get_trace_summary(spec_id)
    if "error" in summary:
        raise HTTPException(status_code=404, detail=summary["error"])
    return summary


@router.post("/replay/{spec_id}", tags=["Replay"])
async def replay_spec(spec_id: str, current_user: str = Depends(get_current_user)):
    """
    Re-execute the pipeline for a previously stored spec_id.

    Returns a ReplayResult with the new replay_spec_id, replay_trace_id,
    and artifact URLs.  The original spec and trace are not modified.
    """
    logger.info("Replay requested: spec_id=%s by user=%s", spec_id, current_user)
    result = await ReplayService.replay(spec_id)
    if result.status == "failed":
        raise HTTPException(status_code=422, detail=result.to_dict())
    return result.to_dict()
