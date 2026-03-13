"""
MongoDB GridFS Storage Module
Handles file uploads, downloads, and management using GridFS with Motor (async)
"""
import io
import logging
from datetime import datetime
from typing import Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorGridFSBucket

logger = logging.getLogger(__name__)


class GridFSStorage:
    """Async GridFS storage handler for MongoDB"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.fs_files = AsyncIOMotorGridFSBucket(db, bucket_name="files")
        self.fs_previews = AsyncIOMotorGridFSBucket(db, bucket_name="previews")
        self.fs_geometry = AsyncIOMotorGridFSBucket(db, bucket_name="geometry")
        self.fs_compliance = AsyncIOMotorGridFSBucket(db, bucket_name="compliance")

    def _get_gridfs_bucket(self, bucket: str) -> AsyncIOMotorGridFSBucket:
        """Get GridFS bucket instance"""
        bucket_map = {
            "files": self.fs_files,
            "previews": self.fs_previews,
            "geometry": self.fs_geometry,
            "compliance": self.fs_compliance,
        }
        return bucket_map.get(bucket, self.fs_files)

    async def upload_file(
        self,
        file_path: str,
        bucket: str,
        destination_path: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Upload file to GridFS

        Args:
            file_path: Local file path
            bucket: Target bucket name
            destination_path: Path in GridFS
            content_type: MIME type
            metadata: Additional metadata

        Returns:
            File ID
        """
        try:
            fs_bucket = self._get_gridfs_bucket(bucket)

            with open(file_path, "rb") as f:
                file_data = f.read()

            file_stream = io.BytesIO(file_data)

            file_id = await fs_bucket.upload_from_stream(
                destination_path,
                file_stream,
                metadata={
                    "content_type": content_type or "application/octet-stream",
                    "upload_date": datetime.utcnow(),
                    **(metadata or {}),
                },
            )

            logger.info(f"Uploaded: {destination_path} to {bucket} (ID: {file_id})")
            return str(file_id)

        except Exception as e:
            logger.error(f"Upload failed: {e}")
            raise

    async def upload_bytes(
        self,
        data: bytes,
        bucket: str,
        destination_path: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Upload bytes to GridFS

        Args:
            data: File bytes
            bucket: Target bucket name
            destination_path: Path in GridFS
            content_type: MIME type
            metadata: Additional metadata

        Returns:
            File ID
        """
        try:
            fs_bucket = self._get_gridfs_bucket(bucket)

            file_stream = io.BytesIO(data)

            file_id = await fs_bucket.upload_from_stream(
                destination_path,
                file_stream,
                metadata={
                    "content_type": content_type or "application/octet-stream",
                    "upload_date": datetime.utcnow(),
                    **(metadata or {}),
                },
            )

            logger.info(f"Uploaded bytes: {destination_path} to {bucket} (ID: {file_id})")
            return str(file_id)

        except Exception as e:
            logger.error(f"Upload failed: {e}")
            raise

    async def download_file(self, file_id: str, bucket: str) -> bytes:
        """
        Download file from GridFS

        Args:
            file_id: GridFS file ID
            bucket: Bucket name

        Returns:
            File bytes
        """
        try:
            fs_bucket = self._get_gridfs_bucket(bucket)

            download_stream = io.BytesIO()
            await fs_bucket.download_to_stream(ObjectId(file_id), download_stream)
            return download_stream.getvalue()

        except Exception as e:
            logger.error(f"Download failed: {e}")
            raise

    async def delete_file(self, file_id: str, bucket: str) -> bool:
        """
        Delete file from GridFS

        Args:
            file_id: GridFS file ID
            bucket: Bucket name

        Returns:
            True if deleted
        """
        try:
            fs_bucket = self._get_gridfs_bucket(bucket)

            await fs_bucket.delete(ObjectId(file_id))
            logger.info(f"Deleted: {file_id} from {bucket}")
            return True

        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False

    async def file_exists(self, file_id: str, bucket: str) -> bool:
        """Check if file exists in GridFS"""
        try:
            fs_bucket = self._get_gridfs_bucket(bucket)

            # Try to get file info
            files_cursor = fs_bucket.find({"_id": ObjectId(file_id)})
            files_list = await files_cursor.to_list(length=1)
            return len(files_list) > 0

        except Exception as e:
            logger.debug(f"File existence check failed: {e}")
            return False

    async def list_files(self, bucket: str, metadata_filter: Optional[dict] = None) -> list:
        """
        List files in bucket

        Args:
            bucket: Bucket name
            metadata_filter: Filter by metadata

        Returns:
            List of file info
        """
        try:
            fs_bucket = self._get_gridfs_bucket(bucket)

            query = {}
            if metadata_filter:
                for key, value in metadata_filter.items():
                    query[f"metadata.{key}"] = value

            files_cursor = fs_bucket.find(query)
            files_list = await files_cursor.to_list(length=None)
            return files_list

        except Exception as e:
            logger.error(f"List failed: {e}")
            return []

    async def get_file_info(self, file_id: str, bucket: str) -> Optional[dict]:
        """Get file metadata"""
        try:
            fs_bucket = self._get_gridfs_bucket(bucket)

            files_cursor = fs_bucket.find({"_id": ObjectId(file_id)})
            files_list = await files_cursor.to_list(length=1)

            if files_list:
                file_info = files_list[0]
                return {
                    "_id": str(file_info._id),
                    "filename": file_info.filename,
                    "length": file_info.length,
                    "upload_date": file_info.upload_date,
                    "metadata": file_info.metadata or {},
                }
            return None

        except Exception as e:
            logger.error(f"Get file info failed: {e}")
            return None


async def upload_preview(
    storage: GridFSStorage,
    spec_id: str,
    preview_data: bytes,
    format: str = "png",
) -> str:
    """Upload design preview image"""
    destination = f"previews/{spec_id}.{format}"

    return await storage.upload_bytes(
        preview_data,
        "previews",
        destination,
        content_type=f"image/{format}",
        metadata={"spec_id": spec_id, "type": "preview"},
    )


async def upload_geometry(
    storage: GridFSStorage,
    spec_id: str,
    glb_data: bytes,
) -> str:
    """Upload .GLB geometry file"""
    destination = f"{spec_id}.glb"

    return await storage.upload_bytes(
        glb_data,
        "geometry",
        destination,
        content_type="model/gltf-binary",
        metadata={"spec_id": spec_id, "type": "geometry"},
    )


async def upload_compliance_doc(
    storage: GridFSStorage,
    spec_id: str,
    doc_data: bytes,
    filename: str,
) -> str:
    """Upload compliance document"""
    destination = f"compliance/{spec_id}/{filename}"

    return await storage.upload_bytes(
        doc_data,
        "compliance",
        destination,
        content_type="application/pdf",
        metadata={"spec_id": spec_id, "type": "compliance"},
    )


__all__ = [
    "GridFSStorage",
    "upload_preview",
    "upload_geometry",
    "upload_compliance_doc",
]
