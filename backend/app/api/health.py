"""
Health API — Task 2 Production Hardening

/health/detailed now performs real dependency checks instead of returning
hardcoded mock values.  Each check is time-boxed so a slow dependency
cannot hang the endpoint.
"""
import logging
import time

import httpx
from app.config import settings
from app.database_mongodb import check_db_connection
from app.schemas import MessageResponse
from app.utils import get_uptime
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_fastapi_instrumentator import Instrumentator

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize Prometheus instrumentator
instrumentator = Instrumentator()

_HEALTH_TIMEOUT = 5.0  # seconds per external check


# ---------------------------------------------------------------------------
# Individual dependency checks
# ---------------------------------------------------------------------------


async def _check_redis() -> dict:
    """Ping Redis using a raw TCP connection via aioredis / redis-py async."""
    start = time.time()
    try:
        import redis.asyncio as aioredis  # type: ignore

        client = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=_HEALTH_TIMEOUT)
        await client.ping()
        await client.aclose()
        return {"status": "healthy", "latency_ms": round((time.time() - start) * 1000, 2)}
    except ImportError:
        return {"status": "not_configured", "note": "redis-py not installed"}
    except Exception as exc:
        return {
            "status": "unhealthy",
            "error": str(exc),
            "latency_ms": round((time.time() - start) * 1000, 2),
        }


async def _check_bucket() -> dict:
    """GET /health on the Bucket service."""
    start = time.time()
    url = settings.BUCKET_URL.rstrip("/") + "/health"
    try:
        async with httpx.AsyncClient(timeout=_HEALTH_TIMEOUT) as client:
            r = await client.get(url)
            r.raise_for_status()
        return {"status": "healthy", "latency_ms": round((time.time() - start) * 1000, 2)}
    except Exception as exc:
        return {
            "status": "unhealthy",
            "error": str(exc),
            "latency_ms": round((time.time() - start) * 1000, 2),
        }


async def _check_external_service(name: str, url: str) -> dict:
    """GET /health on an external service."""
    start = time.time()
    health_url = url.rstrip("/") + "/health"
    try:
        async with httpx.AsyncClient(timeout=_HEALTH_TIMEOUT) as client:
            r = await client.get(health_url)
            r.raise_for_status()
        return {"status": "healthy", "latency_ms": round((time.time() - start) * 1000, 2)}
    except Exception as exc:
        return {
            "status": "unhealthy",
            "error": str(exc),
            "latency_ms": round((time.time() - start) * 1000, 2),
        }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/", response_model=MessageResponse, name="Service Status")
async def service_status():
    return MessageResponse(message="Service is healthy")


@router.get("/health", name="Health Check")
async def health_check():
    return {
        "status": "healthy",
        "uptime": get_uptime(),
        "service": "Design Engine API",
        "version": "1.0.0",
    }


@router.get("/health/detailed", name="Detailed Health")
async def detailed_health():
    """
    Real dependency health checks.
    Each check is independently time-boxed at 5 s.
    Overall status is 'degraded' if any non-critical check fails,
    'unhealthy' if the database is unreachable.
    """
    import asyncio

    db_check, redis_check, bucket_check, sohum_check, ranjeet_check = await asyncio.gather(
        check_db_connection(),
        _check_redis(),
        _check_bucket(),
        _check_external_service("sohum_mcp", settings.SOHUM_MCP_URL),
        _check_external_service("ranjeet_rl", settings.RANJEET_RL_URL),
        return_exceptions=False,
    )

    db_healthy = db_check.get("status") == "healthy"
    all_healthy = db_healthy and all(
        c.get("status") in ("healthy", "not_configured")
        for c in (redis_check, bucket_check, sohum_check, ranjeet_check)
    )

    if not db_healthy:
        overall = "unhealthy"
    elif not all_healthy:
        overall = "degraded"
    else:
        overall = "healthy"

    return {
        "status": overall,
        "uptime": get_uptime(),
        "service": "Design Engine API",
        "version": "1.0.0",
        "components": {
            "database": db_check,
            "redis": redis_check,
            "bucket": bucket_check,
        },
        "external_services": {
            "sohum_mcp": sohum_check,
            "ranjeet_rl": ranjeet_check,
        },
    }


@router.get("/metrics", response_class=PlainTextResponse, name="Prometheus Metrics")
async def get_metrics():
    try:
        return instrumentator.registry.generate_latest().decode("utf-8")
    except Exception:
        uptime = get_uptime()
        return (
            f"# HELP app_uptime_seconds Application uptime in seconds\n"
            f"# TYPE app_uptime_seconds gauge\n"
            f"app_uptime_seconds {uptime}\n"
            f"# HELP app_info Application information\n"
            f"# TYPE app_info gauge\n"
            f'app_info{{version="1.0.0",service="design_engine_api"}} 1\n'
        )


@router.get("/test-error", name="Test Sentry Error")
async def test_sentry_error():
    """Test endpoint to verify Sentry error tracking"""
    import sentry_sdk

    try:
        1 / 0
    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.error("Test error captured: %s", e)
        return {
            "message": "Test error successfully sent to Sentry!",
            "error_type": "ZeroDivisionError",
            "sentry_status": "captured",
        }
