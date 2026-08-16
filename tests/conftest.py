"""Shared fixtures: a deterministic fake embedder and synthetic book builders."""

from __future__ import annotations

import re
import zipfile
import zlib
from pathlib import Path

import pytest

from book_rag.embed import EmbedderError


class FakeEmbedder:
    """Deterministic bag-of-words embedder.

    crc32 (not hash) so vectors are stable across processes; distinctive
    vocabulary produces distinct vectors, which is enough to test ranking.
    """

    dim = 64

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            vec = [0.0] * self.dim
            for word in re.findall(r"\w+", text.lower()):
                vec[zlib.crc32(word.encode()) % self.dim] += 1.0
            norm = (sum(x * x for x in vec) ** 0.5) or 1.0
            out.append([x / norm for x in vec])
        return out


class DeadEmbedder(FakeEmbedder):
    """Always fails — simulates Ollama being down at query time."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise EmbedderError("ollama down (test)")


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def dead_embedder() -> DeadEmbedder:
    return DeadEmbedder()


_CONTAINER = """<?xml version="1.0"?>
<container version="1.0" xmlns="{ns}">
  <rootfiles>
    <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""

_OPF = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{title}</dc:title>
    <dc:creator>{author}</dc:creator>
    <meta id="uid">fixture-uid</meta>
  </metadata>
  <manifest>{nav_item}{items}</manifest>
  <spine>{itemrefs}</spine>
</package>"""

# Spec-correct EPUB container namespace (exercises book_rag's ebooklib shim).
EPUB_CONTAINER_NS = "http://www.w3.org/2009/epub"
# Legacy ODF namespace (what ebooklib matches natively; e.g. Project Gutenberg).
ODF_CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"


def make_epub(
    path: Path,
    chapters: list[tuple[str, str]],
    *,
    title: str = "Fixture Book",
    author: str = "Fixture Author",
    container_ns: str = EPUB_CONTAINER_NS,
) -> Path:
    """Build a minimal valid EPUB3 (nav document for structure).

    ``chapters`` is a list of (toc_title, body_html) pairs.
    """
    items: list[str] = []
    itemrefs: list[str] = ['<itemref idref="nav"/>']
    nav_links: list[str] = []
    for i, (toc_title, _body) in enumerate(chapters):
        items.append(f'<item id="ch{i}" href="ch{i}.xhtml" media-type="application/xhtml+xml"/>')
        itemrefs.append(f'<itemref idref="ch{i}"/>')
        nav_links.append(f'<li><a href="ch{i}.xhtml">{toc_title}</a></li>')

    nav = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<html xmlns="http://www.w3.org/1999/xhtml" '
        'xmlns:epub="http://www.idpf.org/2007/ops">'
        "<head><title>Contents</title></head>"
        f'<body><nav epub:type="toc"><h1>Contents</h1>'
        f"<ol>{''.join(nav_links)}</ol></nav></body></html>"
    )

    with zipfile.ZipFile(path, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED  # must be first, stored
        z.writestr(zi, "application/epub+zip")
        z.writestr("META-INF/container.xml", _CONTAINER.format(ns=container_ns))
        z.writestr(
            "content.opf",
            _OPF.format(
                title=title,
                author=author,
                nav_item=(
                    '<item id="nav" href="nav.xhtml" '
                    'media-type="application/xhtml+xml" properties="nav"/>'
                ),
                items="".join(items),
                itemrefs="".join(itemrefs),
            ),
        )
        z.writestr("nav.xhtml", nav)
        for i, (_toc_title, body) in enumerate(chapters):
            z.writestr(
                f"ch{i}.xhtml",
                '<?xml version="1.0" encoding="utf-8"?>'
                '<html xmlns="http://www.w3.org/1999/xhtml">'
                "<head><title>t</title></head>"
                f"<body>{body}</body></html>",
            )
    return path


@pytest.fixture
def epub_factory():
    """Factory for synthetic EPUBs (spec-correct container namespace by default)."""
    return make_epub
