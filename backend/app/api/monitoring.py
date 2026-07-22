"""
Monitoring and observability endpoints
"""

import logging
from datetime import datetime, timedelta, timezone

from app.auth_mongodb import get_current_user
from app.database_mongodb import get_database
from app.feedback_loop import IterativeFeedbackCycle
from fastapi import APIRouter, Depends

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/monitoring/overview")
async def monitoring_overview(current_user: str = Depends(get_current_user)):
    """Comprehensive monitoring dashboard"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    specs_24h: int = 0
    evals_24h: int = 0
    iters_24h: int = 0
    db_status = "unavailable"

    try:
        db = get_database()
        specs_24h = await db.specs.count_documents({"created_at": {"$gte": cutoff}})
        evals_24h = await db.evaluations.count_documents({"created_at": {"$gte": cutoff}})
        iters_24h = await db.iterations.count_documents({"created_at": {"$gte": cutoff}})
        db_status = "healthy"
    except Exception as exc:
        logger.warning("monitoring_overview: DB query failed: %s", exc)

    feedback_cycle = IterativeFeedbackCycle()
    cycle_status = feedback_cycle.get_cycle_status()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stats_24h": {
            "specs_generated": specs_24h,
            "evaluations_submitted": evals_24h,
            "iterations_created": iters_24h,
        },
        "feedback_loop": cycle_status,
        "system_health": {"database": db_status},
    }


@router.get("/monitoring/rate-limits")
async def rate_limit_status():
    """Get current rate limit stats"""
    from app.middleware.rate_limit import rate_limiter

    return {
        "requests_per_minute": rate_limiter.requests_per_minute,
        "active_clients": len(rate_limiter.clients),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/monitoring/feedback-loop")
async def feedback_loop_status():
    """Get detailed feedback loop status"""
    try:
        cycle = IterativeFeedbackCycle()
        status = cycle.get_cycle_status()
        return {
            "feedback_status": status,
            "endpoint": "/api/v1/monitoring/feedback-loop",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.error("Error getting feedback status: %s", exc)
        return {"error": "Could not retrieve feedback status", "timestamp": datetime.now(timezone.utc).isoformat()}
