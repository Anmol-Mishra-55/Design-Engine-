import logging
import time
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.logging_config import setup_logging as _setup_logging  # noqa: F401 — re-exported
from jose import JWTError, jwt
from passlib.context import CryptContext

# Application start time for uptime calculation
START_TIME = time.time()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# JWT utilities
def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


# Logging setup — delegates to logging_config for JSON + file output
def setup_logging():
    _setup_logging()


# Spec utilities
def create_new_spec_id() -> str:
    """Generate unique spec ID"""
    import uuid

    return f"spec_{uuid.uuid4().hex[:8]}"


def generate_glb_from_spec(spec_json: dict) -> bytes:
    """Generate GLB preview from spec JSON (placeholder)"""
    glb_content = f"GLB_PREVIEW_{spec_json.get('components', ['default'])[0]}"
    return glb_content.encode("utf-8")


def create_eval_id() -> str:
    """Generate unique evaluation ID"""
    import uuid

    return f"eval_{uuid.uuid4().hex[:8]}"


def create_new_eval_id() -> str:
    """Generate unique evaluation ID (alias)"""
    return create_eval_id()


def create_iter_id() -> str:
    """Generate unique iteration ID"""
    import uuid

    return f"iter_{uuid.uuid4().hex[:8]}"


def spec_json_to_prompt(spec_json: dict) -> str:
    """Convert spec JSON to prompt for LM iteration"""
    components = spec_json.get("components", [])
    features = spec_json.get("features", [])
    tech_stack = spec_json.get("tech_stack", [])

    prompt = "Improve this design specification:\n"
    prompt += f"Components: {', '.join(components)}\n"
    prompt += f"Features: {', '.join(features)}\n"
    prompt += f"Tech Stack: {', '.join(tech_stack)}\n"
    prompt += "Generate an improved version with better materials, performance, or design."

    return prompt


def get_uptime() -> float:
    """Get application uptime in seconds"""
    return time.time() - START_TIME


def log_audit_event(event: str, user_id: str, details: dict = None):
    """Log audit events for compliance and tracking"""
    logger = logging.getLogger("audit")
    audit_data = {
        "event": event,
        "user_id": user_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": details or {},
    }
    logger.info(f"AUDIT: {audit_data}")
