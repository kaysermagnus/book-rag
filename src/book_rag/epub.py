"""EPUB book parsing: nav/NCX structure, XHTML text extraction.

Structure comes from the table of contents (ebooklib prefers NCX and falls
back to the EPUB3 nav document). Each spine document becomes one section;
its path is its TOC title when the TOC references it, else ``None``.

ebooklib 0.20 quirk: its container.xml lookup only matches the ODF
namespace, so spec-correct EPUBs (``http://www.w3.org/2009/epub``) fail to
load. ``_load`` rewrites the namespace in a temp copy as a fallback.
"""

from __future__ import annotations

import tempfile
import zipfile
from html.parser import HTMLParser
from pathlib import Path

from ebooklib import epub
from ebooklib.epub import EpubException, EpubHtml, EpubNav

from .models import BookError, BookMeta, Section
from .normalize import normalize

_EPUB_CONTAINER_NS = b"http://www.w3.org/2009/epub"
_ODF_CONTAINER_NS = b"urn:oasis:names:tc:opendocument:xmlns:container"

# Tags whose content starts a new paragraph when flattened to text.
_BLOCK_TAGS = {
    "p",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "blockquote",
    "pre",
    "tr",
    "section",
    "article",
    "figure",
}
_SKIP_TAGS = {"script", "style"}


class _TextExtractor(HTMLParser):
    """Flatten XHTML to text: block tags become paragraph breaks."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag == "br":
            self.parts.append("\n")
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


def _extract_text(xhtml: bytes) -> str:
    extractor = _TextExtractor()
    try:
        extractor.feed(xhtml.decode("utf-8", errors="replace"))
    except Exception:  # malformed markup — keep whatever was collected
        pass
    return extractor.text()


def _load(path: Path) -> epub.EpubBook:
    try:
        return epub.read_epub(str(path))
    except EpubException as e:
        if "container" not in str(e).lower():
            raise BookError(f"unreadable EPUB: {e}") from e
    except KeyError as e:  # no META-INF/container.xml at all
        raise BookError(f"malformed EPUB (missing container): {e}") from e

    # Container exists but ebooklib's namespace lookup missed it: rewrite the
    # EPUB container namespace to the ODF one in a temp copy and retry.
    fixed = Path(tempfile.mkdtemp()) / path.name
    try:
        with zipfile.ZipFile(path) as src, zipfile.ZipFile(fixed, "w") as dst:
            for info in src.infolist():
                data = src.read(info.filename)
                if info.filename == "META-INF/container.xml":
                    data = data.replace(_EPUB_CONTAINER_NS, _ODF_CONTAINER_NS)
                dst.writestr(info, data)
        return epub.read_epub(str(fixed))
    except (EpubException, KeyError, OSError) as e:
        raise BookError(f"unreadable EPUB: {e}") from e
    finally:
        fixed.unlink(missing_ok=True)


def _toc_map(book: epub.EpubBook) -> dict[str, str]:
    """Map content file name (and basename) to TOC title.

    ``book.toc`` entries are ``Link`` objects (leaf entries) or
    ``(Section, [children])`` tuples (entries with sub-entries).
    """
    toc: dict[str, str] = {}

    def walk(entries) -> None:
        for entry in entries:
            if isinstance(entry, tuple):
                section, children = entry
                href = getattr(section, "href", "") or ""
                if href:
                    toc.setdefault(href.split("#")[0], section.title)
                walk(children)
            elif entry.href:  # Link
                toc.setdefault(entry.href.split("#")[0], entry.title)

    walk(book.toc)
    return toc


def _first_metadata(values) -> str | None:
    for value, _attrs in values or []:
        if value and str(value).strip():
            return str(value).strip()
    return None


def parse(path: Path) -> tuple[BookMeta, list[Section]]:
    """Parse an EPUB book into (metadata, sections)."""
    book = _load(path)

    meta = BookMeta(
        title=_first_metadata(book.get_metadata("DC", "title")),
        author=_first_metadata(book.get_metadata("DC", "creator")),
    )

    toc = _toc_map(book)
    sections: list[Section] = []
    for idref, _linear in book.spine:
        item = book.get_item_with_id(idref)
        if not isinstance(item, EpubHtml) or isinstance(item, EpubNav):
            continue  # skip the TOC document and non-content items
        text = normalize(_extract_text(item.get_content()))
        if not text:
            continue  # image-only or empty document
        section_path = toc.get(item.file_name) or toc.get(Path(item.file_name).name)
        sections.append(Section(path=section_path, text=text))

    return meta, sections
