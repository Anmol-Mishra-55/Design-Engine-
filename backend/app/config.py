"""
MongoDB Configuration - Complete Application Configuration
Manages all environment variables, validation, and settings
"""
import os
from typing import List, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings for MongoDB backend"""

    # ============================================================================
    # APPLICATION SETTINGS
    # ============================================================================
    APP_NAME: str = "Design Engine API Backend"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    ENVIRONMENT: str = Field(default="development", description="Environment: development|staging|production")

    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=8000, description="Server port")
    RELOAD: bool = Field(default=False, description="Auto-reload on code changes")

    # Public base URL used to construct download links returned to clients.
    # Override with the deployed service URL in production (e.g. https://bhiv-backend.onrender.com).
    PUBLIC_API_URL: str = Field(
        default="http://localhost:8000",
        description="Public base URL of this API service (used in download_urls)",
    )

    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:3001"], description="Allowed CORS origins"
    )
    CORS_CREDENTIALS: bool = True
    CORS_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
    CORS_HEADERS: List[str] = ["*"]

    # ============================================================================
    # MONGODB CONFIGURATION (PRIMARY DATABASE & STORAGE)
    # ============================================================================
    MONGODB_URL: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB connection string",
    )
    MONGODB_DATABASE: str = Field(default="bhiv_db", description="MongoDB database name")
    DB_POOL_SIZE: int = Field(default=50, description="Connection pool size")
    DB_MAX_POOL_SIZE: int = Field(default=100, description="Max pool size")
    DB_POOL_TIMEOUT: int = Field(default=30, description="Pool timeout in seconds")

    @validator("MONGODB_URL")
    def validate_mongodb_url(cls, v):
        """Ensure MongoDB URL is properly formatted"""
        if not v.startswith(("mongodb://", "mongodb+srv://")):
            raise ValueError("MONGODB_URL must start with mongodb:// or mongodb+srv://")
        return v

    @validator("DEBUG", pre=True)
    def normalize_debug_flag(cls, v):
        """Normalize non-boolean DEBUG values"""
        if isinstance(v, str):
            lowered = v.strip().lower()
            if lowered in {"release", "prod", "production", "0", "false", "no", "warn", "warning"}:
                return False
            if lowered in {"debug", "dev", "development", "1", "true", "yes"}:
                return True
        return bool(v) if v is not None else False

    # ============================================================================
    # MONGODB GRIDFS STORAGE CONFIGURATION
    # ============================================================================
    GRIDFS_BUCKET_FILES: str = Field(default="files", description="User uploaded files bucket")
    GRIDFS_BUCKET_PREVIEWS: str = Field(default="previews", description="Generated previews bucket")
    GRIDFS_BUCKET_GEOMETRY: str = Field(default="geometry", description=".GLB geometry files bucket")
    GRIDFS_BUCKET_COMPLIANCE: str = Field(default="compliance", description="Compliance documents bucket")

    MAX_FILE_SIZE: int = Field(default=100 * 1024 * 1024, description="Max file size in bytes (100MB)")
    STORAGE_CHUNK_SIZE: int = Field(default=255 * 1024, description="GridFS chunk size in bytes")

    # ============================================================================
    # JWT AUTHENTICATION
    # ============================================================================
    JWT_SECRET_KEY: str = Field(
        default="change-me-jwt-secret",
        min_length=16,
        description="JWT secret key",
    )
    JWT_SECRET: str = Field(
        default="change-me-jwt-secret",
        min_length=16,
        description="JWT secret key (alias)",
    )
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    JWT_EXPIRATION_HOURS: int = Field(default=24, description="JWT token lifetime in hours")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=1440, description="Access token lifetime (24h)")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=30, description="Refresh token lifetime")

    @validator("JWT_SECRET_KEY")
    def validate_jwt_secret(cls, v):
        """Ensure JWT secret is strong enough"""
        if len(v) < 16:
            raise ValueError("JWT_SECRET_KEY must be at least 16 characters long")
        return v

    @validator("JWT_SECRET")
    def validate_jwt_secret_alias(cls, v):
        """Ensure JWT secret alias is strong enough"""
        if len(v) < 16:
            raise ValueError("JWT_SECRET must be at least 16 characters long")
        return v

    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        """Allow comma-separated CORS origins via env vars."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # ============================================================================
    # EXTERNAL SERVICES
    # ============================================================================
    SOHUM_MCP_URL: str = Field(default="https://ai-rule-api-w7z5.onrender.com", description="Sohum MCP service URL")
    SOHAM_URL: str = Field(default="https://ai-rule-api-w7z5.onrender.com", description="Legacy Soham URL alias")
    SOHUM_API_KEY: Optional[str] = Field(default=None, description="Sohum API key (if required)")
    COMPLIANCE_API_KEY: Optional[str] = Field(default=None, description="Compliance API key")
    SOHUM_TIMEOUT: int = Field(default=180, description="Timeout for MCP calls in seconds")
    SOHUM_MCP_ENABLED: bool = Field(default=True, description="Enable external MCP service")

    RANJEET_RL_URL: str = Field(
        default="https://land-utilization-rl.onrender.com", description="Ranjeet RL service URL (LIVE)"
    )
    RANJEET_API_KEY: Optional[str] = Field(default=None, description="Ranjeet API key (if required)")
    RANJEET_TIMEOUT: int = Field(default=180, description="Timeout for RL calls in seconds")

    LAND_UTILIZATION_ENABLED: bool = Field(default=True, description="Enable land utilization RL features")
    RANJEET_SERVICE_AVAILABLE: bool = Field(default=True, description="Ranjeet's service availability status")

    # ============================================================================
    # LM (LANGUAGE MODEL) CONFIGURATION
    # ============================================================================
    LM_PROVIDER: str = Field(default="local", description="LM provider: local|yotta|openai")

    LOCAL_GPU_ENABLED: bool = Field(default=True, description="Enable local GPU inference")
    LOCAL_GPU_DEVICE: str = Field(default="cuda:0", description="CUDA device ID")
    LOCAL_MODEL_PATH: str = Field(default="./models/local_model", description="Local model path")
    LOCAL_GPU_MODEL: str = Field(default="gpt2", description="Local model name")
    LOCAL_GPU_MAX_LENGTH: int = Field(default=2048, description="Max generation length")
    PROMPT_LENGTH_THRESHOLD: int = Field(default=100, description="Switch to cloud above this")

    YOTTA_API_KEY: Optional[str] = Field(default=None, description="Yotta API key")
    YOTTA_API_KEY_RL: Optional[str] = Field(default=None, description="Yotta RL API key")
    YOTTA_BASE_URL: Optional[str] = Field(default=None, description="Yotta base URL")
    YOTTA_URL: Optional[str] = Field(
        default="https://api.yotta.ai/v1/inference", description="Yotta inference endpoint"
    )
    YOTTA_MODEL: str = Field(default="llama-2-7b", description="Yotta model name")

    OPENAI_API_KEY: Optional[str] = Field(default=None, description="OpenAI API key")
    GROQ_API_KEY: Optional[str] = Field(default=None, description="Groq API key")
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, description="Anthropic Claude API key")
    TRIPO_API_KEY: Optional[str] = Field(default=None, description="Tripo AI API key for 3D model generation")
    MESHY_API_KEY: Optional[str] = Field(default=None, description="Meshy AI API key for 3D model generation")
    HUGGINGFACE_API_KEY: Optional[str] = Field(default=None, description="Hugging Face API token for 3D generation")

    USE_AI_MODEL: bool = Field(default=True, description="Use real AI models instead of templates")

    MAX_PROMPT_LENGTH: int = Field(default=2048, description="Maximum prompt length")
    DEFAULT_TEMPERATURE: float = Field(default=0.7, description="Default LM temperature")
    DEFAULT_TOP_P: float = Field(default=0.9, description="Default nucleus sampling")

    DEVICE_PREFERENCE: str = Field(default="auto", description="Device preference: local|yotta|auto")

    # ============================================================================
    # MONITORING & LOGGING
    # ============================================================================
    SENTRY_DSN: Optional[str] = Field(
        default=None,
        description="Sentry DSN for error tracking",
    )
    SENTRY_ENVIRONMENT: str = Field(default="development", description="Sentry environment tag")
    SENTRY_TRACES_SAMPLE_RATE: float = Field(default=0.1, description="Percentage of traces to send")

    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FILE: str = Field(default="logs/bhiv.log", description="Log file path")
    LOG_ROTATION: str = Field(default="1 day", description="Log rotation period")
    LOG_RETENTION: str = Field(default="30 days", description="Log retention period")

    METRICS_ENABLED: bool = Field(default=True, description="Enable Prometheus metrics")
    ENABLE_METRICS: bool = Field(default=True, description="Enable metrics (alias)")

    # ============================================================================
    # PREFECT WORKFLOW ORCHESTRATION
    # ============================================================================
    PREFECT_API_KEY: Optional[str] = Field(default=None, description="Prefect Cloud API key")
    PREFECT_API_URL: str = Field(default="https://api.prefect.cloud/api/accounts/", description="Prefect API base URL")
    PREFECT_WORKSPACE: Optional[str] = Field(default=None, description="Prefect workspace ID")
    PREFECT_QUEUE: str = Field(default="default", description="Default work queue")
    PREFECT_WEBHOOK_URL: Optional[str] = Field(default=None, description="Prefect webhook URL for notifications")

    # ============================================================================
    # REDIS CONFIGURATION
    # ============================================================================
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    REDIS_MAX_CONNECTIONS: int = Field(default=50, description="Max Redis connections")
    CACHE_TTL: int = Field(default=3600, description="Default cache TTL in seconds")

    # ============================================================================
    # RATE LIMITING
    # ============================================================================
    RATE_LIMIT_ENABLED: bool = Field(default=True, description="Enable rate limiting")
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, description="Requests per minute per user")
    RATE_LIMIT_PER_HOUR: int = Field(default=1000, description="Requests per hour per user")

    # ============================================================================
    # FILE UPLOAD CONFIGURATION
    # ============================================================================
    MAX_UPLOAD_SIZE: int = Field(default=10 * 1024 * 1024, description="Max upload size in bytes (10MB)")
    ALLOWED_EXTENSIONS: List[str] = Field(
        default=[".pdf", ".png", ".jpg", ".jpeg", ".glb", ".obj", ".fbx"], description="Allowed file extensions"
    )
    UPLOAD_DIRECTORY: str = Field(default="uploads/", description="Temporary upload directory")

    # ============================================================================
    # MULTI-CITY CONFIGURATION
    # ============================================================================
    SUPPORTED_CITIES: List[str] = Field(
        default=["Mumbai", "Pune", "Ahmedabad", "Nashik", "Bangalore"], description="Supported cities for compliance"
    )
    DEFAULT_CITY: str = Field(default="Mumbai", description="Default city if not specified")

    # ============================================================================
    # RL (REINFORCEMENT LEARNING) CONFIGURATION
    # ============================================================================
    RL_ENABLED: bool = Field(default=True, description="Enable RL features")
    RL_FEEDBACK_THRESHOLD: int = Field(default=10, description="Min feedback pairs before training")
    RL_TRAINING_BATCH_SIZE: int = Field(default=32, description="RL training batch size")
    RL_LEARNING_RATE: float = Field(default=0.001, description="RL learning rate")

    # ============================================================================
    # BUCKET STORAGE SERVICE
    # ============================================================================
    BUCKET_URL: str = Field(
        default="https://bhiv-bucket.onrender.com",
        description="Live Bucket storage service URL (Siddhesh)",
    )

    # ============================================================================
    # CORE INTERNAL TOKEN — blocks direct /generate calls
    # ============================================================================
    CORE_INTERNAL_TOKEN: str = Field(
        default="bhiv-core-internal-token-change-in-prod",
        description="Secret token that Core injects; /generate rejects requests without it",
    )

    # ============================================================================
    # SECURITY CONFIGURATION
    # ============================================================================
    ENCRYPTION_KEY: Optional[str] = Field(default=None, description="Encryption key material")

    # ============================================================================
    # DEMO CONFIGURATION
    # ============================================================================
    DEMO_MODE: bool = Field(default=False, description="Enable demo-only fallback authentication")
    DEMO_USERNAME: str = Field(default="admin", description="Demo username")
    DEMO_PASSWORD: Optional[str] = Field(default=None, description="Demo password")

    class Config:
        """Pydantic configuration"""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "allow"


settings = Settings()

# Keep legacy alias aligned with primary secret.
if not settings.JWT_SECRET or settings.JWT_SECRET == "change-me-jwt-secret":
    settings.JWT_SECRET = settings.JWT_SECRET_KEY


def validate_settings():
    """Validate all critical settings on application startup"""
    errors = []
    warnings = []

    if not settings.MONGODB_URL:
        errors.append("MONGODB_URL is required")

    if not settings.MONGODB_DATABASE:
        errors.append("MONGODB_DATABASE is required")

    if not settings.JWT_SECRET_KEY or len(settings.JWT_SECRET_KEY) < 16:
        errors.append("JWT_SECRET_KEY must be at least 16 characters long")

    if settings.ENCRYPTION_KEY and len(settings.ENCRYPTION_KEY) < 16:
        warnings.append("ENCRYPTION_KEY should be at least 16 characters")

    if settings.DEMO_MODE and not settings.DEMO_PASSWORD:
        errors.append("DEMO_PASSWORD must be set when DEMO_MODE=true")

    if settings.ENVIRONMENT == "production":
        insecure_jwt_defaults = {"change-me-jwt-secret", "bhiv-jwt-secret-2024-super-secure-key-for-production"}
        if settings.JWT_SECRET_KEY in insecure_jwt_defaults:
            errors.append("JWT_SECRET_KEY must be overridden in production")
        if settings.MONGODB_URL.startswith("mongodb://localhost"):
            errors.append("MONGODB_URL must be overridden in production")
        if settings.PUBLIC_API_URL == "http://localhost:8000":
            warnings.append("PUBLIC_API_URL is still localhost — set to the deployed service URL")
        if settings.DEMO_MODE:
            warnings.append("DEMO_MODE is enabled in production")

    # Only warn about missing API keys if explicitly set as provider
    # Silently skip optional services in development
    if settings.ENVIRONMENT == "production":
        if settings.LM_PROVIDER == "yotta" and not settings.YOTTA_API_KEY:
            warnings.append("Yotta API key missing but provider is set to yotta")

        if settings.LM_PROVIDER == "openai" and not settings.OPENAI_API_KEY:
            warnings.append("OpenAI API key missing but provider is set to openai")

        if not settings.SENTRY_DSN:
            warnings.append("Sentry DSN not configured - error tracking disabled")

    if warnings:
        import logging

        logger = logging.getLogger(__name__)
        for warning in warnings:
            logger.warning(f"Configuration warning: {warning}")

    if errors:
        raise ValueError(f"Configuration errors: {'; '.join(errors)}")

    return True


def get_mongodb_config() -> dict:
    """Get MongoDB configuration"""
    return {"url": settings.MONGODB_URL, "database": settings.MONGODB_DATABASE}


def get_lm_config() -> dict:
    """Get language model configuration based on provider"""
    config = {
        "provider": settings.LM_PROVIDER,
        "temperature": settings.DEFAULT_TEMPERATURE,
        "top_p": settings.DEFAULT_TOP_P,
        "max_length": settings.MAX_PROMPT_LENGTH,
    }

    if settings.LM_PROVIDER == "local":
        config.update(
            {
                "device": settings.LOCAL_GPU_DEVICE,
                "model_path": settings.LOCAL_MODEL_PATH,
                "model_name": settings.LOCAL_GPU_MODEL,
            }
        )
    elif settings.LM_PROVIDER == "yotta":
        config.update(
            {"api_key": settings.YOTTA_API_KEY, "base_url": settings.YOTTA_URL, "model": settings.YOTTA_MODEL}
        )
    elif settings.LM_PROVIDER == "openai":
        config.update({"api_key": settings.OPENAI_API_KEY})

    return config


def is_development() -> bool:
    """Check if running in development mode"""
    return settings.ENVIRONMENT == "development"


def is_production() -> bool:
    """Check if running in production mode"""
    return settings.ENVIRONMENT == "production"


if __name__ != "__main__" and not os.getenv("PYTEST_CURRENT_TEST"):
    try:
        validate_settings()
    except ValueError as e:
        if settings.ENVIRONMENT == "production":
            raise
        print(f"Configuration Error: {e}")
        print("Some features may not work correctly. Check your .env file.")
    except Exception as e:
        print(f"Configuration Warning: {e}")
        print("Configuration loaded with warnings.")


__all__ = ["settings", "validate_settings", "Settings"]
