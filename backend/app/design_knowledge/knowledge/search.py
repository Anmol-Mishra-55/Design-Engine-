"""
DKB Knowledge Search

Boundary contract
─────────────────
ACCEPTS  : KnowledgeEntry objects from KnowledgeRegistry
PRODUCES : SearchResult objects ranked by relevance
NEVER    : loads files, writes to registry, compiles design specs

Pipeline position
─────────────────
  KnowledgeRegistry → KnowledgeSearchEngine → Compiler

Provider contract
─────────────────
  SearchProvider is the only extension point.
  KnowledgeSearchEngine never instantiates a provider — it receives one.
  Swapping TF-IDF for embeddings later requires only a new SearchProvider
  subclass; the engine, compiler, and Prompt Runner are unaffected.

SearchResult.matched_on
───────────────────────
  Maps field name → list of matched tokens.
  Example: {"title": ["villa"], "tags": ["luxury", "residential"]}
  Used for QA, debugging, and governance tracing.
"""
from __future__ import annotations

import math
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .models import KnowledgeEntry

# ── SearchResult ──────────────────────────────────────────────────────────────


@dataclass
class SearchResult:
    """
    A single ranked result returned by a SearchProvider.

    Attributes
    ----------
    entry:      The matched KnowledgeEntry.
    score:      Relevance score, normalised to [0.0, 1.0].
    matched_on: Field-name → matched tokens, e.g.
                {"title": ["villa"], "tags": ["luxury"]}.
    """

    entry: KnowledgeEntry
    score: float
    matched_on: Dict[str, List[str]] = field(default_factory=dict)


# ── SearchProvider ABC ────────────────────────────────────────────────────────


class SearchProvider(ABC):
    """
    Abstract base for all DKB retrieval strategies.

    Implementors must be synchronous and stateless between calls.
    The index is rebuilt by calling index() with the full entry list.
    """

    @abstractmethod
    def index(self, entries: List[KnowledgeEntry]) -> None:
        """Build or rebuild the internal index from *entries*."""

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """
        Return up to *top_k* results ranked by relevance to *query*.
        Returns an empty list when no entries are indexed.
        """


# ── shared tokeniser ──────────────────────────────────────────────────────────


def _tokenise(text: str) -> List[str]:
    """Lowercase, strip punctuation, split on whitespace."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _entry_fields(entry: KnowledgeEntry) -> Dict[str, List[str]]:
    """Return tokenised field buckets for a KnowledgeEntry."""
    m = entry.metadata
    return {
        "title": _tokenise(m.title),
        "description": _tokenise(m.description),
        "tags": _tokenise(" ".join(m.tags)),
        "type": _tokenise(m.type),
    }


# ── KeywordSearchProvider ─────────────────────────────────────────────────────


class KeywordSearchProvider(SearchProvider):
    """
    Exact-token keyword matching.

    Score = (number of query tokens matched) / (total query tokens).
    Deterministic — identical inputs always produce identical outputs.
    Intended for unit tests, debugging, and governance audits.
    """

    def __init__(self) -> None:
        self._entries: List[KnowledgeEntry] = []

    def index(self, entries: List[KnowledgeEntry]) -> None:
        self._entries = list(entries)

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        query_tokens = set(_tokenise(query))
        if not query_tokens or not self._entries:
            return []

        results: List[SearchResult] = []
        for entry in self._entries:
            fields = _entry_fields(entry)
            matched_on: Dict[str, List[str]] = {}
            total_hits = 0

            for field_name, tokens in fields.items():
                hits = [t for t in tokens if t in query_tokens]
                if hits:
                    matched_on[field_name] = hits
                    total_hits += len(hits)

            if total_hits:
                score = min(total_hits / len(query_tokens), 1.0)
                results.append(SearchResult(entry=entry, score=score, matched_on=matched_on))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]


# ── TFIDFSearchProvider ───────────────────────────────────────────────────────


class TFIDFSearchProvider(SearchProvider):
    """
    TF-IDF ranked retrieval — default production provider.

    Each entry's indexed text is the concatenation of:
        title (weight ×3) + tags (weight ×2) + description + type

    Weights are applied by repeating tokens before IDF calculation,
    so no external library is required.

    Score is cosine similarity between the query TF vector and each
    document TF-IDF vector, normalised to [0.0, 1.0].
    """

    def __init__(self) -> None:
        self._entries: List[KnowledgeEntry] = []
        # entry index → {token: tfidf_weight}
        self._tfidf: List[Dict[str, float]] = []
        self._idf: Dict[str, float] = {}

    def index(self, entries: List[KnowledgeEntry]) -> None:
        self._entries = list(entries)
        self._build_index()

    def _weighted_tokens(self, entry: KnowledgeEntry) -> List[str]:
        """Return a token list with field weights applied via repetition."""
        f = _entry_fields(entry)
        return f["title"] * 3 + f["tags"] * 2 + f["description"] + f["type"]

    def _build_index(self) -> None:
        n = len(self._entries)
        if n == 0:
            self._tfidf = []
            self._idf = {}
            return

        # term frequency per document
        tf_docs: List[Dict[str, float]] = []
        for entry in self._entries:
            tokens = self._weighted_tokens(entry)
            counts: Dict[str, int] = defaultdict(int)
            for t in tokens:
                counts[t] += 1
            total = len(tokens) or 1
            tf_docs.append({t: c / total for t, c in counts.items()})

        # document frequency
        df: Dict[str, int] = defaultdict(int)
        for tf in tf_docs:
            for term in tf:
                df[term] += 1

        # IDF with smoothing
        self._idf = {term: math.log((n + 1) / (count + 1)) + 1.0 for term, count in df.items()}

        # TF-IDF vectors
        self._tfidf = [{term: tf_val * self._idf.get(term, 1.0) for term, tf_val in tf.items()} for tf in tf_docs]

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        query_tokens = _tokenise(query)
        if not query_tokens or not self._entries:
            return []

        # query TF vector (no IDF weighting on query side — standard practice)
        q_counts: Dict[str, int] = defaultdict(int)
        for t in query_tokens:
            q_counts[t] += 1
        q_total = len(query_tokens)
        q_tf = {t: c / q_total for t, c in q_counts.items()}

        results: List[SearchResult] = []
        for i, entry in enumerate(self._entries):
            doc_vec = self._tfidf[i]
            fields = _entry_fields(entry)

            # cosine similarity (query vec · doc vec) / (|q| * |d|)
            dot = sum(q_tf[t] * doc_vec.get(t, 0.0) for t in q_tf)
            if dot == 0.0:
                continue

            q_norm = math.sqrt(sum(v**2 for v in q_tf.values()))
            d_norm = math.sqrt(sum(v**2 for v in doc_vec.values()))
            denom = q_norm * d_norm
            score = dot / denom if denom else 0.0

            # matched_on: which field tokens overlapped with the query
            q_set = set(q_tf)
            matched_on: Dict[str, List[str]] = {}
            for field_name, tokens in fields.items():
                hits = [t for t in tokens if t in q_set]
                if hits:
                    matched_on[field_name] = hits

            results.append(SearchResult(entry=entry, score=score, matched_on=matched_on))

        # normalise scores to [0, 1] relative to the top result
        if results:
            results.sort(key=lambda r: r.score, reverse=True)
            top_score = results[0].score
            if top_score > 0:
                for r in results:
                    r.score = r.score / top_score

        return results[:top_k]


# ── KnowledgeSearchEngine ─────────────────────────────────────────────────────


class KnowledgeSearchEngine:
    """
    Provider-agnostic search engine for the DKB.

    The engine owns no retrieval logic — it delegates entirely to the
    injected SearchProvider.  Swapping providers never requires changes
    here, in the Compiler, or in the Prompt Runner.

    Parameters
    ----------
    provider:
        Any SearchProvider implementation.  Injected at construction time.
    """

    def __init__(self, provider: SearchProvider) -> None:
        self._provider = provider
        self._entries: List[KnowledgeEntry] = []

    def index(self, entries: List[KnowledgeEntry]) -> None:
        """Build the search index from *entries*."""
        self._entries = list(entries)
        self._provider.index(self._entries)

    def reindex(self, entries: List[KnowledgeEntry]) -> None:
        """Replace the current index with a fresh one built from *entries*."""
        self.index(entries)

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Return up to *top_k* ranked SearchResult objects for *query*."""
        return self._provider.search(query, top_k=top_k)

    def resolve(self, query: str) -> Optional[KnowledgeEntry]:
        """
        Return the single best-matching KnowledgeEntry for *query*.

        This is the method the Compiler calls.  It returns one canonical
        entry, not a ranked list.  Returns None when the index is empty
        or no entry scores above zero.
        """
        results = self._provider.search(query, top_k=1)
        return results[0].entry if results else None
