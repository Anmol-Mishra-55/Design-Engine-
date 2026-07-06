"""
DKB Knowledge Registry

Boundary contract
─────────────────
ACCEPTS : KnowledgeEntry objects produced by the DKB Loader.
REFUSES : file paths, raw dicts, JSON strings — anything that is not
          an already-constructed KnowledgeEntry.

This class must never import pathlib, json, os, or any I/O library.
File loading belongs exclusively in knowledge/loader.py (Task 2).
Compilation belongs exclusively in knowledge/compiler.py (Task 3).

Pipeline position
─────────────────
  JSON files → Loader → KnowledgeRegistry → Compiler
"""
from typing import Dict, List, Optional

from .models import KnowledgeEntry


class KnowledgeRegistry:
    """In-memory registry for KnowledgeEntry objects."""

    def __init__(self) -> None:
        self._store: Dict[str, KnowledgeEntry] = {}

    def register(self, entry: KnowledgeEntry) -> None:
        """Register a KnowledgeEntry. Raises ValueError on duplicate id."""
        entry_id = entry.metadata.id
        if entry_id in self._store:
            raise ValueError(f"Knowledge entry '{entry_id}' is already registered.")
        self._store[entry_id] = entry

    def unregister(self, entry_id: str) -> None:
        """Remove an entry by id. Raises KeyError if not found."""
        if entry_id not in self._store:
            raise KeyError(f"Knowledge entry '{entry_id}' not found.")
        del self._store[entry_id]

    def exists(self, entry_id: str) -> bool:
        """Return True if an entry with the given id is registered."""
        return entry_id in self._store

    def get(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """Return the entry for the given id, or None if not found."""
        return self._store.get(entry_id)

    def list(self) -> List[KnowledgeEntry]:
        """Return all registered entries."""
        return list(self._store.values())

    def clear(self) -> None:
        """Remove all entries from the registry."""
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)

    def __repr__(self) -> str:
        return f"KnowledgeRegistry(entries={len(self._store)})"
