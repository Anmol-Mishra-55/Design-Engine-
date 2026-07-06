"""
Tests for KnowledgeLoader.

Uses pytest's tmp_path fixture so every test gets an isolated directory.
No mocking — the loader is exercised against real files on disk.
"""
import json
import time
from pathlib import Path

import pytest
from app.design_knowledge.knowledge.loader import (
    KnowledgeDuplicateError,
    KnowledgeLoader,
    KnowledgeLoaderError,
    KnowledgeValidationError,
)
from app.design_knowledge.knowledge.registry import KnowledgeRegistry

# ── helpers ───────────────────────────────────────────────────────────────────


def _write(directory: Path, filename: str, payload: dict) -> Path:
    """Write *payload* as JSON to *directory*/*filename* and return the path."""
    p = directory / filename
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def _valid_payload(entry_id: str = "villa", major: int = 1) -> dict:
    return {
        "metadata": {
            "id": entry_id,
            "version": f"v{major}.0.0",
            "type": "residential",
            "title": f"{entry_id} rule",
            "description": "Test entry",
            "owner": "rudra",
        },
        "body": {
            "purpose": "Test residential unit",
            "planning_philosophy": "Efficient use of space",
            "occupancy": {
                "typical_occupants": 4,
                "occupant_profile": "nuclear family",
            },
            "required_spaces": [
                {
                    "name": "living_room",
                    "area": {"min_sqft": 150, "max_sqft": 300},
                }
            ],
        },
    }


def _loader(tmp_path: Path) -> KnowledgeLoader:
    return KnowledgeLoader(root_directory=tmp_path, registry=KnowledgeRegistry())


# ── load_file ─────────────────────────────────────────────────────────────────


def test_load_single_file(tmp_path):
    p = _write(tmp_path, "villa.v1.json", _valid_payload("villa", 1))
    loader = _loader(tmp_path)
    entry = loader.load_file(p)
    assert entry.metadata.id == "villa"
    assert entry.metadata.version == "v1.0.0"
    assert entry.source_path == str(p.resolve())


def test_load_file_registers_entry(tmp_path):
    p = _write(tmp_path, "villa.v1.json", _valid_payload("villa", 1))
    loader = _loader(tmp_path)
    loader.load_file(p)
    assert loader.find("villa") is not None


def test_load_file_missing_body(tmp_path):
    payload = _valid_payload("villa", 1)
    del payload["body"]
    p = _write(tmp_path, "villa.v1.json", payload)
    loader = _loader(tmp_path)
    with pytest.raises(KnowledgeValidationError, match="missing 'body'"):
        loader.load_file(p)


def test_load_file_missing_metadata(tmp_path):
    payload = _valid_payload("villa", 1)
    del payload["metadata"]
    p = _write(tmp_path, "villa.v1.json", payload)
    loader = _loader(tmp_path)
    with pytest.raises(KnowledgeValidationError, match="missing 'metadata'"):
        loader.load_file(p)


def test_load_file_invalid_metadata_schema(tmp_path):
    payload = {"metadata": {"id": "villa"}, "body": {}}  # missing required fields
    p = _write(tmp_path, "villa.v1.json", payload)
    loader = _loader(tmp_path)
    with pytest.raises(KnowledgeValidationError, match="Metadata validation failed"):
        loader.load_file(p)


def test_load_file_unknown_type_raises(tmp_path):
    payload = _valid_payload("villa", 1)
    payload["metadata"]["type"] = "commercial"  # not yet registered
    p = _write(tmp_path, "villa.v1.json", payload)
    loader = _loader(tmp_path)
    with pytest.raises(KnowledgeValidationError, match="Unknown knowledge type"):
        loader.load_file(p)


def test_load_file_invalid_body_schema_raises(tmp_path):
    payload = _valid_payload("villa", 1)
    payload["body"] = {"purpose": "ok"}  # missing required residential fields
    p = _write(tmp_path, "villa.v1.json", payload)
    loader = _loader(tmp_path)
    with pytest.raises(KnowledgeValidationError, match="Body validation failed"):
        loader.load_file(p)


def test_load_file_body_is_typed(tmp_path):
    from app.design_knowledge.knowledge.body_models import ResidentialKnowledgeBody

    p = _write(tmp_path, "villa.v1.json", _valid_payload("villa", 1))
    loader = _loader(tmp_path)
    entry = loader.load_file(p)
    assert isinstance(entry.body, ResidentialKnowledgeBody)


# ── filename validation ───────────────────────────────────────────────────────


def test_invalid_filename_no_version(tmp_path):
    p = _write(tmp_path, "villa.json", _valid_payload("villa", 1))
    loader = _loader(tmp_path)
    with pytest.raises(KnowledgeValidationError, match="Invalid filename"):
        loader.load_file(p)


def test_invalid_filename_wrong_extension(tmp_path):
    p = _write(tmp_path, "villa.v1.txt", _valid_payload("villa", 1))
    p = p.rename(tmp_path / "villa.v1.txt")
    loader = _loader(tmp_path)
    with pytest.raises(KnowledgeValidationError, match="Invalid filename"):
        loader.load_file(p)


def test_filename_major_mismatch(tmp_path):
    # filename says v1 but metadata says v2.0.0
    payload = _valid_payload("villa", 2)
    p = _write(tmp_path, "villa.v1.json", payload)
    loader = _loader(tmp_path)
    with pytest.raises(KnowledgeValidationError, match="major version"):
        loader.load_file(p)


def test_filename_id_mismatch(tmp_path):
    # filename says 'villa' but metadata id is 'hospital'
    payload = _valid_payload("hospital", 1)
    p = _write(tmp_path, "villa.v1.json", payload)
    loader = _loader(tmp_path)
    with pytest.raises(KnowledgeValidationError, match="Filename id"):
        loader.load_file(p)


# ── load_directory ────────────────────────────────────────────────────────────


def test_load_directory_count(tmp_path):
    _write(tmp_path, "villa.v1.json", _valid_payload("villa", 1))
    _write(tmp_path, "hospital.v1.json", _valid_payload("hospital", 1))
    loader = _loader(tmp_path)
    count = loader.load_directory(tmp_path)
    assert count == 2


def test_load_directory_skips_non_dkb_files(tmp_path):
    _write(tmp_path, "villa.v1.json", _valid_payload("villa", 1))
    (tmp_path / "README.json").write_text("{}", encoding="utf-8")
    loader = _loader(tmp_path)
    count = loader.load_directory(tmp_path)
    assert count == 1


def test_load_directory_recursive(tmp_path):
    sub = tmp_path / "residential"
    sub.mkdir()
    _write(tmp_path, "hospital.v1.json", _valid_payload("hospital", 1))
    _write(sub, "villa.v1.json", _valid_payload("villa", 1))
    loader = _loader(tmp_path)
    count = loader.load_directory(tmp_path)
    assert count == 2


def test_load_directory_missing_raises(tmp_path):
    loader = _loader(tmp_path)
    with pytest.raises(KnowledgeLoaderError, match="Directory not found"):
        loader.load_directory(tmp_path / "nonexistent")


# ── duplicate detection ───────────────────────────────────────────────────────


def test_duplicate_id_and_version_raises(tmp_path):
    p = _write(tmp_path, "villa.v1.json", _valid_payload("villa", 1))
    loader = _loader(tmp_path)
    loader.load_file(p)
    with pytest.raises(KnowledgeDuplicateError, match="Duplicate entry"):
        loader.load_file(p)


# ── versioning ────────────────────────────────────────────────────────────────


def test_list_versions(tmp_path):
    _write(tmp_path, "villa.v1.json", _valid_payload("villa", 1))
    _write(tmp_path, "villa.v2.json", _valid_payload("villa", 2))
    loader = _loader(tmp_path)
    loader.load_directory(tmp_path)
    versions = loader.list_versions("villa")
    assert versions == ["v1.0.0", "v2.0.0"]


def test_list_versions_empty_for_unknown(tmp_path):
    loader = _loader(tmp_path)
    assert loader.list_versions("ghost") == []


def test_latest_returns_highest_version(tmp_path):
    _write(tmp_path, "villa.v1.json", _valid_payload("villa", 1))
    _write(tmp_path, "villa.v2.json", _valid_payload("villa", 2))
    loader = _loader(tmp_path)
    loader.load_directory(tmp_path)
    entry = loader.latest("villa")
    assert entry.metadata.version == "v2.0.0"


def test_latest_returns_none_for_unknown(tmp_path):
    loader = _loader(tmp_path)
    assert loader.latest("ghost") is None


# ── cache ─────────────────────────────────────────────────────────────────────


def test_cache_hit_skips_reparse(tmp_path):
    p = _write(tmp_path, "villa.v1.json", _valid_payload("villa", 1))
    loader = _loader(tmp_path)
    entry1 = loader._load_and_cache(p)
    # Overwrite file content — mtime unchanged on fast filesystems,
    # but we force a cache hit by checking object identity.
    entry2 = loader._load_and_cache(p)
    assert entry1 is entry2  # same object returned from cache


def test_cache_invalidated_on_mtime_change(tmp_path):
    p = _write(tmp_path, "villa.v1.json", _valid_payload("villa", 1))
    loader = _loader(tmp_path)
    entry1 = loader._load_and_cache(p)

    # Force a detectable mtime change
    time.sleep(0.05)
    p.write_text(json.dumps(_valid_payload("villa", 1)), encoding="utf-8")

    entry2 = loader._load_and_cache(p)
    assert entry1 is not entry2  # re-parsed after mtime change


# ── reload ────────────────────────────────────────────────────────────────────


def test_reload_repopulates_registry(tmp_path):
    _write(tmp_path, "villa.v1.json", _valid_payload("villa", 1))
    loader = _loader(tmp_path)
    loader.load_directory(tmp_path)
    assert loader.find("villa") is not None

    count = loader.reload()
    assert count == 1
    assert loader.find("villa") is not None


def test_reload_clears_then_reloads(tmp_path):
    _write(tmp_path, "villa.v1.json", _valid_payload("villa", 1))
    loader = _loader(tmp_path)
    loader.load_directory(tmp_path)

    # Add a new file before reload
    _write(tmp_path, "hospital.v1.json", _valid_payload("hospital", 1))
    count = loader.reload()
    assert count == 2
    assert loader.find("hospital") is not None
