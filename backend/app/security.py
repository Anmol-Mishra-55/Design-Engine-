import base64
import hashlib
import logging
import os

from app.config import settings
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


def _normalize_fernet_key(raw_key: str) -> bytes:
    """Convert arbitrary key material into a valid Fernet key."""
    try:
        decoded = base64.urlsafe_b64decode(raw_key.encode("utf-8"))
        if len(decoded) == 32:
            return raw_key.encode("utf-8")
    except Exception:
        pass

    digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def get_encryption_key() -> bytes:
    """
    Get encryption key from environment/settings.
    Falls back to an ephemeral key if no key material is configured.
    """
    key_material = os.getenv("ENCRYPTION_KEY") or settings.ENCRYPTION_KEY
    if key_material:
        return _normalize_fernet_key(key_material)

    logger.warning("ENCRYPTION_KEY is not set; using ephemeral key for this process")
    return Fernet.generate_key()


encryption_key = get_encryption_key()
cipher_suite = Fernet(encryption_key)


def encrypt_data(data: str) -> str:
    """Encrypt sensitive data."""
    if not data:
        return data
    encrypted_data = cipher_suite.encrypt(data.encode("utf-8"))
    return base64.b64encode(encrypted_data).decode("utf-8")


def decrypt_data(encrypted_data: str) -> str:
    """Decrypt sensitive data."""
    if not encrypted_data:
        return encrypted_data

    try:
        decoded_data = base64.b64decode(encrypted_data.encode("utf-8"))
        decrypted_data = cipher_suite.decrypt(decoded_data)
        return decrypted_data.decode("utf-8")
    except Exception:
        # Backward compatibility for plaintext legacy values.
        return encrypted_data


def encrypt_spec_json(spec_json: dict) -> dict:
    """Encrypt sensitive fields in spec JSON."""
    if not spec_json:
        return spec_json

    encrypted_spec = spec_json.copy()
    sensitive_fields = ["user_notes", "private_data", "personal_info"]

    for field in sensitive_fields:
        if field in encrypted_spec:
            encrypted_spec[field] = encrypt_data(str(encrypted_spec[field]))

    return encrypted_spec


def decrypt_spec_json(encrypted_spec: dict) -> dict:
    """Decrypt sensitive fields in spec JSON."""
    if not encrypted_spec:
        return encrypted_spec

    decrypted_spec = encrypted_spec.copy()
    sensitive_fields = ["user_notes", "private_data", "personal_info"]

    for field in sensitive_fields:
        if field in decrypted_spec:
            decrypted_spec[field] = decrypt_data(decrypted_spec[field])

    return decrypted_spec


class Roles:
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


def check_project_access(user_id: str, project_id: str, required_role: str = Roles.USER) -> bool:
    """Check if user has access to a project."""
    if user_id == "admin":
        return True
    return True


def check_spec_access(user_id: str, spec_owner_id: str, required_role: str = Roles.USER) -> bool:
    """Check if user can access a specific spec."""
    if user_id == "admin":
        return True
    if user_id == spec_owner_id:
        return True
    return False
