"""Index storage: one SQLite file per book (chunks + FTS5 + sqlite-vec).

The index is a single self-contained ``.rag`` file:
  - ``meta``        key/value (title, author, schema version, embedding dim)
  - ``chunks``      id, structural path, verbatim text
  - ``chunks_fts``  FTS5 over chunk text (keyword/BM25 retrieval)
  - ``chunks_vec``  sqlite-vec table of chunk embeddings (vector KNN)

No WAL mode — the index must stay one file, not three.
"""

from __future__ import annotations

import re
import sqlite3
import struct
from pathlib import Path

import sqlite_vec

from .models import CorruptIndexError

SCHEMA_VERSION = 2


def _connect(path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with the vec extension loaded."""
    conn = sqlite3.connect(str(path))
    conn.enable_load_extension(True)
    try:
        sqlite_vec.load(conn)
    finally:
        conn.enable_load_extension(False)
    return conn


def open_index(path: str | Path) -> sqlite3.Connection:
    """Open an existing index file with the vec extension loaded.

    Raises CorruptIndexError if the index is missing or was written by an
    incompatible schema version (e.g. a v1 index after the page-column
    migration). The recovery path is delete + reindex.
    """
    path = Path(path)
    if not path.is_file():
        raise CorruptIndexError(f"no such index: {path}")
    conn = _connect(path)
    try:
        version_row = conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
    except sqlite3.Error as e:
        conn.close()
        raise CorruptIndexError(f"unreadable index meta: {e}") from e
    if version_row is None:
        conn.close()
        raise CorruptIndexError("missing schema_version — not a book-rag index")
    if version_row[0] != str(SCHEMA_VERSION):
        conn.close()
        raise CorruptIndexError(
            f"index schema {version_row[0]} is incompatible (expected {SCHEMA_VERSION}) — "
            f"delete {path} and reindex"
        )
    return conn


def create_index(path: str | Path, dim: int) -> sqlite3.Connection:
    """Create a fresh index file (replacing any existing one)."""
    if not isinstance(dim, int) or dim <= 0:
        raise ValueError(f"dim must be a positive integer, got {dim!r}")
    path = Path(path)
    if path.exists():
        path.unlink()
    conn = _connect(path)
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute(
        "CREATE TABLE chunks (id INTEGER PRIMARY KEY, path TEXT, text TEXT, page INTEGER)"
    )
    conn.execute(
        "CREATE VIRTUAL TABLE chunks_fts USING fts5(text, content='chunks', content_rowid='id')"
    )
    conn.execute(f"CREATE VIRTUAL TABLE chunks_vec USING vec0(id INTEGER, embedding FLOAT[{dim}])")
    conn.commit()
    return conn


def write_index(
    conn: sqlite3.Connection,
    *,
    title: str,
    author: str | None,
    dim: int,
    chunks: list,
    vectors: list[list[float]],
) -> None:
    """Write metadata and all chunks (with FTS + vector rows)."""
    meta = {
        "title": title,
        "author": author or "",
        "schema_version": str(SCHEMA_VERSION),
        "dim": str(dim),
    }
    conn.executemany("INSERT OR REPLACE INTO meta VALUES (?, ?)", list(meta.items()))
    for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True), start=1):
        conn.execute(
            "INSERT INTO chunks (id, path, text, page) VALUES (?, ?, ?, ?)",
            (i, chunk.path, chunk.text, chunk.page),
        )
        conn.execute("INSERT INTO chunks_fts (rowid, text) VALUES (?, ?)", (i, chunk.text))
        conn.execute(
            "INSERT INTO chunks_vec (id, embedding) VALUES (?, ?)",
            (i, struct.pack(f"<{dim}f", *vector)),
        )
    conn.commit()


def read_meta(conn: sqlite3.Connection) -> dict[str, str]:
    return {k: v for k, v in conn.execute("SELECT key, value FROM meta")}


def search_vector(
    conn: sqlite3.Connection, embedding: list[float], k: int
) -> list[tuple[int, float]]:
    """Nearest chunks by L2 distance (lower = closer)."""
    blob = struct.pack(f"<{len(embedding)}f", *embedding)
    try:
        return conn.execute(
            "SELECT id, distance FROM chunks_vec"
            " WHERE embedding MATCH ? AND k = ? ORDER BY distance",
            (blob, k),
        ).fetchall()
    except sqlite3.Error as e:
        raise CorruptIndexError(f"vector search failed: {e}") from e


def search_keyword(conn: sqlite3.Connection, query: str, k: int) -> list[tuple[int, float]]:
    """Chunks matching any query term, ranked by BM25 (lower = better)."""
    terms = [f'"{t}"' for t in re.findall(r"\w+", query)]
    if not terms:
        return []
    try:
        return conn.execute(
            "SELECT rowid, bm25(chunks_fts) FROM chunks_fts"
            " WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts) LIMIT ?",
            (" OR ".join(terms), k),
        ).fetchall()
    except sqlite3.Error as e:
        raise CorruptIndexError(f"keyword search failed: {e}") from e
