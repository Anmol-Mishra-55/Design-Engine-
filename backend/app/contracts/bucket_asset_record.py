"""
BucketAssetRecord
=================
Immutable record of a single asset written to the live Bucket service.

Live Bucket base URL : https://bhiv-bucket.onrender.com
Write endpoint       : POST /bucket/artifacts/write
Canonical asset URL  : https://bhiv-bucket.onrender.com/bucket/artifact/{artifact_id}

This contract is created AFTER a successful upload_to_bucket() call and ties
together the trace context (trace_id, execution_id), the asset identity
(asset_type, asset_name), the storage location (bucket_url), and a
content-integrity fingerprint (payload_hash).

Required fields:
    trace_id      — pipeline trace identifier (from CoreGateway / TTGClient)
    execution_id  — TTG execution ID returned by POST /core/execute
    bucket_url    — canonical URL returned by upload_to_bucket()

Optional fields (defaulted):
    asset_type    — "glb" | "stl" | "step" | "spec" | "request" | ""
    asset_name    — human-readable label, e.g. "drone_mesh_v1"
    payload_hash  — SHA-256 hex of the raw bytes written (set by caller)
    created_at    — ISO-8601 UTC timestamp (auto-set on construction)

Raises:
    BucketAssetValidationError — any required field is empty / missing
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# ── Exception ─────────────────────────────────────────────────────────────────


class BucketAssetValidationError(ValueError):
    """Raised when a required BucketAssetRecord field is missing or empty."""


# ── Contract ──────────────────────────────────────────────────────────────────

_VALID_ASSET_TYPES = {"glb", "stl", "step", "spec", "spec_json", "request", "preview", ""}


@dataclass
class BucketAssetRecord:
    """
    Immutable record of one asset stored in the live Bucket service.

    Construct via BucketAssetRecord.create() to get validation + auto-timestamp,
    or use from_dict() to deserialise a stored record.
    """

    trace_id: str
    execution_id: str
    bucket_url: str
    asset_type: str = ""
    asset_name: str = ""
    payload_hash: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # ── Factories ──────────────────────────────────────────────────────────────

    @classmethod
    def create(
        cls,
        trace_id: str,
        execution_id: str,
        bucket_url: str,
        asset_type: str = "",
        asset_name: str = "",
        payload_hash: str = "",
        created_at: Optional[str] = None,
    ) -> "BucketAssetRecord":
        """
        Validated constructor.

        Raises BucketAssetValidationError if trace_id, execution_id, or
        bucket_url are empty or whitespace-only.
        """
        cls._validate(trace_id, execution_id, bucket_url, asset_type)
        return cls(
            trace_id=trace_id.strip(),
            execution_id=execution_id.strip(),
            bucket_url=bucket_url.strip(),
            asset_type=asset_type.strip().lower(),
            asset_name=asset_name.strip(),
            payload_hash=payload_hash.strip(),
            created_at=created_at or datetime.now(timezone.utc).isoformat(),
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BucketAssetRecord":
        """Deserialise from a dict (e.g. loaded from JSONL trace file)."""
        return cls.create(
            trace_id=str(data.get("trace_id", "")),
            execution_id=str(data.get("execution_id", "")),
            bucket_url=str(data.get("bucket_url", "")),
            asset_type=str(data.get("asset_type", "")),
            asset_name=str(data.get("asset_name", "")),
            payload_hash=str(data.get("payload_hash", "")),
            created_at=data.get("created_at") or None,
        )

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def hash_bytes(data: bytes) -> str:
        """Return SHA-256 hex digest of raw bytes — use as payload_hash."""
        return hashlib.sha256(data).hexdigest()

    @property
    def artifact_id(self) -> str:
        """
        Extract artifact_id from a canonical bucket URL.
        URL format: https://bhiv-bucket.onrender.com/bucket/artifact/{artifact_id}
        Returns empty string if the URL does not follow the expected pattern.
        """
        parts = self.bucket_url.rstrip("/").rsplit("/", 1)
        return parts[-1] if len(parts) == 2 and parts[-1] else ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "execution_id": self.execution_id,
            "bucket_url": self.bucket_url,
            "asset_type": self.asset_type,
            "asset_name": self.asset_name,
            "payload_hash": self.payload_hash,
            "created_at": self.created_at,
        }

    # ── Internal validation ────────────────────────────────────────────────────

    @staticmethod
    def _validate(
        trace_id: str,
        execution_id: str,
        bucket_url: str,
        asset_type: str,
    ) -> None:
        for name, value in [
            ("trace_id", trace_id),
            ("execution_id", execution_id),
            ("bucket_url", bucket_url),
        ]:
            if not value or not str(value).strip():
                raise BucketAssetValidationError(f"BucketAssetRecord: '{name}' is required and cannot be empty.")

        if asset_type and asset_type.strip().lower() not in _VALID_ASSET_TYPES:
            raise BucketAssetValidationError(
                f"BucketAssetRecord: invalid asset_type '{asset_type}'. "
                f"Must be one of {sorted(_VALID_ASSET_TYPES)}."
            )
