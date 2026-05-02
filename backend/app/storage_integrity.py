"""
Storage Integrity — bucket only. No local file writes.
All artifacts go through upload_to_bucket(). Raises on failure.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class StorageManager:
    """Routes all artifact storage through GridFS bucket."""

    async def store_spec(self, spec_id: str, spec_json: dict, metadata: Optional[dict] = None) -> str:
        import json

        from app.storage import upload_to_bucket

        data = json.dumps(spec_json, indent=2).encode("utf-8")
        url = await upload_to_bucket("files", f"specs/{spec_id}.json", data, "application/json")
        if not url:
            raise Exception(f"Bucket upload failed for spec {spec_id} → abort")
        logger.info(f"Spec stored in bucket: {spec_id}")
        return url

    async def store_geometry(self, spec_id: str, geometry_data: bytes, file_type: str = "glb") -> str:
        from app.storage import upload_to_bucket

        content_type = "model/gltf-binary" if file_type == "glb" else "application/octet-stream"
        url = await upload_to_bucket("geometry", f"{spec_id}.{file_type}", geometry_data, content_type)
        if not url:
            raise Exception(f"Bucket upload failed for geometry {spec_id} → abort")
        logger.info(f"Geometry stored in bucket: {spec_id}")
        return url

    async def store_preview(self, spec_id: str, preview_data: bytes, file_type: str = "glb") -> str:
        from app.storage import upload_to_bucket

        content_type = "model/gltf-binary" if file_type == "glb" else "image/png"
        url = await upload_to_bucket("previews", f"{spec_id}.{file_type}", preview_data, content_type)
        if not url:
            raise Exception(f"Bucket upload failed for preview {spec_id} → abort")
        logger.info(f"Preview stored in bucket: {spec_id}")
        return url


# Global storage manager instance
storage_manager = StorageManager()
