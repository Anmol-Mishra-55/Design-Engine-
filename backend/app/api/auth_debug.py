#!/usr/bin/env python3
"""
Debug auth endpoint - logs all received data
"""
import logging
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.database_mongodb import get_database
from app.utils import verify_password
from fastapi import APIRouter, Depends, HTTPException, Request
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
    logger.info(f"[AUTH] Attempting authentication for user: {username}")
    logger.info(f"[AUTH] Password length: {len(password)}")
    logger.info(f"[AUTH] Password (first 4 chars): {password[:4]}****")

    try:
        db = get_database()
        logger.info(f"[AUTH] Database connection obtained")
    except Exception as e:
        logger.error(f"[AUTH] Failed to get database: {e}")
        raise

    try:
        user = await db.users.find_one({"$or": [{"username": username}, {"email": username}], "is_active": True})
        logger.info(f"[AUTH] User query completed. Found: {user is not None}")
    except Exception as e:
        logger.error(f"[AUTH] Failed to query user: {e}")
        raise

    if not user:
        logger.warning(f"[AUTH] User not found: {username}")
        return None

    password_hash = user.get("password_hash") or user.get("hashed_password")
    if not password_hash:
        logger.warning(f"[AUTH] No password hash for user: {username}")
        return None

    try:
        is_valid = verify_password(password, password_hash)
        logger.info(f"[AUTH] Password verification result: {is_valid}")
        if not is_valid:
            logger.warning(f"[AUTH] Invalid password for user: {username}")
            return None
    except Exception as e:
        logger.error(f"[AUTH] Password verification exception: {e}")
        return None

    subject = str(user.get("_id") or user.get("username"))
    logger.info(f"[AUTH] Authentication successful for: {username}, subject: {subject}")
    return subject


@router.post("/login")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    # Log all form data
    logger.info(f"[LOGIN] ===== LOGIN REQUEST =====")
    logger.info(f"[LOGIN] form_data.username: '{form_data.username}'")
    logger.info(f"[LOGIN] form_data.password length: {len(form_data.password)}")
    logger.info(f"[LOGIN] form_data.password (first 4): {form_data.password[:4]}****")
    logger.info(f"[LOGIN] form_data.grant_type: {form_data.grant_type}")
    logger.info(f"[LOGIN] form_data.scopes: {form_data.scopes}")
    logger.info(f"[LOGIN] form_data.client_id: {form_data.client_id}")
    logger.info(f"[LOGIN] form_data.client_secret: {'***' if form_data.client_secret else 'None'}")

    # Also log raw request body
    try:
        body = await request.body()
        logger.info(f"[LOGIN] Raw body: {body.decode('utf-8')}")
    except:
        pass

    logger.info(f"[LOGIN] ===========================")

    username = form_data.username.strip()
    password = form_data.password

    if not username or not password:
        logger.warning("[LOGIN] Missing username or password")
        raise HTTPException(status_code=400, detail="Username and password are required")

    # Optional demo fallback for local/manual demo environments only.
    if settings.DEMO_MODE and settings.DEMO_PASSWORD:
        logger.info(f"[LOGIN] Demo mode enabled, checking demo credentials")
        if username == settings.DEMO_USERNAME and password == settings.DEMO_PASSWORD:
            logger.info(f"[LOGIN] Demo authentication successful")
            token = _issue_access_token(settings.DEMO_USERNAME)
            return {"access_token": token, "token_type": "bearer"}

    try:
        logger.info(f"[LOGIN] Calling _authenticate_against_mongodb")
        subject = await _authenticate_against_mongodb(username, password)
        logger.info(f"[LOGIN] Authentication result: {subject}")
    except RuntimeError as e:
        logger.error(f"[LOGIN] RuntimeError during authentication: {e}")
        raise HTTPException(status_code=503, detail="Authentication service unavailable")
    except Exception as exc:
        logger.error(f"[LOGIN] Exception during authentication: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Authentication failed")

    if not subject:
        logger.warning(f"[LOGIN] Authentication failed for user: {username}")
        raise HTTPException(status_code=401, detail="Invalid username or password")

    logger.info(f"[LOGIN] Issuing token for subject: {subject}")
    token = _issue_access_token(subject)
    logger.info(f"[LOGIN] Login successful for user: {username}")
    return {"access_token": token, "token_type": "bearer"}


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
