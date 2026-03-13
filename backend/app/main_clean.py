import logging
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.database_mongodb import close_mongo_connection, connect_to_mongo, get_database
from app.utils import setup_logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Design Engine API",
    description="MongoDB-based FastAPI backend",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.on_event("startup")
async def startup_event():
    print("\n" + "=" * 70)
    print("Design Engine API Server Starting...")
    print("Server URL: http://0.0.0.0:8000")
    print("API Docs: http://0.0.0.0:8000/docs")
    print("Health Check: http://0.0.0.0:8000/health")
    print("=" * 70 + "\n")
    try:
        await connect_to_mongo(settings.MONGODB_URL, settings.MONGODB_DATABASE)
        logger.info("MongoDB connected successfully")
    except Exception as e:
        logger.warning(f"MongoDB connection failed: {e}")
        logger.info("Server will start without database connection")


@app.on_event("shutdown")
async def shutdown_event():
    try:
        await close_mongo_connection()
        logger.info("MongoDB connection closed")
    except Exception as e:
        logger.warning(f"Error closing MongoDB: {e}")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    request_log = f"{request.method} {request.url.path}"
    print(request_log)

    response = await call_next(request)

    process_time = time.time() - start_time
    status_marker = "OK" if 200 <= response.status_code < 300 else "ERROR" if response.status_code >= 400 else "WARN"
    response_log = (
        f"{status_marker} {request.method} {request.url.path} -> {response.status_code} ({process_time:.3f}s)"
    )
    print(response_log)

    return response


@app.get("/health")
async def basic_health_check():
    return {"status": "ok", "service": "Design Engine API", "version": "0.1.0"}


# Import and include only working routers
try:
    from app.api import auth

    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
    logger.info("Auth router loaded")
except Exception as e:
    logger.warning(f"Auth router failed: {e}")

try:
    from app.api import health

    app.include_router(health.router, prefix="/api/v1", tags=["Health"])
    logger.info("Health router loaded")
except Exception as e:
    logger.warning(f"Health router failed: {e}")

try:
    from app.api import generate

    app.include_router(generate.router, prefix="/api/v1", tags=["Generate"])
    logger.info("Generate router loaded")
except Exception as e:
    logger.warning(f"Generate router failed: {e}")

try:
    from app.api import compliance

    app.include_router(compliance.router, prefix="/api/v1/compliance", tags=["Compliance"])
    logger.info("Compliance router loaded")
except Exception as e:
    logger.warning(f"Compliance router failed: {e}")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
