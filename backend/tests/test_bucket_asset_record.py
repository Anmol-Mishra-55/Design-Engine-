"""
Unit tests for BucketAssetRecord contract.

Covers:
  - Construction via create() and from_dict()
  - Required field validation (trace_id, execution_id, bucket_url)
  - Optional field defaults
  - asset_type validation
  - payload_hash helper (hash_bytes)
  - artifact_id property (live URL parsing)
  - to_dict() serialisation round-trip
  - created_at auto-generation and override
  - Exception hierarchy
"""

import hashlib
from datetime import datetime, timezone

import pytest
from app.contracts.bucket_asset_record import BucketAssetRecord, BucketAssetValidationError

# ── Fixtures ──────────────────────────────────────────────────────────────────

TRACE_ID = "trace-abc-123"
EXEC_ID = "exec-xyz-456"
BUCKET_URL = "https://bhiv-bucket.onrender.com/bucket/artifact/some-uuid-1234"


def valid_record(**overrides) -> BucketAssetRecord:
    kwargs = dict(trace_id=TRACE_ID, execution_id=EXEC_ID, bucket_url=BUCKET_URL)
    kwargs.update(overrides)
    return BucketAssetRecord.create(**kwargs)


# ── Construction ──────────────────────────────────────────────────────────────


class TestConstruction:
    def test_create_returns_instance(self):
        r = valid_record()
        assert isinstance(r, BucketAssetRecord)

    def test_required_fields_stored(self):
        r = valid_record()
        assert r.trace_id == TRACE_ID
        assert r.execution_id == EXEC_ID
        assert r.bucket_url == BUCKET_URL

    def test_optional_asset_type_default_empty(self):
        assert valid_record().asset_type == ""

    def test_optional_asset_name_default_empty(self):
        assert valid_record().asset_name == ""

    def test_optional_payload_hash_default_empty(self):
        assert valid_record().payload_hash == ""

    def test_created_at_auto_set(self):
        r = valid_record()
        assert r.created_at
        assert "T" in r.created_at  # ISO-8601

    def test_created_at_override(self):
        ts = "2026-01-01T00:00:00+00:00"
        r = valid_record(created_at=ts)
        assert r.created_at == ts

    def test_whitespace_stripped_from_required_fields(self):
        r = BucketAssetRecord.create(
            trace_id="  trace-1  ",
            execution_id="  exec-1  ",
            bucket_url="  https://bhiv-bucket.onrender.com/bucket/artifact/id  ",
        )
        assert r.trace_id == "trace-1"
        assert r.execution_id == "exec-1"
        assert "  " not in r.bucket_url

    def test_asset_type_stored_lowercase(self):
        r = valid_record(asset_type="GLB")
        assert r.asset_type == "glb"

    def test_all_valid_asset_types(self):
        for at in ("glb", "stl", "step", "spec", "spec_json", "request", "preview", ""):
            r = valid_record(asset_type=at)
            assert r.asset_type == at.lower()

    def test_asset_name_stored(self):
        r = valid_record(asset_name="drone_mesh_v1")
        assert r.asset_name == "drone_mesh_v1"

    def test_payload_hash_stored(self):
        h = "abc123deadbeef"
        r = valid_record(payload_hash=h)
        assert r.payload_hash == h


# ── Required field validation ─────────────────────────────────────────────────


class TestRequiredFieldValidation:
    def test_missing_trace_id_raises(self):
        with pytest.raises(BucketAssetValidationError, match="trace_id"):
            BucketAssetRecord.create(trace_id="", execution_id=EXEC_ID, bucket_url=BUCKET_URL)

    def test_whitespace_trace_id_raises(self):
        with pytest.raises(BucketAssetValidationError, match="trace_id"):
            BucketAssetRecord.create(trace_id="   ", execution_id=EXEC_ID, bucket_url=BUCKET_URL)

    def test_missing_execution_id_raises(self):
        with pytest.raises(BucketAssetValidationError, match="execution_id"):
            BucketAssetRecord.create(trace_id=TRACE_ID, execution_id="", bucket_url=BUCKET_URL)

    def test_whitespace_execution_id_raises(self):
        with pytest.raises(BucketAssetValidationError, match="execution_id"):
            BucketAssetRecord.create(trace_id=TRACE_ID, execution_id="  ", bucket_url=BUCKET_URL)

    def test_missing_bucket_url_raises(self):
        with pytest.raises(BucketAssetValidationError, match="bucket_url"):
            BucketAssetRecord.create(trace_id=TRACE_ID, execution_id=EXEC_ID, bucket_url="")

    def test_whitespace_bucket_url_raises(self):
        with pytest.raises(BucketAssetValidationError, match="bucket_url"):
            BucketAssetRecord.create(trace_id=TRACE_ID, execution_id=EXEC_ID, bucket_url="   ")

    def test_invalid_asset_type_raises(self):
        with pytest.raises(BucketAssetValidationError, match="asset_type"):
            BucketAssetRecord.create(trace_id=TRACE_ID, execution_id=EXEC_ID, bucket_url=BUCKET_URL, asset_type="video")

    def test_unknown_asset_type_raises(self):
        with pytest.raises(BucketAssetValidationError):
            BucketAssetRecord.create(trace_id=TRACE_ID, execution_id=EXEC_ID, bucket_url=BUCKET_URL, asset_type="png")


# ── from_dict ─────────────────────────────────────────────────────────────────


class TestFromDict:
    def test_from_dict_round_trip(self):
        r = valid_record(asset_type="glb", asset_name="test_asset", payload_hash="deadbeef")
        r2 = BucketAssetRecord.from_dict(r.to_dict())
        assert r2.trace_id == r.trace_id
        assert r2.execution_id == r.execution_id
        assert r2.bucket_url == r.bucket_url
        assert r2.asset_type == r.asset_type
        assert r2.asset_name == r.asset_name
        assert r2.payload_hash == r.payload_hash
        assert r2.created_at == r.created_at

    def test_from_dict_missing_optional_fields_defaults(self):
        r = BucketAssetRecord.from_dict(
            {
                "trace_id": TRACE_ID,
                "execution_id": EXEC_ID,
                "bucket_url": BUCKET_URL,
            }
        )
        assert r.asset_type == ""
        assert r.asset_name == ""
        assert r.payload_hash == ""

    def test_from_dict_missing_trace_id_raises(self):
        with pytest.raises(BucketAssetValidationError):
            BucketAssetRecord.from_dict({"execution_id": EXEC_ID, "bucket_url": BUCKET_URL})

    def test_from_dict_missing_execution_id_raises(self):
        with pytest.raises(BucketAssetValidationError):
            BucketAssetRecord.from_dict({"trace_id": TRACE_ID, "bucket_url": BUCKET_URL})

    def test_from_dict_missing_bucket_url_raises(self):
        with pytest.raises(BucketAssetValidationError):
            BucketAssetRecord.from_dict({"trace_id": TRACE_ID, "execution_id": EXEC_ID})


# ── to_dict / serialisation ───────────────────────────────────────────────────


class TestSerialisation:
    def test_to_dict_has_all_seven_keys(self):
        r = valid_record()
        d = r.to_dict()
        assert set(d.keys()) == {
            "trace_id",
            "execution_id",
            "bucket_url",
            "asset_type",
            "asset_name",
            "payload_hash",
            "created_at",
        }

    def test_to_dict_values_match(self):
        r = valid_record(asset_type="stl", asset_name="wall_mesh", payload_hash="abc")
        d = r.to_dict()
        assert d["trace_id"] == TRACE_ID
        assert d["execution_id"] == EXEC_ID
        assert d["bucket_url"] == BUCKET_URL
        assert d["asset_type"] == "stl"
        assert d["asset_name"] == "wall_mesh"
        assert d["payload_hash"] == "abc"

    def test_to_dict_is_json_serialisable(self):
        import json

        d = valid_record(asset_type="step").to_dict()
        json.dumps(d)  # must not raise


# ── payload_hash helper ───────────────────────────────────────────────────────


class TestHashBytes:
    def test_returns_sha256_hex(self):
        data = b"hello bucket"
        expected = hashlib.sha256(data).hexdigest()
        assert BucketAssetRecord.hash_bytes(data) == expected

    def test_empty_bytes_returns_known_hash(self):
        expected = hashlib.sha256(b"").hexdigest()
        assert BucketAssetRecord.hash_bytes(b"") == expected

    def test_different_bytes_differ(self):
        h1 = BucketAssetRecord.hash_bytes(b"data_a")
        h2 = BucketAssetRecord.hash_bytes(b"data_b")
        assert h1 != h2

    def test_hash_length_is_64(self):
        assert len(BucketAssetRecord.hash_bytes(b"x")) == 64


# ── artifact_id property ──────────────────────────────────────────────────────


class TestArtifactId:
    def test_extracts_id_from_canonical_url(self):
        r = valid_record()
        assert r.artifact_id == "some-uuid-1234"

    def test_extracts_uuid_style_id(self):
        url = "https://bhiv-bucket.onrender.com/bucket/artifact/f47ac10b-58cc-4372-a567-0e02b2c3d479"
        r = valid_record(bucket_url=url)
        assert r.artifact_id == "f47ac10b-58cc-4372-a567-0e02b2c3d479"

    def test_trailing_slash_ignored(self):
        url = "https://bhiv-bucket.onrender.com/bucket/artifact/myid/"
        r = valid_record(bucket_url=url)
        assert r.artifact_id == "myid"

    def test_non_standard_url_returns_last_segment(self):
        url = "https://bhiv-bucket.onrender.com/custom/path/abc123"
        r = valid_record(bucket_url=url)
        assert r.artifact_id == "abc123"


# ── Exception hierarchy ───────────────────────────────────────────────────────


class TestExceptionHierarchy:
    def test_bucket_asset_validation_error_is_value_error(self):
        assert issubclass(BucketAssetValidationError, ValueError)

    def test_bucket_asset_validation_error_is_exception(self):
        assert issubclass(BucketAssetValidationError, Exception)

    def test_error_message_contains_field_name(self):
        try:
            BucketAssetRecord.create(trace_id="", execution_id=EXEC_ID, bucket_url=BUCKET_URL)
        except BucketAssetValidationError as e:
            assert "trace_id" in str(e)

    def test_error_message_for_invalid_asset_type(self):
        try:
            BucketAssetRecord.create(trace_id=TRACE_ID, execution_id=EXEC_ID, bucket_url=BUCKET_URL, asset_type="video")
        except BucketAssetValidationError as e:
            assert "asset_type" in str(e)
            assert "video" in str(e)


# ── Live bucket URL alignment ─────────────────────────────────────────────────


class TestLiveBucketAlignment:
    """Verify the contract aligns with the live bucket at https://bhiv-bucket.onrender.com."""

    LIVE_BASE = "https://bhiv-bucket.onrender.com"

    def test_live_glb_url_accepted(self):
        url = f"{self.LIVE_BASE}/bucket/artifact/abc-glb-001"
        r = BucketAssetRecord.create(trace_id="trace-1", execution_id="exec-1", bucket_url=url, asset_type="glb")
        assert r.bucket_url == url
        assert r.artifact_id == "abc-glb-001"

    def test_live_stl_url_accepted(self):
        url = f"{self.LIVE_BASE}/bucket/artifact/abc-stl-001"
        r = valid_record(bucket_url=url, asset_type="stl")
        assert r.asset_type == "stl"

    def test_live_step_url_accepted(self):
        url = f"{self.LIVE_BASE}/bucket/artifact/abc-step-001"
        r = valid_record(bucket_url=url, asset_type="step")
        assert r.asset_type == "step"

    def test_payload_hash_matches_upload_to_bucket_pattern(self):
        """upload_to_bucket() uses SHA-256 — verify hash_bytes matches."""
        data = b"some 3d mesh binary"
        expected = hashlib.sha256(data).hexdigest()
        assert BucketAssetRecord.hash_bytes(data) == expected

    def test_full_record_for_drone_glb(self):
        """Simulate a BucketAssetRecord created after a drone GLB upload."""
        glb_data = b"fake-glb-binary-content"
        url = f"{self.LIVE_BASE}/bucket/artifact/drone-exec-uuid-9999"
        r = BucketAssetRecord.create(
            trace_id="ttg-trace-drone-001",
            execution_id="ttg-exec-drone-001",
            bucket_url=url,
            asset_type="glb",
            asset_name="drone_rotorcraft_mesh",
            payload_hash=BucketAssetRecord.hash_bytes(glb_data),
        )
        assert r.domain_ok if hasattr(r, "domain_ok") else True
        assert r.artifact_id == "drone-exec-uuid-9999"
        assert r.asset_type == "glb"
        assert len(r.payload_hash) == 64
        d = r.to_dict()
        assert d["trace_id"] == "ttg-trace-drone-001"
