"""book-rag: transform books into local retrieval indexes.

Public seam — everything else in the package is an implementation detail:

    from book_rag import build_index, query

    index = build_index("moby-dick.epub")   # -> moby-dick.rag beside the source
    answer = query(index, "who is Ahab?")   # -> QueryOutput (JSON-serializable)

The tool retrieves; it never generates. The querying agent composes the
answer from verbatim chunks and cites their provenance (book + path).
"""

import sys
from pathlib import Path

from .chunk import chunk_sections
from .embed import Embedder, EmbedderError, OllamaEmbedder
from .epub import parse as _parse_epub
from .models import BookError, CorruptIndexError, QueryOutput, Result
from .retrieve import fuse
from .store import create_index, open_index, read_meta, search_keyword, search_vector, write_index
from .txt import parse as _parse_txt

__all__ = [
    "build_index",
    "query",
    "Embedder",
    "OllamaEmbedder",
    "BookError",
    "CorruptIndexError",
    "QueryOutput",
]

# Below this much extracted text, the book has nothing to index.
MIN_TEXT_CHARS = 100

# Embed in batches: fewer HTTP round-trips, and progress stays visible.
_EMBED_BATCH = 32

_PARSERS = {".epub": _parse_epub, ".txt": _parse_txt}


def build_index(
    source: str | Path,
    *,
    title: str | None = None,
    author: str | None = None,
    embedder: Embedder | None = None,
) -> Path:
    """Transform a book (EPUB/TXT) into an index file beside it.

    Rebuilding is idempotent: any existing ``<stem>.rag`` is replaced.
    Raises BookError for unsupported formats or books with no extractable
    text; EmbedderError if the embedder is unavailable (fail fast, before
    any partial work).
    """
    source = Path(source)
    if not source.is_file():
        raise BookError(f"no such file: {source}")

    parser = _PARSERS.get(source.suffix.lower())
    if parser is None:
        raise BookError(f"unsupported format {source.suffix!r} — v1 supports .epub and .txt")

    meta, sections = parser(source)
    if sum(len(s.text) for s in sections) < MIN_TEXT_CHARS:
        raise BookError(f"no extractable text in {source.name} (image-only or empty?)")

    chunks = chunk_sections(sections)
    if embedder is None:
        ollama = OllamaEmbedder()
        ollama.ensure_ready()  # fail fast, before any partial work
        embedder = ollama

    vectors = _embed_with_progress(embedder, [c.text for c in chunks])
    index_path = source.with_suffix(".rag")
    conn = create_index(index_path, embedder.dim)
    try:
        write_index(
            conn,
            title=title or meta.title or source.stem,
            author=author if author is not None else meta.author,
            dim=embedder.dim,
            chunks=chunks,
            vectors=vectors,
        )
    except BaseException:
        conn.close()
        index_path.unlink(missing_ok=True)  # never leave a half-written index
        raise
    conn.close()
    return index_path


def query(
    index: str | Path,
    question: str,
    *,
    top_k: int = 5,
    embedder: Embedder | None = None,
) -> QueryOutput:
    """Retrieve the best-matching verbatim chunks for a question.

    Hybrid by default (vector KNN + BM25, fused with RRF). If the embedder
    is unavailable at query time, degrades to keyword-only and says so via
    ``mode: "keyword-fallback"``.
    """
    index = Path(index)
    if not index.is_file():
        raise BookError(f"no such index: {index}")

    conn = open_index(index)
    try:
        meta = read_meta(conn)
        if embedder is None:
            embedder = OllamaEmbedder()

        mode = "hybrid"
        vector_hits: list[tuple[int, float]] = []
        try:
            [question_vector] = embedder.embed([question])
            vector_hits = search_vector(conn, question_vector, top_k * 2)
        except EmbedderError:
            mode = "keyword-fallback"

        keyword_hits = search_keyword(conn, question, top_k * 2)
        ranked = _fuse(vector_hits, keyword_hits, top_k)
        results = [
            _fetch_result(conn, rank, chunk_id, score)
            for rank, (chunk_id, score) in enumerate(ranked, start=1)
        ]
        return QueryOutput(
            book=meta.get("title") or index.stem,
            mode=mode,
            results=[r for r in results if r is not None],
        )
    finally:
        conn.close()


def _embed_with_progress(embedder: Embedder, texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(texts), _EMBED_BATCH):
        batch = texts[start : start + _EMBED_BATCH]
        vectors.extend(embedder.embed(batch))
        done = min(start + _EMBED_BATCH, len(texts))
        print(f"embedded {done}/{len(texts)}", file=sys.stderr)
    return vectors


def _fuse(
    vector_hits: list[tuple[int, float]],
    keyword_hits: list[tuple[int, float]],
    top_k: int,
) -> list[tuple[int, float]]:
    return fuse(vector_hits, keyword_hits, top_k)


def _fetch_result(conn, rank: int, chunk_id: int, score: float) -> Result | None:
    row = conn.execute("SELECT path, text FROM chunks WHERE id = ?", (chunk_id,)).fetchone()
    if row is None:  # cannot happen for ids we just ranked; defensive only
        return None
    return Result(rank=rank, score=score, path=row[0], text=row[1])
