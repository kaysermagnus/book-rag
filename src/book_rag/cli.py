"""The book-rag command line: a thin wrapper over build_index / query.

    book-rag index <file> [--title T] [--author A]
    book-rag query <index> "<question>" [--top N] [--text]

``query`` prints JSON on stdout by default (the agent-facing contract);
``--text`` switches to human-readable output. Progress and warnings go to
stderr, so stdout stays machine-parseable. Exit code 1 with a message on
stderr for any failure (bad format, no text, Ollama down at index time).
"""

from __future__ import annotations

import argparse
import json
import sys

from . import build_index, query
from .embed import EmbedderError
from .models import BookError, CorruptIndexError


def _render_text(output) -> str:
    lines = [f"{output.book}  (mode: {output.mode})", ""]
    for r in output.results:
        where = f"  [{r.path}]" if r.path else ""
        lines.append(f"{r.rank}. (score {r.score:.3f}){where}")
        lines.append(f"   {r.text[:400]}")
        lines.append("")
    return "\n".join(lines).rstrip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="book-rag",
        description="Transform books into local retrieval indexes; retrieve verbatim chunks.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_index = sub.add_parser("index", help="transform a book into an index beside it")
    p_index.add_argument("file", help="path to the .epub or .txt book")
    p_index.add_argument("--title", help="override the book title")
    p_index.add_argument("--author", help="override the author")

    p_query = sub.add_parser("query", help="retrieve verbatim chunks for a question")
    p_query.add_argument("index", help="path to the .rag index file")
    p_query.add_argument("question", help="the question to retrieve for")
    p_query.add_argument("--top", type=int, default=5, help="number of results (default 5)")
    p_query.add_argument("--text", action="store_true", help="human-readable output")

    args = parser.parse_args(argv)
    try:
        if args.command == "index":
            path = build_index(args.file, title=args.title, author=args.author)
            print(f"indexed → {path}")
        else:
            output = query(args.index, args.question, top_k=args.top)
            if args.text:
                print(_render_text(output))
            else:
                payload = {
                    "book": output.book,
                    "mode": output.mode,
                    "results": [
                        {
                            "rank": r.rank,
                            "score": round(r.score, 4),
                            "path": r.path,
                            "text": r.text,
                        }
                        for r in output.results
                    ],
                }
                print(json.dumps(payload, ensure_ascii=False, indent=2))
    except (BookError, EmbedderError, CorruptIndexError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
