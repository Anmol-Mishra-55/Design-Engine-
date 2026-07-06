"""Tests for KnowledgeRegistry."""
import pytest
from app.design_knowledge.knowledge.body_models import BaseKnowledgeBody
from app.design_knowledge.knowledge.models import KnowledgeEntry, KnowledgeMetadata, KnowledgeStatus
from app.design_knowledge.knowledge.registry import KnowledgeRegistry

_STUB_BODY = BaseKnowledgeBody(purpose="stub", planning_philosophy="stub")


def _make_entry(entry_id: str, version: str = "v1.0.0") -> KnowledgeEntry:
    meta = KnowledgeMetadata(
        id=entry_id,
        version=version,
        type="rule",
        title=f"Entry {entry_id}",
        description="Test entry",
        owner="rudra",
        status=KnowledgeStatus.ACTIVE,
    )
    return KnowledgeEntry(metadata=meta, body=_STUB_BODY)


@pytest.fixture
def registry() -> KnowledgeRegistry:
    return KnowledgeRegistry()


# ── register ──────────────────────────────────────────────────────────────────


def test_register_single(registry):
    entry = _make_entry("e-001")
    registry.register(entry)
    assert registry.exists("e-001")


def test_register_duplicate_raises(registry):
    entry = _make_entry("e-001")
    registry.register(entry)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(entry)


# ── unregister ────────────────────────────────────────────────────────────────


def test_unregister(registry):
    registry.register(_make_entry("e-002"))
    registry.unregister("e-002")
    assert not registry.exists("e-002")


def test_unregister_missing_raises(registry):
    with pytest.raises(KeyError):
        registry.unregister("nonexistent")


# ── exists / get ──────────────────────────────────────────────────────────────


def test_exists_false_for_unknown(registry):
    assert not registry.exists("ghost")


def test_get_returns_entry(registry):
    entry = _make_entry("e-003")
    registry.register(entry)
    result = registry.get("e-003")
    assert result is entry


def test_get_returns_none_for_missing(registry):
    assert registry.get("missing") is None


# ── list ──────────────────────────────────────────────────────────────────────


def test_list_empty(registry):
    assert registry.list() == []


def test_list_multiple(registry):
    for i in range(3):
        registry.register(_make_entry(f"e-{i:03d}"))
    assert len(registry.list()) == 3


# ── clear ─────────────────────────────────────────────────────────────────────


def test_clear(registry):
    registry.register(_make_entry("e-004"))
    registry.register(_make_entry("e-005"))
    registry.clear()
    assert registry.list() == []
    assert not registry.exists("e-004")


# ── source_path provenance ────────────────────────────────────────────────────


def test_source_path_stored_and_retrievable(registry):
    entry = _make_entry("e-006")
    entry = entry.model_copy(update={"source_path": "/dkb/rules/e-006.json"})
    registry.register(entry)
    assert registry.get("e-006").source_path == "/dkb/rules/e-006.json"


def test_source_path_defaults_none(registry):
    entry = _make_entry("e-007")
    registry.register(entry)
    assert registry.get("e-007").source_path is None


# ── __len__ / __repr__ ────────────────────────────────────────────────────────


def test_len(registry):
    assert len(registry) == 0
    registry.register(_make_entry("e-008"))
    assert len(registry) == 1


def test_repr(registry):
    assert repr(registry) == "KnowledgeRegistry(entries=0)"
    registry.register(_make_entry("e-009"))
    assert repr(registry) == "KnowledgeRegistry(entries=1)"
