"""Core data types shared across the pipeline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BookMeta:
    """Identity of a book, as extracted from the source (or fallback)."""

    title: str | None = None
    author: str | None = None


@dataclass(frozen=True)
class Section:
    """A structurally bounded span of normalized text.

    ``path`` is the structural path (e.g. "Part II › Chapter 3");
    ``None`` means the section has no structure (flat text).
    ``page`` is the 1-based page number when the source format has pages
    (PDF); ``None`` for formats without a page concept (EPUB/TXT).
    """

    path: str | None
    text: str
    page: int | None = None


@dataclass(frozen=True)
class Chunk:
    """A unit of text stored in an index and returned by retrieval."""

    path: str | None
    text: str
    page: int | None = None


@dataclass(frozen=True)
class Result:
    """A retrieved chunk with its rank and fused score."""

    rank: int
    score: float
    path: str | None
    text: str
    page: int | None = None


@dataclass(frozen=True)
class QueryOutput:
    """The full answer to a query: book identity, retrieval mode, results."""

    book: str
    mode: str  # "hybrid" | "keyword-fallback"
    results: list[Result]


class BookError(Exception):
    """The source cannot be indexed (unsupported format, no extractable text)."""


class CorruptIndexError(Exception):
    """An index file exists but cannot be read (schema mismatch, corruption)."""
