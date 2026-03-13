"""
Storage Module - MongoDB GridFS Integration
Handles file uploads, previews, and file management using GridFS
"""
import logging
import mimetypes
from datetime import datetime, timedelta
from typing import Optional

from app.config import settings
from app.database_mongodb import get_database
from app.storage_mongodb import GridFSStorage

logger = logging.getLogger(__name__)

# Global storage instance
_storage: Optional[GridFSStorage] = None


def get_storage() -> GridFSStorage:
    """Get GridFS storage instance"""
    global _storage
    if _storage is None:
        db = get_database()
        _storage = GridFSStorage(db)
    return _storage


# ============================================================================
# FILE UPLOAD
# ============================================================================


def upload_file(file_path: str, bucket: str, destination_path: str, content_type: Optional[str] = None) -> str:
    """
    Upload file to MongoDB GridFS

    Args:
        file_path: Local file path
        bucket: Target bucket name
        destination_path: Path in bucket (e.g., "users/123/file.pdf")
        content_type: MIME type (auto-detected if None)

    Returns:
        File ID
    """
    try:
        # Auto-detect content type
        if not content_type:
            content_type, _ = mimetypes.guess_type(file_path)
            content_type = content_type or "application/octet-stream"

        storage = get_storage()
        file_id = storage.upload_file(
            file_path=file_path, bucket=bucket, destination_path=destination_path, content_type=content_type
        )

        logger.info(f"Uploaded: {destination_path} to {bucket}")
        return file_id

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise


def upload_preview(spec_id: str, preview_data: bytes, format: str = "png") -> str:
    """
    Upload design preview image

    Args:
        spec_id: Specification ID
        preview_data: Image bytes
        format: Image format (png, jpg)

    Returns:
        File ID
    """
    destination = f"previews/{spec_id}.{format}"

    try:
        storage = get_storage()
        file_id = storage.upload_bytes(
            data=preview_data,
            bucket=settings.GRIDFS_BUCKET_PREVIEWS,
            destination_path=destination,
            content_type=f"image/{format}",
            metadata={"spec_id": spec_id, "type": "preview"},
        )

        logger.info(f"Preview uploaded: {spec_id}")
        return file_id

    except Exception as e:
        logger.error(f"Preview upload failed: {e}")
        raise


def upload_geometry(spec_id: str, glb_data: bytes) -> str:
    """
    Upload .GLB geometry file

    Args:
        spec_id: Specification ID
        glb_data: GLB file bytes

    Returns:
        File ID
    """
    destination = f"{spec_id}.glb"

    try:
        storage = get_storage()
        file_id = storage.upload_bytes(
            data=glb_data,
            bucket=settings.GRIDFS_BUCKET_GEOMETRY,
            destination_path=destination,
            content_type="model/gltf-binary",
            metadata={"spec_id": spec_id, "type": "geometry"},
        )

        logger.info(f"Geometry uploaded: {spec_id}")
        return file_id

    except Exception as e:
        logger.error(f"Geometry upload failed: {e}")
        raise


# ============================================================================
# FILE ACCESS
# ============================================================================


def file_exists(bucket: str, file_path: str) -> bool:
    """Check if file exists in storage"""
    try:
        storage = get_storage()
        files = storage.list_files(bucket, metadata_filter={"filename": file_path})
        return len(files) > 0
    except Exception as e:
        logger.debug(f"File existence check failed: {e}")
        return False


def generate_signed_url(file_path: str, bucket: Optional[str] = None, expires_in: int = 3600) -> str:
    """
    Generate signed URL for private file access
    Note: GridFS doesn't have signed URLs, so we return a direct access URL

    Args:
        file_path: File ID or path
        bucket: Bucket name
        expires_in: Expiration time in seconds (not used in GridFS)

    Returns:
        Access URL
    """
    try:
        # For GridFS, we return a direct access URL
        # In a real implementation, you'd create an endpoint that serves files
        return f"/api/v1/files/{bucket}/{file_path}"

    except Exception as e:
        logger.error(f"URL generation failed: {e}")
        return file_path


def download_file(file_id: str, bucket: str) -> bytes:
    """Download file from GridFS"""
    try:
        storage = get_storage()
        return storage.download_file(file_id, bucket)
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise


# ============================================================================
# FILE MANAGEMENT
# ============================================================================


def delete_file(file_path: str, bucket: str) -> bool:
    """Delete file from storage"""
    try:
        storage = get_storage()
        success = storage.delete_file(file_path, bucket)
        if success:
            logger.info(f"Deleted: {file_path} from {bucket}")
        return success
    except Exception as e:
        logger.error(f"Delete failed: {e}")
        return False


def list_files(bucket: str, path: str = "") -> list:
    """List files in bucket path"""
    try:
        storage = get_storage()
        files = storage.list_files(bucket)
        return files
    except Exception as e:
        logger.error(f"List failed: {e}")
        return []


def get_file_info(file_id: str, bucket: str) -> Optional[dict]:
    """Get file metadata"""
    try:
        storage = get_storage()
        return storage.get_file_info(file_id, bucket)
    except Exception as e:
        logger.error(f"Get file info failed: {e}")
        return None


# ============================================================================
# INITIALIZATION
# ============================================================================


def init_storage():
    """Initialize storage system on startup"""
    logger.info("Initializing MongoDB GridFS storage...")
    try:
        # Test storage connection
        storage = get_storage()
        logger.info("GridFS storage initialization complete")
        return True
    except Exception as e:
        logger.error(f"Storage initialization failed: {e}")
        return False


# ============================================================================
# COMPATIBILITY ALIASES
# ============================================================================


def get_signed_url(bucket: str, file_path: str, expires: int = 3600) -> str:
    """Alias for generate_signed_url for backward compatibility"""
    return generate_signed_url(file_path, bucket, expires)


async def upload_to_bucket(bucket: str, file_path: str, data: bytes) -> str:
    """Upload data to bucket (async wrapper)"""
    try:
        storage = get_storage()
        file_id = await storage.upload_bytes(
            data=data, bucket=bucket, destination_path=file_path, content_type="application/octet-stream"
        )
        return file_id
    except Exception as e:
        logger.error(f"Upload to bucket failed: {e}")
        raise


# ============================================================================
# BUCKET MANAGEMENT (GridFS Collections)
# ============================================================================


def ensure_buckets_exist():
    """
    Ensure all required GridFS collections exist
    GridFS collections are created automatically when first used
    """
    try:
        storage = get_storage()
        logger.info("GridFS collections will be created automatically when first used")
        return True
    except Exception as e:
        logger.warning(f"GridFS check failed (non-critical): {e}")
        return True


if __name__ != "__main__":
    logger.info("MongoDB GridFS storage module loaded")
