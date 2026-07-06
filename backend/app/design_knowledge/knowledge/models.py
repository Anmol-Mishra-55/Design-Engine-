"""
DKB Knowledge Models
Rudra Governance — version format: vMAJOR.MINOR.PATCH
"""
from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from .body_models import BaseKnowledgeBody


class KnowledgeStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class KnowledgeVersion:
    """Represents a semantic version in vMAJOR.MINOR.PATCH format."""

    _PATTERN = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")

    def __init__(self, major: int, minor: int, patch: int) -> None:
        self.major = major
        self.minor = minor
        self.patch = patch

    @classmethod
    def parse(cls, version_str: str) -> "KnowledgeVersion":
        """Parse a version string like 'v1.2.3' into a KnowledgeVersion."""
        match = cls._PATTERN.match(version_str)
        if not match:
            raise ValueError(f"Invalid version format '{version_str}'. Expected vMAJOR.MINOR.PATCH")
        return cls(int(match.group(1)), int(match.group(2)), int(match.group(3)))

    def to_string(self) -> str:
        """Return the canonical version string."""
        return f"v{self.major}.{self.minor}.{self.patch}"

    def _tuple(self) -> tuple:
        return (self.major, self.minor, self.patch)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, KnowledgeVersion) and self._tuple() == other._tuple()

    def __lt__(self, other: "KnowledgeVersion") -> bool:
        return self._tuple() < other._tuple()

    def __le__(self, other: "KnowledgeVersion") -> bool:
        return self._tuple() <= other._tuple()

    def __gt__(self, other: "KnowledgeVersion") -> bool:
        return self._tuple() > other._tuple()

    def __ge__(self, other: "KnowledgeVersion") -> bool:
        return self._tuple() >= other._tuple()

    def __repr__(self) -> str:
        return f"KnowledgeVersion({self.to_string()})"


class KnowledgeMetadata(BaseModel):
    """Metadata header for every knowledge entry."""

    id: str
    version: str = Field(..., pattern=r"^v\d+\.\d+\.\d+$")
    type: str
    title: str
    description: str
    owner: str
    status: KnowledgeStatus = KnowledgeStatus.DRAFT
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    consumers: List[str] = Field(default_factory=list)


class KnowledgeEntry(BaseModel):
    """
    A single unit of design knowledge: metadata + typed body.

    body is always a validated BaseKnowledgeBody subclass — never a raw dict.
    The Loader is responsible for parsing JSON and casting to the correct
    domain body model before constructing this object.

    source_path is stamped by the Loader when an entry is read from disk.
    The Registry stores it as-is. The Compiler uses it as a cache key.
    Neither the Registry nor the Compiler ever writes to this field.
    """

    metadata: KnowledgeMetadata
    body: BaseKnowledgeBody
    source_path: Optional[str] = None  # set by Loader only
