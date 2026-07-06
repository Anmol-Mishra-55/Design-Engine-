"""
Tests for KnowledgeSearchEngine, TFIDFSearchProvider, KeywordSearchProvider.

No files on disk — entries are constructed directly.
All tests are deterministic and offline.
"""
import pytest
from app.design_knowledge.knowledge.body_models import BaseKnowledgeBody
from app.design_knowledge.knowledge.models import KnowledgeEntry, KnowledgeMetadata, KnowledgeStatus
from app.design_knowledge.knowledge.search import (
    KeywordSearchProvider,
    KnowledgeSearchEngine,
    SearchProvider,
    SearchResult,
    TFIDFSearchProvider,
)

_STUB_BODY = BaseKnowledgeBody(purpose="stub", planning_philosophy="stub")


# ── fixtures ──────────────────────────────────────────────────────────────────


def _make_entry(
    entry_id: str,
    title: str,
    description: str,
    tags: list[str] | None = None,
    entry_type: str = "layout_rule",
) -> KnowledgeEntry:
    meta = KnowledgeMetadata(
        id=entry_id,
        version="v1.0.0",
        type=entry_type,
        title=title,
        description=description,
        owner="rudra",
        status=KnowledgeStatus.ACTIVE,
        tags=tags or [],
    )
    return KnowledgeEntry(metadata=meta, body=_STUB_BODY)


VILLA = _make_entry(
    "villa",
    title="Villa Layout Rules",
    description="Luxury residential property with private garden",
    tags=["luxury", "residential", "villa"],
)

APARTMENT_1BHK = _make_entry(
    "apartment-1bhk",
    title="1BHK Apartment Layout",
    description="Compact urban apartment with one bedroom",
    tags=["apartment", "urban", "compact", "residential"],
)

HOSPITAL = _make_entry(
    "hospital",
    title="Hospital Design Rules",
    description="Medical facility with emergency and ICU wings",
    tags=["medical", "hospital", "emergency"],
)

ALL_ENTRIES = [VILLA, APARTMENT_1BHK, HOSPITAL]


# ── SearchResult dataclass ────────────────────────────────────────────────────


def test_search_result_fields():
    result = SearchResult(entry=VILLA, score=0.9, matched_on={"title": ["villa"]})
    assert result.entry is VILLA
    assert result.score == 0.9
    assert result.matched_on == {"title": ["villa"]}


def test_search_result_default_matched_on():
    result = SearchResult(entry=VILLA, score=0.5)
    assert result.matched_on == {}


# ── SearchProvider is abstract ────────────────────────────────────────────────


def test_search_provider_is_abstract():
    with pytest.raises(TypeError):
        SearchProvider()  # type: ignore[abstract]


# ── KeywordSearchProvider ─────────────────────────────────────────────────────


class TestKeywordSearchProvider:
    def _provider(self, entries=None) -> KeywordSearchProvider:
        p = KeywordSearchProvider()
        p.index(entries or ALL_ENTRIES)
        return p

    def test_exact_match_returns_result(self):
        p = self._provider()
        results = p.search("villa")
        assert len(results) >= 1
        assert results[0].entry.metadata.id == "villa"

    def test_no_match_returns_empty(self):
        p = self._provider()
        results = p.search("xyzzy")
        assert results == []

    def test_empty_index_returns_empty(self):
        p = KeywordSearchProvider()
        p.index([])
        assert p.search("villa") == []

    def test_top_k_respected(self):
        p = self._provider()
        results = p.search("residential", top_k=1)
        assert len(results) <= 1

    def test_matched_on_populated(self):
        p = self._provider()
        results = p.search("villa luxury")
        assert len(results) >= 1
        top = results[0]
        assert "villa" in top.matched_on.get("tags", []) or "villa" in top.matched_on.get("title", [])

    def test_score_between_0_and_1(self):
        p = self._provider()
        for r in p.search("luxury residential villa"):
            assert 0.0 <= r.score <= 1.0

    def test_results_sorted_descending(self):
        p = self._provider()
        results = p.search("luxury residential villa")
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_deterministic(self):
        p = self._provider()
        r1 = p.search("luxury apartment")
        r2 = p.search("luxury apartment")
        assert [r.entry.metadata.id for r in r1] == [r.entry.metadata.id for r in r2]


# ── TFIDFSearchProvider ───────────────────────────────────────────────────────


class TestTFIDFSearchProvider:
    def _provider(self, entries=None) -> TFIDFSearchProvider:
        p = TFIDFSearchProvider()
        p.index(entries or ALL_ENTRIES)
        return p

    def test_villa_query_returns_villa_first(self):
        p = self._provider()
        results = p.search("villa")
        assert results[0].entry.metadata.id == "villa"

    def test_hospital_query_returns_hospital_first(self):
        p = self._provider()
        results = p.search("hospital medical emergency")
        assert results[0].entry.metadata.id == "hospital"

    def test_apartment_query_returns_apartment_first(self):
        p = self._provider()
        results = p.search("apartment urban compact")
        assert results[0].entry.metadata.id == "apartment-1bhk"

    def test_no_match_returns_empty(self):
        p = self._provider()
        results = p.search("xyzzy")
        assert results == []

    def test_empty_index_returns_empty(self):
        p = TFIDFSearchProvider()
        p.index([])
        assert p.search("villa") == []

    def test_top_k_respected(self):
        p = self._provider()
        results = p.search("residential", top_k=1)
        assert len(results) <= 1

    def test_scores_normalised_to_1(self):
        p = self._provider()
        results = p.search("villa luxury residential")
        assert results[0].score == pytest.approx(1.0)

    def test_scores_between_0_and_1(self):
        p = self._provider()
        for r in p.search("luxury residential"):
            assert 0.0 <= r.score <= 1.0

    def test_results_sorted_descending(self):
        p = self._provider()
        results = p.search("luxury residential villa")
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_matched_on_populated(self):
        p = self._provider()
        results = p.search("luxury villa")
        assert len(results) >= 1
        assert results[0].matched_on  # non-empty dict

    def test_semantic_proximity(self):
        """'luxury apartment' should rank villa above hospital."""
        p = self._provider()
        results = p.search("luxury apartment")
        ids = [r.entry.metadata.id for r in results]
        assert "hospital" not in ids[:1]  # hospital should not be top result

    def test_reindex_replaces_old_entries(self):
        p = TFIDFSearchProvider()
        p.index([VILLA])
        assert p.search("hospital") == []
        p.index([HOSPITAL])
        results = p.search("hospital")
        assert results[0].entry.metadata.id == "hospital"


# ── KnowledgeSearchEngine ─────────────────────────────────────────────────────


class TestKnowledgeSearchEngine:
    def _engine(self, provider=None, entries=None) -> KnowledgeSearchEngine:
        engine = KnowledgeSearchEngine(provider or TFIDFSearchProvider())
        engine.index(entries or ALL_ENTRIES)
        return engine

    def test_search_returns_results(self):
        engine = self._engine()
        results = engine.search("villa")
        assert len(results) >= 1

    def test_search_top_k(self):
        engine = self._engine()
        results = engine.search("residential", top_k=1)
        assert len(results) <= 1

    def test_resolve_returns_single_entry(self):
        engine = self._engine()
        entry = engine.resolve("villa luxury")
        assert isinstance(entry, KnowledgeEntry)
        assert entry.metadata.id == "villa"

    def test_resolve_returns_none_on_empty_index(self):
        engine = KnowledgeSearchEngine(TFIDFSearchProvider())
        engine.index([])
        assert engine.resolve("villa") is None

    def test_resolve_returns_none_on_no_match(self):
        engine = self._engine()
        assert engine.resolve("xyzzy") is None

    def test_reindex_updates_results(self):
        engine = self._engine(entries=[VILLA])
        assert engine.resolve("hospital") is None
        engine.reindex([HOSPITAL])
        assert engine.resolve("hospital medical").metadata.id == "hospital"

    def test_engine_accepts_keyword_provider(self):
        """Engine must work with any SearchProvider — not just TF-IDF."""
        engine = self._engine(provider=KeywordSearchProvider())
        result = engine.resolve("villa")
        assert result is not None
        assert result.metadata.id == "villa"

    def test_provider_never_instantiated_by_engine(self):
        """Engine must receive provider via injection, not create it."""
        import inspect

        src = inspect.getsource(KnowledgeSearchEngine)
        assert "TFIDFSearchProvider()" not in src
        assert "KeywordSearchProvider()" not in src
