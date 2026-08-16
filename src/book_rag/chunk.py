"""Structure-first chunking: bounded by document structure, capped at max size.

Sections that fit the token budget become single chunks. Oversized sections
are sub-split at paragraph boundaries; a new window carries the previous
window's tail as overlap so sentences crossing the boundary stay retrievable.

Token counting uses word count — a conservative estimate (English tokens run
~1.3x words), so a window that fits in words also fits the embedding model's
context with margin.
"""

from __future__ import annotations

from .models import Chunk, Section

MAX_TOKENS = 1024
OVERLAP_TOKENS = 128


def _tokens(text: str) -> int:
    return len(text.split())


def _split_oversized_paragraph(paragraph: str) -> list[str]:
    """Hard-split a paragraph longer than the cap, at word boundaries."""
    words = paragraph.split()
    if len(words) <= MAX_TOKENS:
        return [paragraph]

    parts: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + MAX_TOKENS, len(words))
        parts.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = max(end - OVERLAP_TOKENS, start + 1)
    return parts


def _overlap_tail(window_text: str) -> list[str]:
    """Trailing paragraphs of a window, up to ~OVERLAP_TOKENS words."""
    paragraphs = [p for p in (s.strip() for s in window_text.split("\n\n")) if p]
    tail: list[str] = []
    for paragraph in reversed(paragraphs):
        if tail and _tokens(" ".join(tail + [paragraph])) > OVERLAP_TOKENS:
            break
        tail.insert(0, paragraph)
    if _tokens(" ".join(tail)) > OVERLAP_TOKENS:  # single giant paragraph
        return [" ".join(" ".join(tail).split()[-OVERLAP_TOKENS:])]
    return tail


def _chunk_section(section: Section) -> list[Chunk]:
    paragraphs = [p for p in (s.strip() for s in section.text.split("\n\n")) if p]
    units: list[str] = []
    for paragraph in paragraphs:
        units.extend(_split_oversized_paragraph(paragraph))

    chunks: list[Chunk] = []
    window: list[str] = []
    for unit in units:
        if window and _tokens("\n\n".join(window + [unit])) > MAX_TOKENS:
            chunks.append(Chunk(path=section.path, text="\n\n".join(window)))
            window = _overlap_tail("\n\n".join(window))
        window.append(unit)
    if window:
        chunks.append(Chunk(path=section.path, text="\n\n".join(window)))
    return chunks


def chunk_sections(sections: list[Section]) -> list[Chunk]:
    """Turn sections into bounded, overlapping chunks."""
    chunks: list[Chunk] = []
    for section in sections:
        if not section.text.strip():
            continue
        chunks.extend(_chunk_section(section))
    return chunks
