"""
DKB Runtime Exceptions

All exceptions raised by DKBRuntime are subclasses of DKBRuntimeError,
so callers can catch the base class or specific subtypes.
"""
from __future__ import annotations


class DKBRuntimeError(Exception):
    """Base class for all DKB Runtime errors."""


class DKBRuntimeNoMatchError(DKBRuntimeError):
    """
    Raised when the search engine finds no matching KnowledgeEntry
    for the given topic.
    """


class DKBRuntimeCompilerError(DKBRuntimeError):
    """
    Raised when the DesignSpecCompiler fails to compile the resolved entry.
    Wraps DesignSpecCompilerError with runtime context.
    """


class DKBRuntimeValidationError(DKBRuntimeError):
    """
    Raised when the ValidationEngine cannot validate the specification
    (e.g. no validator registered for the project type).
    Wraps ValidationEngineError with runtime context.
    Note: a spec that fails validation rules is NOT an exception —
    it returns a DKBRuntimeResult with valid=False.
    """


class DKBRuntimeNotInitializedError(DKBRuntimeError):
    """
    Raised when DKBRuntime.execute() is called before the search index
    has been built (i.e. before index() or load() is called).
    """
