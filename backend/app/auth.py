"""
Authentication helpers (MongoDB-compatible).
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config import settings
from jose import JWTError, jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode = {"sub": user_id, "exp": expire, "type": "access"}
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


async def create_refresh_token(
    user_id: str,
    db,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    await db.refresh_tokens.insert_one(
        {
            "token": token,
            "user_id": user_id,
            "expires_at": expires_at,
            "is_revoked": False,
            "created_at": datetime.now(timezone.utc),
            "ip_address": ip_address,
            "user_agent": user_agent,
        }
    )
    return token


async def verify_refresh_token(token: str, db) -> Optional[str]:
    refresh = await db.refresh_tokens.find_one(
        {"token": token, "is_revoked": False, "expires_at": {"$gt": datetime.now(timezone.utc)}}
    )
    if not refresh:
        return None
    return refresh.get("user_id")


async def revoke_refresh_token(token: str, db, reason: str = "user_logout"):
    await db.refresh_tokens.update_one(
        {"token": token},
        {"$set": {"is_revoked": True, "revoked_at": datetime.now(timezone.utc), "revoked_reason": reason}},
    )


async def authenticate_user(username: str, password: str, db) -> Optional[dict]:
    user = await db.users.find_one({"$or": [{"username": username}, {"email": username}], "is_active": True})
    if not user:
        return None

    password_hash = user.get("password_hash") or user.get("hashed_password")
    if not password_hash:
        return None
    if not verify_password(password, password_hash):
        return None

    await db.users.update_one({"_id": user["_id"]}, {"$set": {"last_login": datetime.now(timezone.utc)}})
    return user


async def get_current_user(token: str, db) -> Optional[dict]:
    user_id = verify_token(token)
    if not user_id:
        return None
    return await db.users.find_one({"$or": [{"_id": user_id}, {"username": user_id}], "is_active": True})


async def refresh_access_token(refresh_token: str, db) -> Optional[dict]:
    user_id = await verify_refresh_token(refresh_token, db)
    if not user_id:
        return None
    access_token = create_access_token(user_id)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


async def cleanup_expired_tokens(db) -> int:
    result = await db.refresh_tokens.delete_many({"expires_at": {"$lte": datetime.now(timezone.utc)}})
    return int(result.deleted_count)


async def revoke_all_user_tokens(user_id: str, db, reason: str = "security") -> int:
    result = await db.refresh_tokens.update_many(
        {"user_id": user_id, "is_revoked": False},
        {"$set": {"is_revoked": True, "revoked_at": datetime.now(timezone.utc), "revoked_reason": reason}},
    )
    return int(result.modified_count)
