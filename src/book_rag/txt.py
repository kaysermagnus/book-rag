"""TXT book parsing: Markdown headings as structure, paragraphs otherwise.

Many "TXT books" are plain-text or Markdown exports. ``#``/``##`` heading
lines become section boundaries (path "H1" or "H1 › H2"); a file with no
headings is one flat section. No all-caps heuristics — too risky with poetry
and emphasis.
"""

from __future__ import annotations

import re
from pathlib import Path

from charset_normalizer import from_bytes

from .models import BookMeta, Section
from .normalize import normalize

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def _decode(raw: bytes) -> str:
    """UTF-8 strict first, encoding detection as fallback."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        best = from_bytes(raw).best()
        if best is not None:
            return str(best)
        return raw.decode("utf-8", errors="replace")


def parse(path: Path) -> tuple[BookMeta, list[Section]]:
    """Parse a TXT book into (metadata, sections)."""
    text = _decode(path.read_bytes())

    meta = BookMeta(title=path.stem, author=None)

    sections: list[Section] = []
    h1: str | None = None
    h2: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        if any(line.strip() for line in buffer):
            path_ = " › ".join(p for p in (h1, h2) if p) or None
            sections.append(Section(path=path_, text=normalize("\n".join(buffer))))
        buffer = []

    for line in text.splitlines():
        match = _HEADING.match(line)
        if match:
            flush()
            level, title = len(match.group(1)), match.group(2).strip()
            if level == 1:
                h1, h2 = title or None, None
            else:
                h2 = title or None
        else:
            buffer.append(line)
    flush()

    return meta, sections
