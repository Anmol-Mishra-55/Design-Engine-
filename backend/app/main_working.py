import logging
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
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
    logger.info("Server started successfully")


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
    response = await call_next(request)
    process_time = time.time() - start_time
    print(f"{request.method} {request.url.path} -> {response.status_code} ({process_time:.3f}s)")
    return response


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "Design Engine API", "version": "0.1.0"}


@app.get("/")
async def root():
    return {"message": "Design Engine API is running", "docs": "/docs"}


# Only include working routers
try:
    from app.api import auth

    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
    logger.info("Auth router loaded")
except Exception as e:
    logger.warning(f"Auth router failed: {e}")

try:
    from app.api import generate

    app.include_router(generate.router, prefix="/api/v1", tags=["Generate"])
    logger.info("Generate router loaded")
except Exception as e:
    logger.warning(f"Generate router failed: {e}")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
