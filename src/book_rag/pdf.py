"""PDF book parsing: one section per page, page number as provenance.

pypdfium2 (Google PDFium bindings) gives reading-order text per page via
``get_textpage().get_text_range()`` — good enough for prose-heavy books
without paying for a layout engine. Each page becomes one section whose
``path`` is ``"Page N"`` and whose ``page`` is the 1-based page number;
PDF outline / bookmark titles are a later refinement (v2).

Image-only or scanned PDFs yield no text and are rejected downstream by
``build_index``'s ``MIN_TEXT_CHARS`` guard. OCR is explicitly out of scope.
"""

from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium
from pypdfium2 import PdfiumError

from .models import BookError, BookMeta, Section
from .normalize import normalize


def _meta_value(values: object) -> str | None:
    """First non-empty metadata string, if any."""
    if not values:
        return None
    if isinstance(values, str):
        return values.strip() or None
    return None


def parse(path: Path) -> tuple[BookMeta, list[Section]]:
    """Parse a PDF book into (metadata, sections)."""
    try:
        doc = pdfium.PdfDocument(str(path))
    except (PdfiumError, FileNotFoundError, OSError) as e:
        raise BookError(f"unreadable PDF: {e}") from e

    try:
        meta_dict = doc.get_metadata_dict()
    except Exception:  # metadata is best-effort; never fail indexing on it
        meta_dict = {}

    meta = BookMeta(
        title=_meta_value(meta_dict.get("Title")),
        author=_meta_value(meta_dict.get("Author")),
    )

    sections: list[Section] = []
    for i, page in enumerate(doc, start=1):
        try:
            raw = page.get_textpage().get_text_range()
        except PdfiumError:
            raw = ""
        text = normalize(raw)
        if not text:
            continue  # image-only or empty page
        sections.append(Section(path=f"Page {i}", text=text, page=i))

    doc.close()
    return meta, sections
