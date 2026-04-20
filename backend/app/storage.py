"""
Storage Module - MongoDB GridFS Bucket Integration

All outputs MUST go through upload_to_bucket().
Local file writes are NOT allowed.
"""
import logging
from typing import Optional

from app.database_mongodb import get_database
from app.storage_mongodb import GridFSStorage

logger = logging.getLogger(__name__)

_storage: Optional[GridFSStorage] = None


def get_storage() -> GridFSStorage:
    """Get GridFS storage instance."""
    global _storage
    if _storage is None:
        db = get_database()
        _storage = GridFSStorage(db)
    return _storage


async def upload_to_bucket(bucket: str, path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """
    Upload bytes to a named GridFS bucket.

    Args:
        bucket:       Bucket name  ("geometry", "files", "previews", "compliance")
        path:         Destination path inside the bucket  (e.g. "spec_abc.glb")
        data:         Raw bytes to store
        content_type: MIME type

    Returns:
        Canonical bucket URL:  /api/v1/files/<bucket>/<file_id>

    Raises:
        Exception if the upload fails — callers must NOT fall back to local disk.
    """
    storage = get_storage()
    file_id = await storage.upload_bytes(
        data=data,
        bucket=bucket,
        destination_path=path,
        content_type=content_type,
    )
    url = f"/api/v1/files/{bucket}/{file_id}"
    logger.info("bucket.upload OK  bucket=%s  path=%s  id=%s  bytes=%d", bucket, path, file_id, len(data))
    return url


async def download_from_bucket(bucket: str, file_id: str) -> bytes:
    """Download bytes from a named GridFS bucket by file_id."""
    storage = get_storage()
    return await storage.download_file(file_id, bucket)


def get_signed_url(bucket: str, file_path: str, expires: int = 3600) -> str:
    """Return a serve URL for a stored file (GridFS has no signed URLs)."""
    return f"/api/v1/files/{bucket}/{file_path}"


if __name__ != "__main__":
    logger.info("Storage module loaded — all outputs route through GridFS bucket")
