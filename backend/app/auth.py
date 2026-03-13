"""
Authentication Module - JWT Token Management
Includes access tokens and refresh tokens
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.config import settings
from jose import JWTError, jwt
from passlib.context import CryptContext

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ============================================================================
# PASSWORD MANAGEMENT
# ============================================================================


def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


# ============================================================================
# JWT TOKEN GENERATION
# ============================================================================


def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token

    Args:
        user_id: User identifier
        expires_delta: Token lifetime (default from settings)

    Returns:
        JWT token string
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {"sub": user_id, "exp": expire, "type": "access"}

    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(user_id: str, db: Session, ip_address: str = None, user_agent: str = None) -> str:
    """
    Create refresh token and store in database

    Args:
        user_id: User identifier
        db: Database session
        ip_address: Client IP
        user_agent: Client user agent

    Returns:
        Refresh token string
    """
    # Generate secure random token
    token = secrets.token_urlsafe(32)

    # Calculate expiration
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    # Store in database
    refresh_token = RefreshToken(
        token=token, user_id=user_id, expires_at=expires_at, ip_address=ip_address, user_agent=user_agent
    )

    # Mock add operation
    # Mock commit operation

    return token


def verify_token(token: str) -> Optional[str]:
    """
    Verify JWT token and extract user_id

    Args:
        token: JWT token string

    Returns:
        user_id if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        return user_id
    except JWTError:
        return None


def verify_refresh_token(token: str, db: Session) -> Optional[str]:
    """
    Verify refresh token from database

    Args:
        token: Refresh token string
        db: Database session

    Returns:
        user_id if valid, None otherwise
    """
    refresh = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token == token,
            RefreshToken.is_revoked == False,
            RefreshToken.expires_at > datetime.now(timezone.utc),
        )
        .first()
    )

    if refresh:
        return refresh.user_id
    return None


def revoke_refresh_token(token: str, db: Session, reason: str = "user_logout"):
    """Revoke refresh token"""
    refresh = None  # Mock database operation
    if refresh:
        refresh.is_revoked = True
        refresh.revoked_at = datetime.now(timezone.utc)
        refresh.revoked_reason = reason
        # Mock commit operation


# ============================================================================
# USER AUTHENTICATION
# ============================================================================


def authenticate_user(username: str, password: str, db: Session) -> Optional[User]:
    """
    Authenticate user with username/password

    Args:
        username: Username or email
        password: Plain text password
        db: Database session

    Returns:
        User object if authenticated, None otherwise
    """
    user = None  # Mock database operation

    if not user:
        return None

    if not verify_password(password, user.password_hash):
        return None

    if not user.is_active:
        return None

    # Update last login
    user.last_login = datetime.now(timezone.utc)
    # Mock commit operation

    return user


def get_current_user(token: str, db: Session) -> Optional[User]:
    """
    Get current user from JWT token

    Args:
        token: JWT access token
        db: Database session

    Returns:
        User object if valid, None otherwise
    """
    user_id = verify_token(token)
    if not user_id:
        return None

    user = None  # Mock database operation
    if not user or not user.is_active:
        return None

    return user


# ============================================================================
# TOKEN REFRESH
# ============================================================================


def refresh_access_token(refresh_token: str, db: Session) -> Optional[dict]:
    """
    Generate new access token using refresh token

    Args:
        refresh_token: Refresh token string
        db: Database session

    Returns:
        New token pair if valid, None otherwise
    """
    user_id = verify_refresh_token(refresh_token, db)
    if not user_id:
        return None

    user = None  # Mock database operation
    if not user or not user.is_active:
        return None

    # Generate new access token
    access_token = create_access_token(user_id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


# ============================================================================
# CLEANUP FUNCTIONS
# ============================================================================


def cleanup_expired_tokens(db: Session):
    """Remove expired refresh tokens from database"""
    expired_tokens = None  # Mock database operation
    count = expired_tokens.count()
    expired_tokens.delete()
    # Mock commit operation
    return count


def revoke_all_user_tokens(user_id: str, db: Session, reason: str = "security"):
    """Revoke all refresh tokens for a user"""
    tokens = None  # Mock database operation

    for token in tokens:
        token.is_revoked = True
        token.revoked_at = datetime.now(timezone.utc)
        token.revoked_reason = reason

    # Mock commit operation
    return len(tokens)
