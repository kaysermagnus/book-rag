"""MCP server exposing book-rag retrieval to external agents.

    uv run --extra mcp book-rag-mcp                          # stdio (default)
    uv run --extra mcp book-rag-mcp --transport http \
        --host 0.0.0.0 --port 8080                          # streamable-http

Two read-only tools (ADR 0002):
    list_indexes(directory=".")   -> discover available book indexes
    query_book(index, question)   -> verbatim chunks with provenance

Index building is deliberately not exposed — it is a write operation,
gated behind an explicit decision (ADR 0002). The agent-facing contract
mirrors `book-rag query`: verbatim chunks, provenance, and a citation
obligation (answer only from retrieved chunks, and cite them).
"""

from __future__ import annotations

import argparse
from pathlib import Path

# Optional extra (`uv sync --extra mcp`); unresolvable where the extra is absent.
from mcp.server.fastmcp import FastMCP  # pyright: ignore[reportMissingImports]

from . import query
from .models import BookError
from .store import open_index, read_meta

mcp = FastMCP(
    "book-rag",
    instructions=(
        "Retrieve verbatim chunks from indexed books. Call list_indexes first to see "
        "which books are available, then query_book with an index path. Answer only "
        "from the retrieved chunks and cite their provenance (book + structural path)."
    ),
)


@mcp.tool()
def list_indexes(directory: str = ".") -> dict:
    """List available book indexes (.rag files) in a directory, with title and author.

    Call this first to discover which books you can query. Returns the index
    paths — pass one of them as `index` to query_book.
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise BookError(f"no such directory: {directory}")

    indexes = []
    for rag in sorted(dir_path.glob("*.rag")):
        conn = open_index(rag)
        try:
            meta = read_meta(conn)
        finally:
            conn.close()
        indexes.append(
            {
                "path": str(rag),
                "title": meta.get("title") or rag.stem,
                "author": meta.get("author") or "",
            }
        )
    return {"indexes": indexes}


@mcp.tool()
def query_book(index: str, question: str, top_k: int = 5) -> dict:
    """Retrieve verbatim chunks from a book index for a question.

    Hybrid retrieval (vector + keyword) by default; degrades to
    keyword-only when the embedder is unavailable (see `mode`). Returns up
    to top_k ranked results, each with a structural path and verbatim text.
    Answer only from the returned chunks, citing their paths.
    """
    output = query(index, question, top_k=top_k)
    return {
        "book": output.book,
        "mode": output.mode,
        "results": [
            {
                "rank": r.rank,
                "score": round(r.score, 4),
                "path": r.path,
                "page": r.page,
                "text": r.text,
            }
            for r in output.results
        ],
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="book-rag-mcp",
        description="MCP server exposing book-rag retrieval to agents.",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "http"),
        default="stdio",
        help="stdio for in-process agents; http serves streamable-http (default: stdio)",
    )
    parser.add_argument("--host", help="bind address for http transport (default 127.0.0.1)")
    parser.add_argument("--port", type=int, help="port for http transport (default 8000)")
    args = parser.parse_args(argv)

    if args.transport == "http":
        if args.host is not None:
            mcp.settings.host = args.host
        if args.port is not None:
            mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
