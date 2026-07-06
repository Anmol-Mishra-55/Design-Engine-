"""Tests for KnowledgeVersion, KnowledgeMetadata, and KnowledgeEntry."""
from datetime import datetime

import pytest
from app.design_knowledge.knowledge.body_models import BaseKnowledgeBody, ValidationRule
from app.design_knowledge.knowledge.models import KnowledgeEntry, KnowledgeMetadata, KnowledgeStatus, KnowledgeVersion


def _make_body(**overrides) -> BaseKnowledgeBody:
    defaults = dict(
        purpose="Test purpose",
        planning_philosophy="Test philosophy",
    )
    defaults.update(overrides)
    return BaseKnowledgeBody(**defaults)


# ── KnowledgeVersion ──────────────────────────────────────────────────────────


def test_version_parse_valid():
    v = KnowledgeVersion.parse("v1.2.3")
    assert v.major == 1
    assert v.minor == 2
    assert v.patch == 3


def test_version_to_string():
    v = KnowledgeVersion(2, 0, 1)
    assert v.to_string() == "v2.0.1"


def test_version_parse_invalid():
    with pytest.raises(ValueError):
        KnowledgeVersion.parse("1.2.3")  # missing 'v' prefix

    with pytest.raises(ValueError):
        KnowledgeVersion.parse("vX.Y.Z")


def test_version_equality():
    assert KnowledgeVersion.parse("v1.0.0") == KnowledgeVersion.parse("v1.0.0")
    assert KnowledgeVersion.parse("v1.0.0") != KnowledgeVersion.parse("v1.0.1")


def test_version_ordering():
    v1 = KnowledgeVersion.parse("v1.0.0")
    v2 = KnowledgeVersion.parse("v1.0.1")
    v3 = KnowledgeVersion.parse("v2.0.0")

    assert v1 < v2 < v3
    assert v3 > v2 > v1
    assert v1 <= v1
    assert v3 >= v3


# ── KnowledgeMetadata & KnowledgeEntry ───────────────────────────────────────


def _make_metadata(**overrides) -> KnowledgeMetadata:
    defaults = dict(
        id="test-001",
        version="v1.0.0",
        type="layout_rule",
        title="Test Rule",
        description="A test knowledge entry",
        owner="rudra",
        status=KnowledgeStatus.ACTIVE,
    )
    defaults.update(overrides)
    return KnowledgeMetadata(**defaults)


def test_metadata_defaults():
    meta = _make_metadata()
    assert meta.consumers == []
    assert isinstance(meta.created_at, datetime)
    assert isinstance(meta.updated_at, datetime)


def test_metadata_invalid_version():
    with pytest.raises(Exception):
        _make_metadata(version="1.0.0")  # missing 'v'


def test_knowledge_entry_structure():
    meta = _make_metadata()
    body = _make_body(purpose="no overlapping rooms")
    entry = KnowledgeEntry(metadata=meta, body=body)
    assert entry.metadata.id == "test-001"
    assert entry.body.purpose == "no overlapping rooms"


def test_knowledge_entry_body_is_typed():
    meta = _make_metadata()
    body = _make_body()
    entry = KnowledgeEntry(metadata=meta, body=body)
    assert isinstance(entry.body, BaseKnowledgeBody)


def test_knowledge_entry_source_path_default_none():
    meta = _make_metadata()
    body = _make_body()
    entry = KnowledgeEntry(metadata=meta, body=body)
    assert entry.source_path is None


def test_knowledge_entry_source_path_set_by_loader():
    meta = _make_metadata()
    body = _make_body()
    entry = KnowledgeEntry(metadata=meta, body=body, source_path="/dkb/rules/test.json")
    assert entry.source_path == "/dkb/rules/test.json"
