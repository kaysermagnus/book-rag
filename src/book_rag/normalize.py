"""Verbatim normalization: faithful to the book's words, minus mechanical artifacts.

The fidelity promise is "what you retrieve is what the book says" — not
byte-identity to a lossy extraction. So we remove mechanical artifacts of
extraction (line-break hyphens, soft hyphens, ligatures, layout whitespace)
while leaving words and punctuation untouched.

Known v1 imperfection: a genuine compound word at a line end
("well-" / "known") is joined without the hyphen. Prose-first trade-off.
"""

from __future__ import annotations

import re

_LIGATURES = str.maketrans(
    {
        "\ufb00": "ff",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\ufb03": "ffi",
        "\ufb04": "ffl",
        "\ufb06": "ft",
        "\ufb07": "st",
    }
)

_SOFT_HYPHEN = "\u00ad"
# "com-\nbat" -> "combat": hyphen + line break before a lowercase letter.
_HYPHEN_BREAK_LOWER = re.compile(r"-\n(?=[a-z])")
# "New-\nYork" -> "New York": keep the hyphen as a space before non-lowercase.
_HYPHEN_BREAK_UPPER = re.compile(r"-\n(?=[^a-z])")
_INLINE_WS = re.compile(r"[ \t\r\f\v]+")


def normalize(text: str) -> str:
    """Normalize extracted text to verbatim form.

    Returns paragraphs separated by blank lines (``\\n\\n``), each paragraph
    on a single line with collapsed whitespace. Paragraph boundaries are the
    unit the chunker sub-splits on, so they must survive normalization.
    """
    text = text.translate(_LIGATURES)
    text = text.replace(_SOFT_HYPHEN, "")
    text = _HYPHEN_BREAK_LOWER.sub("", text)
    text = _HYPHEN_BREAK_UPPER.sub(" ", text)

    paragraphs: list[str] = []
    current: list[str] = []
    for line in text.split("\n"):
        stripped = _INLINE_WS.sub(" ", line).strip()
        if not stripped:
            if current:
                paragraphs.append(" ".join(current))
                current = []
        else:
            current.append(stripped)
    if current:
        paragraphs.append(" ".join(current))

    return "\n\n".join(paragraphs).strip()
