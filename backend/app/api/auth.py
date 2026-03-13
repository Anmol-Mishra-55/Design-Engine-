from datetime import datetime, timedelta, timezone

from app.config import settings
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt

router = APIRouter()

# Hardcoded users for demo
USERS_DB = {"user": "pass", "admin": "bhiv2024", "demo": "demo123"}


@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Validate user credentials
    if form_data.username not in USERS_DB or USERS_DB[form_data.username] != form_data.password:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {"code": "INVALID_CREDENTIALS", "message": "Invalid username or password", "status_code": 401}
            },
        )

    # Create JWT token
    token_data = {
        "sub": form_data.username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRATION_HOURS),
    }
    token = jwt.encode(token_data, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}


from fastapi.security import HTTPBearer

security = HTTPBearer()


@router.post("/refresh", include_in_schema=False)
async def refresh_token(token: str = Depends(security)):
    """Refresh JWT token - requires valid existing token"""
    try:
        # Extract token from Bearer scheme
        token_str = token.credentials

        # Decode existing token to get user
        payload = jwt.decode(token_str, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        username = payload.get("sub")

        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        # Create new JWT token
        token_data = {
            "sub": username,
            "exp": datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRATION_HOURS),
        }
        new_token = jwt.encode(token_data, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return {"access_token": new_token, "token_type": "bearer"}

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
