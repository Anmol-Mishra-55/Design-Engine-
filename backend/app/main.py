import os
import sys

# Fix Windows console encoding for Unicode characters
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import time

import sentry_sdk
from app.api import (
    auth,
    bhiv_assistant,
    bhiv_integrated,
    compliance,
    core_entry,
    data_audit,
    data_privacy,
    downloads,
    evaluate,
    files,
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
from app.config import settings
from app.database_mongodb import close_mongo_connection, connect_to_mongo
from app.multi_city.city_data_loader import city_router
from app.utils import setup_logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

setup_logging()
logger = logging.getLogger(__name__)

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
    logger.info("Sentry initialized")
else:
    logger.debug("Sentry not configured (optional)")

try:
    from app.gpu_detector import gpu_detector

    logger.info("GPU detector loaded")
except ImportError:
    logger.info("GPU detector not available")

if settings.YOTTA_API_KEY and settings.YOTTA_URL:
    logger.info(f"Yotta configured: {settings.YOTTA_URL}")
else:
    logger.debug("Yotta not configured (optional)")

security = HTTPBearer()
IS_DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

app = FastAPI(
    title="Design Engine API",
    description="Complete FastAPI backend for design generation with JWT authentication",
    version="0.1.0",
    docs_url="/docs" if not IS_DEMO_MODE else None,
    redoc_url="/redoc" if not IS_DEMO_MODE else None,
    openapi_url="/openapi.json" if not IS_DEMO_MODE else None,
)


@app.on_event("startup")
async def startup_event():
    print("\n" + "=" * 70)
    print("Design Engine API Server Starting...")
    print("Server URL: http://0.0.0.0:8000")
    print("API Docs: http://0.0.0.0:8000/docs")
    print("Health Check: http://0.0.0.0:8000/health")
    print("Database: MongoDB (attempting connection...)")
    print("Storage: MongoDB GridFS")
    print("Request logging is ENABLED")
    print("=" * 70 + "\n")

    # Try to connect to MongoDB (non-blocking)
    try:
        await connect_to_mongo(settings.MONGODB_URL, settings.MONGODB_DATABASE)
        logger.info("MongoDB connected successfully")
        logger.info(f"Database: {settings.MONGODB_DATABASE}")
        logger.info("GridFS Buckets: files, previews, geometry, compliance")
    except Exception as e:
        logger.warning(f"MongoDB connection failed: {e}")
        logger.warning("Server will start without database (some features disabled)")
        logger.warning("Fix MongoDB connection and restart for full functionality")


@app.on_event("shutdown")
async def shutdown_event():
    await close_mongo_connection()
    logger.info("MongoDB connection closed")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "HTTP_ERROR", "message": exc.detail, "status_code": exc.status_code}},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    import traceback

    error_details = traceback.format_exc()
    logger.error(f"Unhandled exception: {exc}\n{error_details}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": str(exc), "status_code": 500}},
    )


if settings.ENABLE_METRICS:
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics", "/docs", "/openapi.json"],
        env_var_name="ENABLE_METRICS",
    )
    instrumentator.instrument(app).expose(app, tags=["Metrics"])
    logger.info("Essential metrics enabled")
else:
    logger.info("Metrics disabled")

cors_origins = list(settings.CORS_ORIGINS or [])
if not cors_origins:
    cors_origins = ["http://localhost:3000", "http://localhost:3001"]
if "*" in cors_origins and settings.CORS_CREDENTIALS:
    logger.warning("CORS wildcard '*' removed because credentials are enabled")
    cors_origins = [origin for origin in cors_origins if origin != "*"]
    if not cors_origins:
        cors_origins = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=settings.CORS_CREDENTIALS,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
)


@app.middleware("http")
async def core_entry_guard(request: Request, call_next):
    """
    Phase 3 — Core Entry Enforcement.
    POST /api/v1/generate is only reachable with the correct X-Core-Token header.
    All other callers get 403 immediately, before the route handler runs.
    The token is injected automatically by /api/v1/core/generate (the public Core entry).
    """
    if request.method == "POST" and request.url.path == "/api/v1/generate":
        token = request.headers.get("X-Core-Token", "")
        if token != settings.CORE_INTERNAL_TOKEN:
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "CORE_BYPASS_BLOCKED",
                        "message": "Forbidden: direct access not allowed. All requests must go through /api/v1/core/generate.",
                        "status_code": 403,
                    }
                },
            )
    return await call_next(request)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    request_log = f"{request.method} {request.url.path} from {request.client.host if request.client else 'unknown'}"
    print(request_log)
    logger.info(request_log)

    response = await call_next(request)

    process_time = time.time() - start_time
    status_marker = "OK" if 200 <= response.status_code < 300 else "ERROR" if response.status_code >= 400 else "WARN"
    response_log = (
        f"{status_marker} {request.method} {request.url.path} -> {response.status_code} ({process_time:.3f}s)"
    )
    print(response_log)
    logger.info(response_log)

    return response


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


@app.get("/health", tags=["Public Health"])
async def basic_health_check():
    """Basic health check - no authentication required"""
    return {"status": "ok", "service": "Design Engine API", "version": "0.1.0"}


app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(files.router, prefix="/api/v1", tags=["File Download"])
app.include_router(downloads.router, tags=["File Downloads"])
app.include_router(health.router, prefix="/api/v1", tags=["System Health"], include_in_schema=False)
app.include_router(monitoring_system.router, include_in_schema=False)
app.include_router(data_privacy.router, prefix="/api/v1", tags=["Data Privacy"], include_in_schema=False)
app.include_router(data_audit.router, tags=["Data Audit"], include_in_schema=False)
app.include_router(generate.router, prefix="/api/v1", tags=["Design Generation"])
app.include_router(core_entry.router, prefix="/api/v1", tags=["Core Entry"])
app.include_router(evaluate.router, prefix="/api/v1", tags=["Design Evaluation"], include_in_schema=False)
app.include_router(iterate.router, prefix="/api/v1", tags=["Design Iteration"], include_in_schema=False)
app.include_router(switch.router, include_in_schema=False)
app.include_router(history.router, prefix="/api/v1", tags=["Design History"], include_in_schema=False)
app.include_router(compliance.router, prefix="/api/v1/compliance", tags=["Compliance & Validation"])
app.include_router(mcp_integration.router, include_in_schema=False)
app.include_router(city_router, prefix="/api/v1", tags=["Multi-City"], include_in_schema=False)
app.include_router(bhiv_assistant.router, include_in_schema=False)
app.include_router(bhiv_integrated.router, include_in_schema=False)
app.include_router(reports.router, prefix="/api/v1", tags=["File Management"], include_in_schema=False)
app.include_router(rl.router, prefix="/api/v1", tags=["RL Training"], include_in_schema=False)
app.include_router(mobile.router, prefix="/api/v1", tags=["Mobile API"], include_in_schema=False)
app.include_router(vr.router, prefix="/api/v1", tags=["VR API"], include_in_schema=False)
app.include_router(integration_layer.router, include_in_schema=False)
app.include_router(workflow_consolidation.router, include_in_schema=False)
app.include_router(multi_city_testing.router, include_in_schema=False)
app.include_router(geometry_generator.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
