"""
Storage Module — Live Bucket Service Integration (Phase 4)

ALL outputs MUST go through upload_to_bucket().
Writes to the live Bucket service at BUCKET_URL/bucket/artifacts/write.
Local file writes and GridFS fallbacks are NOT allowed.

Confirmed working contract:
  POST /bucket/artifacts/write
  { "requester_id": "core", "integration_id": "core",
    "artifact": { ..., "schema_version": "1.0.0", "parent_hash": <latest_hash> } }

The Bucket is append-only — every write must carry parent_hash = current chain tip.
We fetch /bucket/latest-hash before each write to satisfy the lineage check.
"""
import base64
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from app.config import settings

logger = logging.getLogger(__name__)

_BUCKET_BASE = settings.BUCKET_URL.rstrip("/")
_WRITE_ENDPOINT = f"{_BUCKET_BASE}/bucket/artifacts/write"
_READ_ENDPOINT = f"{_BUCKET_BASE}/bucket/artifacts/read"
_LATEST_HASH_ENDPOINT = f"{_BUCKET_BASE}/bucket/latest-hash"

_REQUESTER_ID = "core"
_INTEGRATION_ID = "core"
_SCHEMA_VERSION = "1.0.0"


async def _get_latest_hash(client: httpx.AsyncClient) -> Optional[str]:
    """Fetch the current chain tip hash from the Bucket service."""
    try:
        r = await client.get(_LATEST_HASH_ENDPOINT)
        r.raise_for_status()
        return r.json().get("last_hash")
    except Exception as exc:
        logger.warning("Could not fetch latest hash (will use None): %s", exc)
        return None


async def upload_to_bucket(bucket: str, path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """
    Upload bytes to the live Bucket service (append-only chain).

    Fetches the current chain tip (parent_hash) before each write.
    Retries up to 5 times on lineage conflicts (parallel request race).

    Returns:
        Canonical Bucket URL:  https://bhiv-bucket.onrender.com/bucket/artifact/<artifact_id>

    Raises:
        RuntimeError if the upload fails after all retries.
    """
    import asyncio as _asyncio

    artifact_id = str(uuid.uuid4())
    data_hash = hashlib.sha256(data).hexdigest()

    for attempt in range(5):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                parent_hash = await _get_latest_hash(client)

                payload = {
                    "requester_id": _REQUESTER_ID,
                    "integration_id": _INTEGRATION_ID,
                    "artifact": {
                        "artifact_id": artifact_id,
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        "schema_version": _SCHEMA_VERSION,
                        "source_module_id": _REQUESTER_ID,
                        "artifact_type": f"{bucket}/{path}",
                        "parent_hash": parent_hash,
                        "hash": data_hash,
                        "payload": {
                            "bucket": bucket,
                            "path": path,
                            "content_type": content_type,
                            "data_base64": base64.b64encode(data).decode("ascii"),
                            "size_bytes": len(data),
                        },
                    },
                }

                response = await client.post(_WRITE_ENDPOINT, json=payload)
                response.raise_for_status()
                result = response.json()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text
            # Lineage conflict from parallel writes — retry with fresh hash
            if exc.response.status_code == 400 and "Invalid lineage" in body:
                wait = 0.2 * (attempt + 1)
                logger.warning("Bucket lineage conflict (attempt %d/5), retrying in %.1fs", attempt + 1, wait)
                await _asyncio.sleep(wait)
                continue
            raise RuntimeError(f"Bucket upload failed [{exc.response.status_code}]: {body}") from exc
        except Exception as exc:
            raise RuntimeError(f"Bucket upload failed: {exc}") from exc

        if not result.get("success"):
            raise RuntimeError(f"Bucket rejected artifact: {result.get('error', result)}")

        url = f"{_BUCKET_BASE}/bucket/artifact/{artifact_id}"
        logger.info("bucket.upload OK  bucket=%s  path=%s  id=%s  bytes=%d", bucket, path, artifact_id, len(data))
        return url

    raise RuntimeError("Bucket upload failed: exceeded 5 lineage conflict retries")


async def download_from_bucket(bucket: str, artifact_id: str) -> bytes:
    """Download bytes from the live Bucket service by artifact_id."""
    payload = {
        "requester_id": _REQUESTER_ID,
        "integration_id": _INTEGRATION_ID,
        "artifact_id": artifact_id,
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(_READ_ENDPOINT, json=payload)
            response.raise_for_status()
            result = response.json()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"Bucket download failed [{exc.response.status_code}]: {exc.response.text}") from exc
    except Exception as exc:
        raise RuntimeError(f"Bucket download failed: {exc}") from exc

    if not result.get("success"):
        raise RuntimeError(f"Bucket read failed: {result.get('error', result)}")

    data_b64 = result.get("data", {}).get("artifact", {}).get("payload", {}).get("data_base64")
    if not data_b64:
        raise RuntimeError(f"Bucket returned no data_base64 for artifact {artifact_id}")

    return base64.b64decode(data_b64)


def get_signed_url(bucket: str, artifact_id: str, expires: int = 3600) -> str:
    """Return a serve URL for a stored artifact."""
    return f"{_BUCKET_BASE}/bucket/artifact/{artifact_id}"


if __name__ != "__main__":
    logger.info("Storage module loaded — all outputs route through live Bucket service: %s", _BUCKET_BASE)
