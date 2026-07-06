"""
DKB Knowledge Loader

Boundary contract
─────────────────
READS    : JSON files from disk matching the pattern <id>.v<major>.json
PRODUCES : KnowledgeEntry objects stamped with source_path
WRITES   : into KnowledgeRegistry via registry.register()
NEVER    : compiles, validates design rules, or calls external services

Pipeline position
─────────────────
  JSON files → KnowledgeLoader → KnowledgeRegistry → Compiler

Filename convention
───────────────────
  <id>.v<major>.json
  Examples: villa.v1.json  |  hospital.v2.json

  The major version in the filename must match the major component of
  the 'version' field inside the JSON metadata block.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import ValidationError

from .body_models import BaseKnowledgeBody, ResidentialKnowledgeBody
from .models import KnowledgeEntry, KnowledgeMetadata, KnowledgeVersion
from .registry import KnowledgeRegistry

# ── Body model dispatch registry ──────────────────────────────────────────────
# Maps metadata.type → the concrete BaseKnowledgeBody subclass.
# To add a new domain: insert one line here. Nothing else changes.

BODY_MODEL_REGISTRY: dict[str, type[BaseKnowledgeBody]] = {
    "residential": ResidentialKnowledgeBody,
}

# ── Custom exceptions ─────────────────────────────────────────────────────────


class KnowledgeLoaderError(Exception):
    """Raised for I/O or structural problems during loading."""


class KnowledgeValidationError(KnowledgeLoaderError):
    """Raised when a JSON file fails metadata or schema validation."""


class KnowledgeDuplicateError(KnowledgeLoaderError):
    """Raised when the same id + version is loaded more than once."""


# ── Filename pattern ──────────────────────────────────────────────────────────

_FILENAME_RE = re.compile(r"^(?P<id>.+)\.v(?P<major>\d+)\.json$")


def _parse_filename(filename: str) -> Tuple[str, int]:
    """
    Parse '<id>.v<major>.json' and return (id, major).
    Raises KnowledgeValidationError on mismatch.
    """
    match = _FILENAME_RE.match(filename)
    if not match:
        raise KnowledgeValidationError(f"Invalid filename '{filename}'. Expected <id>.v<major>.json")
    return match.group("id"), int(match.group("major"))


# ── Cache entry ───────────────────────────────────────────────────────────────


class _CacheEntry:
    """Holds a parsed KnowledgeEntry alongside the mtime it was read at."""

    __slots__ = ("entry", "mtime")

    def __init__(self, entry: KnowledgeEntry, mtime: float) -> None:
        self.entry = entry
        self.mtime = mtime


# ── Loader ────────────────────────────────────────────────────────────────────


class KnowledgeLoader:
    """
    Loads versioned DKB JSON files, validates them, caches them, and
    registers them into a KnowledgeRegistry.

    Parameters
    ----------
    root_directory:
        Base directory used as the default search root.
    registry:
        The KnowledgeRegistry that receives every successfully loaded entry.
    """

    def __init__(self, root_directory: Path, registry: KnowledgeRegistry) -> None:
        self._root = Path(root_directory)
        self._registry = registry

        # path (str) → _CacheEntry
        self._cache: Dict[str, _CacheEntry] = {}

        # (id, version_str) → KnowledgeEntry  — full version index
        self._version_index: Dict[Tuple[str, str], KnowledgeEntry] = {}

        # directories passed to load_directory() — needed for reload()
        self._loaded_directories: List[Path] = []

    # ── public API ────────────────────────────────────────────────────────────

    def load_file(self, path: Path) -> KnowledgeEntry:
        """
        Load, validate, cache, and register a single JSON file.

        Returns the KnowledgeEntry on success.
        Raises KnowledgeValidationError, KnowledgeDuplicateError, or
        KnowledgeLoaderError on failure.
        """
        path = Path(path)
        entry = self._load_and_cache(path)
        self._register(entry)
        return entry

    def load_directory(self, directory: Path) -> int:
        """
        Recursively load all '*.v<major>.json' files under *directory*.

        Registers every valid entry.  Returns the count of newly loaded
        entries.  The directory is remembered for reload().
        """
        directory = Path(directory)
        if not directory.is_dir():
            raise KnowledgeLoaderError(f"Directory not found: {directory}")

        if directory not in self._loaded_directories:
            self._loaded_directories.append(directory)

        count = 0
        for json_path in sorted(directory.rglob("*.json")):
            if not _FILENAME_RE.match(json_path.name):
                continue  # skip non-DKB files silently
            entry = self._load_and_cache(json_path)
            self._register(entry)
            count += 1
        return count

    def reload(self) -> int:
        """
        Clear the registry and version index, then re-load every directory
        that was previously passed to load_directory().

        The file cache is preserved so unchanged files are not re-parsed.
        Returns the total count of reloaded entries.
        """
        self._registry.clear()
        self._version_index.clear()

        total = 0
        dirs = list(self._loaded_directories)
        self._loaded_directories.clear()
        for directory in dirs:
            total += self.load_directory(directory)
        return total

    def find(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """Return the registered KnowledgeEntry for *entry_id*, or None."""
        return self._registry.get(entry_id)

    def list_versions(self, entry_id: str) -> List[str]:
        """
        Return all version strings loaded for *entry_id*, sorted ascending.
        """
        versions = [ver for (eid, ver) in self._version_index if eid == entry_id]
        return sorted(versions, key=lambda v: KnowledgeVersion.parse(v)._tuple())

    def latest(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """
        Return the KnowledgeEntry with the highest version for *entry_id*.
        Returns None if no versions are loaded for that id.
        """
        versions = self.list_versions(entry_id)
        if not versions:
            return None
        newest = versions[-1]
        return self._version_index.get((entry_id, newest))

    # ── internal helpers ──────────────────────────────────────────────────────

    def _load_and_cache(self, path: Path) -> KnowledgeEntry:
        """
        Parse *path* into a KnowledgeEntry, using the cache when the file
        has not changed since the last read.
        """
        path_str = str(path.resolve())

        try:
            mtime = os.path.getmtime(path)
        except OSError as exc:
            raise KnowledgeLoaderError(f"Cannot access file: {path}") from exc

        cached = self._cache.get(path_str)
        if cached is not None and cached.mtime == mtime:
            return cached.entry

        entry = self._parse(path)
        self._cache[path_str] = _CacheEntry(entry, mtime)
        return entry

    def _parse(self, path: Path) -> KnowledgeEntry:
        """Read, validate, and construct a KnowledgeEntry from *path*."""
        # ── filename validation ───────────────────────────────────────────────
        file_id, file_major = _parse_filename(path.name)

        # ── read JSON ─────────────────────────────────────────────────────────
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise KnowledgeLoaderError(f"Cannot read '{path}': {exc}") from exc

        if not isinstance(raw, dict):
            raise KnowledgeValidationError(f"'{path}' must contain a JSON object.")

        # ── presence checks ───────────────────────────────────────────────────
        if "metadata" not in raw:
            raise KnowledgeValidationError(f"'{path}' is missing 'metadata'.")
        if "body" not in raw:
            raise KnowledgeValidationError(f"'{path}' is missing 'body'.")

        # ── metadata schema ───────────────────────────────────────────────────
        try:
            metadata = KnowledgeMetadata(**raw["metadata"])
        except (ValidationError, TypeError) as exc:
            raise KnowledgeValidationError(f"Metadata validation failed in '{path}': {exc}") from exc

        # ── version consistency: filename major vs metadata version ───────────
        try:
            parsed_ver = KnowledgeVersion.parse(metadata.version)
        except ValueError as exc:
            raise KnowledgeValidationError(str(exc)) from exc

        if parsed_ver.major != file_major:
            raise KnowledgeValidationError(
                f"Filename major version (v{file_major}) does not match "
                f"metadata version ({metadata.version}) in '{path}'."
            )

        # ── id consistency: filename id vs metadata id ────────────────────────
        if metadata.id != file_id:
            raise KnowledgeValidationError(
                f"Filename id '{file_id}' does not match metadata id " f"'{metadata.id}' in '{path}'."
            )

        # ── body model dispatch and validation ────────────────────────────────
        body_cls = BODY_MODEL_REGISTRY.get(metadata.type)
        if body_cls is None:
            raise KnowledgeValidationError(
                f"Unknown knowledge type '{metadata.type}' in '{path}'. "
                f"Registered types: {list(BODY_MODEL_REGISTRY)}"
            )
        try:
            body = body_cls(**raw["body"])
        except (ValidationError, TypeError) as exc:
            raise KnowledgeValidationError(f"Body validation failed in '{path}': {exc}") from exc

        return KnowledgeEntry(
            metadata=metadata,
            body=body,
            source_path=str(path.resolve()),
        )

    def _register(self, entry: KnowledgeEntry) -> None:
        """
        Add *entry* to the version index and the registry.

        The registry holds the latest version per id (last-write-wins when
        loading a directory in sorted order).  The version index holds every
        version ever loaded.
        """
        key = (entry.metadata.id, entry.metadata.version)

        if key in self._version_index:
            raise KnowledgeDuplicateError(
                f"Duplicate entry: id='{entry.metadata.id}' " f"version='{entry.metadata.version}' already loaded."
            )

        self._version_index[key] = entry

        # Registry stores one entry per id — unregister the older one first
        # so the registry always reflects the latest loaded version.
        if self._registry.exists(entry.metadata.id):
            self._registry.unregister(entry.metadata.id)

        self._registry.register(entry)
