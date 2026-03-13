import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import time

import sentry_sdk
from app.api import (
    auth,
    bhiv_assistant,
    bhiv_integrated,
    compliance,
    data_audit,
    data_privacy,
    evaluate,
    generate,
    geometry_generator,
    health,
    history,
    integration_layer,
    iterate,
    mcp_integration,
    mobile,
    monitoring_system,
    multi_city_testing,
    reports,
    rl,
    switch,
    vr,
    workflow_consolidation,
)
from app.auth_mongodb import get_current_user, get_db

# BHIV AI Assistant: Both bhiv_assistant.py and bhiv_integrated.py are included
# bhiv_assistant.py: Main orchestration layer (/bhiv/v1/prompt)
# bhiv_integrated.py: Integrated design endpoint (/bhiv/v1/design)
from app.config import settings
from app.multi_city.city_data_loader import city_router
from app.utils import setup_logging
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)

# Initialize Sentry
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(),
        ],
        traces_sample_rate=1.0,
        environment=settings.ENVIRONMENT,
        send_default_pii=True,
    )
    logger.info("Sentry initialized and connected")
else:
    logger.warning("Sentry not configured")

# Lazy GPU detection - only when needed
try:
    from app.gpu_detector import gpu_detector

    logger.info("GPU detector loaded (detection deferred)")
except ImportError:
    logger.info("GPU detector not available - using CPU mode")

# MongoDB GridFS connection - only when needed
try:
    from app.storage_mongodb import GridFSStorage

    logger.info(f"MongoDB GridFS storage loaded: {settings.MONGODB_URL}")
except Exception as e:
    logger.error(f"MongoDB GridFS storage loading failed: {e}")

# Check Yotta configuration
if settings.YOTTA_API_KEY and settings.YOTTA_URL:
    logger.info(f"Yotta configured: {settings.YOTTA_URL}")
else:
    logger.warning("Yotta not configured")

# Lazy initialization - validate on first use
try:
    from app.database_validator import validate_database
    from app.storage_manager import ensure_storage_ready

    logger.info("Storage and database modules loaded (validation deferred)")
except Exception as e:
    logger.error(f"Storage/Database module loading failed: {e}")

# JWT Security scheme
security = HTTPBearer()

# Demo/Production mode: Hide internal endpoints from OpenAPI
IS_DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

app = FastAPI(
    title="Design Engine API",
    description="Complete FastAPI backend for design generation with JWT authentication",
    version="0.1.0",
    # Disable docs in demo mode
    docs_url="/docs" if not IS_DEMO_MODE else None,
    redoc_url="/redoc" if not IS_DEMO_MODE else None,
    openapi_url="/openapi.json" if not IS_DEMO_MODE else None,
)


# Startup event to ensure logging is working
@app.on_event("startup")
async def startup_event():
    print("\n" + "=" * 70)
    print("Design Engine API Server Starting...")
    print("Server URL: http://0.0.0.0:8000")
    print("API Docs: http://0.0.0.0:8000/docs")
    print("Health Check: http://0.0.0.0:8000/health")
    print("Request logging is ENABLED")
    print("=" * 70 + "\n")
    logger.info("Design Engine API Server Started Successfully")


# Global exception handler for consistent error responses
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    print(f"HTTP {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "HTTP_ERROR", "message": exc.detail, "status_code": exc.status_code}},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    import traceback

    error_details = traceback.format_exc()
    logger.error(f"Unhandled exception: {exc}\n{error_details}", exc_info=True)
    print(f"EXCEPTION: {exc}\n{error_details}")
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": str(exc), "status_code": 500}},
    )


# Essential metrics only for BHIV automations
if settings.ENABLE_METRICS:
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics", "/docs", "/openapi.json"],
        env_var_name="ENABLE_METRICS",
    )
    instrumentator.instrument(app).expose(app, tags=["📊 Metrics"])
    logger.info("Essential metrics enabled")
else:
    logger.info("Metrics disabled")

# CORS middleware - TODO: Update with actual frontend origins
# Yash & Bhavesh: Provide your frontend URLs to replace ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React dev server
        "http://localhost:3001",  # Alternative dev port
        "https://staging.bhiv.com",  # Staging (update with actual)
        "https://app.bhiv.com",  # Production (update with actual)
        "*",  # Remove this in production
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Force-Update"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    # Log incoming request with print and logger
    request_log = f"{request.method} {request.url.path} from {request.client.host if request.client else 'unknown'}"
    print(request_log)
    logger.info(request_log)

    response = await call_next(request)

    # Log response with timing
    process_time = time.time() - start_time
    status_marker = "OK" if 200 <= response.status_code < 300 else "ERROR" if response.status_code >= 400 else "WARN"
    response_log = (
        f"{status_marker} {request.method} {request.url.path} -> {response.status_code} ({process_time:.3f}s)"
    )
    print(response_log)
    logger.info(response_log)

    return response


# ============================================================================
# STATIC FILE SERVING
# ============================================================================

# Mount static files for geometry previews
try:
    import os

    geometry_dir = os.path.join(os.path.dirname(__file__), "..", "data", "geometry_outputs")
    geometry_dir = os.path.abspath(geometry_dir)

    if os.path.exists(geometry_dir):
        app.mount("/static/geometry", StaticFiles(directory=geometry_dir), name="geometry")
        logger.info(f"Static geometry files mounted at /static/geometry -> {geometry_dir}")
    else:
        os.makedirs(geometry_dir, exist_ok=True)
        app.mount("/static/geometry", StaticFiles(directory=geometry_dir), name="geometry")
        logger.info(f"Created and mounted geometry directory: {geometry_dir}")

    export_dir = os.path.join(os.path.dirname(__file__), "..", "data", "export_outputs")
    export_dir = os.path.abspath(export_dir)
    if os.path.exists(export_dir):
        app.mount("/static/exports", StaticFiles(directory=export_dir), name="exports")
        logger.info(f"Static export files mounted at /static/exports -> {export_dir}")
    else:
        os.makedirs(export_dir, exist_ok=True)
        app.mount("/static/exports", StaticFiles(directory=export_dir), name="exports")
        logger.info(f"Created and mounted export directory: {export_dir}")
except Exception as e:
    logger.warning(f"Static files mount failed: {e}")

# ============================================================================
# PUBLIC ENDPOINTS (No Authentication Required)
# ============================================================================


# Basic public health check
@app.get("/health", tags=["📊 Public Health"])
async def basic_health_check():
    """Basic health check - no authentication required"""
    return {"status": "ok", "service": "Design Engine API", "version": "0.1.0"}


# Authentication endpoints (PUBLIC - visible in docs)
app.include_router(auth.router, prefix="/api/v1/auth", tags=["🔐 Authentication"])

# ============================================================================
# PROTECTED ENDPOINTS (JWT Authentication Required)
# ============================================================================

# 1. System Health & Monitoring (HIDDEN from docs)
app.include_router(
    health.router,
    prefix="/api/v1",
    tags=["📊 System Health"],
    dependencies=[Depends(get_current_user)],
    include_in_schema=False,
)
app.include_router(monitoring_system.router, dependencies=[Depends(get_current_user)], include_in_schema=False)

# 2. Data Privacy & Security (HIDDEN from docs)
app.include_router(
    data_privacy.router,
    prefix="/api/v1",
    tags=["🔐 Data Privacy"],
    dependencies=[Depends(get_current_user)],
    include_in_schema=False,
)

# 2.1 Data Audit & Integrity (HIDDEN from docs)
app.include_router(
    data_audit.router, tags=["🔍 Data Audit"], dependencies=[Depends(get_current_user)], include_in_schema=False
)

# 3. Core Design Engine (PUBLIC - visible in docs)
app.include_router(
    generate.router, prefix="/api/v1", tags=["🎨 Design Generation"], dependencies=[Depends(get_current_user)]
)
app.include_router(
    evaluate.router,
    prefix="/api/v1",
    tags=["📊 Design Evaluation"],
    dependencies=[Depends(get_current_user)],
    include_in_schema=False,
)
app.include_router(
    iterate.router,
    prefix="/api/v1",
    tags=["🔄 Design Iteration"],
    dependencies=[Depends(get_current_user)],
    include_in_schema=False,
)
app.include_router(switch.router, dependencies=[Depends(get_current_user)], include_in_schema=False)
app.include_router(
    history.router,
    prefix="/api/v1",
    tags=["📚 Design History"],
    dependencies=[Depends(get_current_user)],
    include_in_schema=False,
)


# Add explicit /history endpoint (HIDDEN from docs)
@app.get("/api/v1/history", tags=["📚 Design History"], include_in_schema=False)
async def get_design_history(current_user: str = Depends(get_current_user), limit: int = 20, project_id: str = None):
    """Get user's design history - explicit route"""
    from app.api.history import get_user_history

    return await get_user_history(current_user, db, limit, project_id)


# 4. Compliance & Validation (PUBLIC - visible in docs)
app.include_router(
    compliance.router,
    prefix="/api/v1/compliance",
    tags=["✅ Compliance & Validation"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(mcp_integration.router, dependencies=[Depends(get_current_user)], include_in_schema=False)

# 5. Multi-City Support (HIDDEN from docs)
app.include_router(
    city_router,
    prefix="/api/v1",
    tags=["🏙️ Multi-City"],
    dependencies=[Depends(get_current_user)],
    include_in_schema=False,
)

# Multi-city RL feedback endpoint (HIDDEN from docs)
from app.multi_city.rl_feedback_integration import multi_city_rl


@app.post("/api/v1/rl/feedback/city", tags=["🏙️ Multi-City"], include_in_schema=False)
async def city_rl_feedback(city: str, user_rating: float, request_body: dict, current_user=Depends(get_current_user)):
    """Submit city-specific RL feedback"""
    design_spec = request_body.get("design_spec", {})
    compliance_result = request_body.get("compliance_result", {})

    feedback_id = await multi_city_rl.collect_city_feedback(city, design_spec, user_rating, compliance_result)
    return {"feedback_id": feedback_id, "city": city, "status": "success"}


# 6. BHIV AI Assistant (HIDDEN from docs)
app.include_router(bhiv_assistant.router, dependencies=[Depends(get_current_user)], include_in_schema=False)
app.include_router(bhiv_integrated.router, dependencies=[Depends(get_current_user)], include_in_schema=False)

# 7. BHIV Automations & Workflows (HIDDEN from docs)
from app.api import workflow_management
from prefect_triggers import router as prefect_router

app.include_router(
    workflow_management.router,
    prefix="/api/v1",
    tags=["🤖 BHIV Automations"],
    dependencies=[Depends(get_current_user)],
    include_in_schema=False,
)
app.include_router(
    prefect_router,
    prefix="/api/v1/prefect",
    tags=["🚀 Event Triggers"],
    dependencies=[Depends(get_current_user)],
    include_in_schema=False,
)

# 8. File Management & Reports (HIDDEN from docs)
app.include_router(
    reports.router,
    prefix="/api/v1",
    tags=["📁 File Management"],
    dependencies=[Depends(get_current_user)],
    include_in_schema=False,
)


# Add explicit /reports/{spec_id} endpoint (HIDDEN from docs)
@app.get("/api/v1/reports/{spec_id}", tags=["📁 File Management"], include_in_schema=False)
async def get_spec_report(
    spec_id: str,
    current_user: str = Depends(get_current_user),
):
    """Get report for specific spec - explicit route"""
    from app.api.reports import get_report

    return await get_report(spec_id, current_user, db)


# 9. Machine Learning & Training (HIDDEN from docs)
app.include_router(
    rl.router,
    prefix="/api/v1",
    tags=["🤖 RL Training"],
    dependencies=[Depends(get_current_user)],
    include_in_schema=False,
)

# 9.1 Mobile & VR Endpoints (HIDDEN from docs)
app.include_router(
    mobile.router,
    prefix="/api/v1",
    tags=["📱 Mobile API"],
    dependencies=[Depends(get_current_user)],
    include_in_schema=False,
)
app.include_router(
    vr.router, prefix="/api/v1", tags=["🥽 VR API"], dependencies=[Depends(get_current_user)], include_in_schema=False
)

# 9.2 Integration Layer (HIDDEN from docs)
app.include_router(integration_layer.router, dependencies=[Depends(get_current_user)], include_in_schema=False)

# 9.3 Workflow Consolidation (HIDDEN from docs)
app.include_router(workflow_consolidation.router, dependencies=[Depends(get_current_user)], include_in_schema=False)

# 9.4 Multi-City Testing & Integration (HIDDEN from docs)
app.include_router(multi_city_testing.router, dependencies=[Depends(get_current_user)], include_in_schema=False)

# 10. 3D Geometry Generation (PUBLIC - visible in docs)
app.include_router(geometry_generator.router, dependencies=[Depends(get_current_user)])


# Note: /api/v1/rl/feedback/city/{city}/summary endpoint is handled by rl.router


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
