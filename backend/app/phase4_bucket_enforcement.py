"""
PHASE 4: Bucket-Only Enforcement
===============================

RULE: All URLs must be Bucket URLs.
No /static/, no /data/, no local paths.

If URL is not /api/v1/files/* → ERROR
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def validate_bucket_url(url: Optional[str]) -> bool:
    """
    Validate that URL is a Bucket URL, not a local path.
    
    Valid:
    - /api/v1/files/geometry/{id}
    - /api/v1/files/files/{id}
    - http://localhost:8000/api/v1/files/...
    
    Invalid:
    - /static/geometry/...
    - /data/geometry_outputs/...
    - file:///...
    - C:\\...
    """
    if not url:
        return False
    
    # Must be bucket URL
    if "/api/v1/files/" not in url:
        logger.error(f"INVALID URL (not bucket): {url}")
        return False
    
    # Must NOT be local path
    forbidden = ["/static/", "/data/", "file://", "C:\\", "\\\\"]
    for pattern in forbidden:
        if pattern in url:
            logger.error(f"INVALID URL (forbidden pattern {pattern}): {url}")
            return False
    
    logger.info(f"✓ Valid bucket URL: {url}")
    return True


async def enforce_bucket_urls(response_data: dict) -> None:
    """
    Validate all URLs in response are bucket URLs.
    Raises if any local paths detected.
    """
    
    urls_to_check = [
        response_data.get("glb_url"),
        response_data.get("stl_url"),
        response_data.get("step_url"),
        response_data.get("preview_url"),
        response_data.get("geometry_url"),
    ]
    
    metadata = response_data.get("metadata", {})
    if isinstance(metadata, dict):
        urls_to_check.append(metadata.get("export_urls", {}).get("glb"))
    
    for url in urls_to_check:
        if url and not validate_bucket_url(url):
            raise RuntimeError(
                f"FATAL: Invalid URL detected (PHASE 4 enforcement): {url}. "
                "All URLs must be /api/v1/files/bucket/file_id format."
            )
    
    logger.info("✓ All URLs validated as bucket URLs")
