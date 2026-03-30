"""
File Download API - Serve files from MongoDB GridFS
"""
import logging

from app.database_mongodb import get_database
from app.storage_mongodb import GridFSStorage
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

router = APIRouter()
logger = logging.getLogger(__name__)

CONTENT_TYPES = {
    "glb": "model/gltf-binary",
    "stl": "model/stl",
    "step": "application/step",
    "json": "application/json",
}


@router.get("/files/{bucket}/{file_id}")
async def download_file_endpoint(bucket: str, file_id: str):
    """Download file from GridFS storage"""
    try:
        from bson import ObjectId
        from bson.errors import InvalidId

        db = get_database()
        fs_bucket = GridFSStorage(db)._get_gridfs_bucket(bucket)

        try:
            oid = ObjectId(file_id)
        except InvalidId:
            raise HTTPException(status_code=404, detail="Invalid file ID")

        # Open stream directly — raises if not found
        try:
            grid_out = await fs_bucket.open_download_stream(oid)
        except Exception:
            raise HTTPException(status_code=404, detail="File not found")

        file_data = await grid_out.read()
        filename = grid_out.filename or file_id
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        meta = grid_out.metadata or {}
        content_type = meta.get("content_type") or CONTENT_TYPES.get(ext, "application/octet-stream")
        disposition = "attachment" if ext in {"glb", "stl", "step"} else "inline"

        return Response(
            content=file_data,
            media_type=content_type,
            headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File download failed: {e}")
        raise HTTPException(status_code=500, detail="File download failed")
