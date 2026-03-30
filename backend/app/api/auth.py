import logging
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.database_mongodb import get_database
from app.utils import verify_password
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt

router = APIRouter()
logger = logging.getLogger(__name__)
security = HTTPBearer()


def _issue_access_token(subject: str) -> str:
    token_data = {
        "sub": subject,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRATION_HOURS),
    }
    return jwt.encode(token_data, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


async def _authenticate_against_mongodb(username: str, password: str) -> str | None:
    try:
        db = get_database()
    except Exception as e:
        logger.error(f"[AUTH] Failed to get database: {e}")
        raise

    user = await db.users.find_one({"$or": [{"username": username}, {"email": username}], "is_active": True})
    if not user:
        return None

    password_hash = user.get("password_hash") or user.get("hashed_password")
    if not password_hash:
        return None

    try:
        if not verify_password(password, password_hash):
            return None
    except Exception as e:
        logger.error(f"[AUTH] Password verification error: {e}")
        return None

    return str(user.get("_id") or user.get("username"))


@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    username = form_data.username.strip()
    password = form_data.password

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    if settings.DEMO_MODE and settings.DEMO_PASSWORD:
        if username == settings.DEMO_USERNAME and password == settings.DEMO_PASSWORD:
            token = _issue_access_token(settings.DEMO_USERNAME)
            return {"access_token": token, "token_type": "bearer"}

    try:
        subject = await _authenticate_against_mongodb(username, password)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Authentication service unavailable")
    except Exception as exc:
        logger.error(f"Login error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Authentication failed")

    if not subject:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    logger.info(f"Login successful: {username}")
    return {"access_token": _issue_access_token(subject), "token_type": "bearer"}


@router.post("/refresh", include_in_schema=False)
async def refresh_token(token: HTTPAuthorizationCredentials = Depends(security)):
    """Refresh JWT token - requires valid existing token."""
    try:
        payload = jwt.decode(token.credentials, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        new_token = _issue_access_token(str(username))
        return {"access_token": new_token, "token_type": "bearer"}

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
