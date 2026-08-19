"""build_index: format dispatch, metadata, structure, errors, idempotency.

All tests use the fake embedder (no Ollama) and exercise the public seam.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import EPUB_CONTAINER_NS, ODF_CONTAINER_NS

from book_rag import BookError, build_index, query
from book_rag.store import open_index, read_meta


def _txt(tmp_path, name="book.txt", content=None) -> Path:
    p = tmp_path / name
    if content is None:
        content = (
            "# Alpha\n"
            "\n"
            "The zebra quokka alpaca gather in the meadow to discuss alpha topics at length.\n"
            "\n"
            "# Beta\n"
            "\n"
            "The fjord glacier tundra stretch across the north where beta topics are debated.\n"
        )
    p.write_text(content, encoding="utf-8")
    return p


def test_txt_build_creates_rag_beside_source(tmp_path, fake_embedder):
    src = _txt(tmp_path)
    idx = build_index(src, embedder=fake_embedder)
    assert idx == src.with_suffix(".rag")
    assert idx.is_file()


def test_txt_metadata_falls_back_to_stem(tmp_path, fake_embedder):
    src = _txt(tmp_path, name="mybook.txt")
    idx = build_index(src, embedder=fake_embedder)
    assert query(idx, "zebra", embedder=fake_embedder).book == "mybook"


def test_title_override(tmp_path, fake_embedder):
    src = _txt(tmp_path)
    idx = build_index(src, title="Custom Title", embedder=fake_embedder)
    assert query(idx, "zebra", embedder=fake_embedder).book == "Custom Title"


def test_txt_heading_paths_retrievable(tmp_path, fake_embedder):
    src = _txt(tmp_path)
    idx = build_index(src, embedder=fake_embedder)
    out = query(idx, "zebra quokka alpaca meadow", embedder=fake_embedder)
    assert out.results[0].path == "Alpha"


def test_epub_build_and_opf_metadata(tmp_path, epub_factory, fake_embedder):
    chapters = [
        ("Chapter One", "<p>The emerald canopy of the forest shelters one-unique creatures.</p>"),
        ("Chapter Two", "<p>The crimson desert of the wasteland hosts two-unique wanderers.</p>"),
    ]
    epub = epub_factory(tmp_path / "book.epub", chapters, title="Epub Title", author="Epub Author")
    idx = build_index(epub, embedder=fake_embedder)
    assert idx.is_file()
    meta = read_meta(open_index(idx))
    assert meta["title"] == "Epub Title"
    assert meta["author"] == "Epub Author"


def test_epub_toc_paths_retrievable(tmp_path, epub_factory, fake_embedder):
    chapters = [
        ("Chapter One", "<p>The emerald canopy of the forest shelters one-unique creatures.</p>"),
        ("Chapter Two", "<p>The crimson desert of the wasteland hosts two-unique wanderers.</p>"),
    ]
    epub = epub_factory(tmp_path / "book.epub", chapters)
    idx = build_index(epub, embedder=fake_embedder)
    out = query(idx, "emerald canopy forest", embedder=fake_embedder)
    assert out.results[0].path == "Chapter One"


def test_epub_spec_container_namespace(tmp_path, epub_factory, fake_embedder):
    # spec-correct 2009/epub namespace — exercises the ebooklib shim
    epub = epub_factory(
        tmp_path / "a.epub",
        [
            ("One", "<p>The first chapter opens with a long sentence of body text.</p>"),
            ("Two", "<p>The second chapter continues with another long sentence of text.</p>"),
            ("Three", "<p>The third chapter closes with yet another long sentence of text.</p>"),
        ],
        container_ns=EPUB_CONTAINER_NS,
    )
    assert build_index(epub, embedder=fake_embedder).is_file()


def test_epub_odf_container_namespace(tmp_path, epub_factory, fake_embedder):
    # legacy ODF namespace — what ebooklib matches natively (e.g. Project Gutenberg)
    epub = epub_factory(
        tmp_path / "b.epub",
        [
            ("One", "<p>The first chapter opens with a long sentence of body text.</p>"),
            ("Two", "<p>The second chapter continues with another long sentence of text.</p>"),
            ("Three", "<p>The third chapter closes with yet another long sentence of text.</p>"),
        ],
        container_ns=ODF_CONTAINER_NS,
    )
    assert build_index(epub, embedder=fake_embedder).is_file()


def test_unsupported_format_raises(tmp_path, fake_embedder):
    docx = tmp_path / "book.docx"
    docx.write_bytes(b"PK fake docx")
    with pytest.raises(BookError, match="unsupported format"):
        build_index(docx, embedder=fake_embedder)


def test_pdf_build_creates_rag_beside_source(tmp_path, pdf_factory, fake_embedder):
    pdf = pdf_factory(
        tmp_path / "book.pdf",
        [
            "The zebra quokka alpaca gather in the meadow to discuss alpha topics "
            "at considerable length and with great enthusiasm."
        ],
    )
    idx = build_index(pdf, embedder=fake_embedder)
    assert idx == pdf.with_suffix(".rag")
    assert idx.is_file()


def test_pdf_metadata_falls_back_to_stem(tmp_path, pdf_factory, fake_embedder):
    pdf = pdf_factory(
        tmp_path / "mybook.pdf",
        [
            "The zebra quokka alpaca gather in the meadow to discuss alpha topics "
            "at considerable length and with great enthusiasm."
        ],
    )
    idx = build_index(pdf, embedder=fake_embedder)
    assert query(idx, "zebra", embedder=fake_embedder).book == "mybook"


def test_pdf_page_provenance_retrievable(tmp_path, pdf_factory, fake_embedder):
    pdf = pdf_factory(
        tmp_path / "book.pdf",
        [
            "The emerald canopy of the forest shelters one-unique creatures "
            "at considerable length and with great enthusiasm.",
            "The crimson desert of the wasteland hosts two-unique wanderers "
            "at considerable length and with great enthusiasm.",
        ],
    )
    idx = build_index(pdf, embedder=fake_embedder)
    out = query(idx, "emerald canopy forest", embedder=fake_embedder)
    top = out.results[0]
    assert top.path == "Page 1"
    assert top.page == 1


def test_pdf_second_page_retrievable(tmp_path, pdf_factory, fake_embedder):
    pdf = pdf_factory(
        tmp_path / "book.pdf",
        [
            "The emerald canopy of the forest shelters one-unique creatures "
            "at considerable length and with great enthusiasm.",
            "The crimson desert of the wasteland hosts two-unique wanderers "
            "at considerable length and with great enthusiasm.",
        ],
    )
    idx = build_index(pdf, embedder=fake_embedder)
    out = query(idx, "crimson desert wasteland", embedder=fake_embedder)
    top = out.results[0]
    assert top.page == 2


def test_image_only_pdf_raises(tmp_path, pdf_factory, fake_embedder):
    # a PDF whose only page has no text content
    pdf = pdf_factory(tmp_path / "book.pdf", ["   "])
    with pytest.raises(BookError, match="no extractable text"):
        build_index(pdf, embedder=fake_embedder)


def test_no_such_file_raises(tmp_path, fake_embedder):
    with pytest.raises(BookError, match="no such file"):
        build_index(tmp_path / "missing.txt", embedder=fake_embedder)


def test_no_extractable_text_raises(tmp_path, fake_embedder):
    tiny = tmp_path / "tiny.txt"
    tiny.write_text("too short", encoding="utf-8")  # < MIN_TEXT_CHARS
    with pytest.raises(BookError, match="no extractable text"):
        build_index(tiny, embedder=fake_embedder)


def test_rebuild_is_idempotent(tmp_path, fake_embedder):
    src = _txt(tmp_path)
    idx1 = build_index(src, embedder=fake_embedder)
    idx2 = build_index(src, embedder=fake_embedder)  # replaces, does not fail
    assert idx1 == idx2
    assert idx1.is_file()


def test_non_utf8_txt_decoded(tmp_path, fake_embedder):
    p = tmp_path / "latin.txt"
    raw = (
        "Caf\u00e9 cr\u00e8me au lait: a long discussion of the morning menu and its "
        "many delightful items served each day.\n"
    )
    p.write_bytes(raw.encode("latin-1"))  # 0xe9/0xe8 bytes are invalid UTF-8
    assert build_index(p, embedder=fake_embedder).is_file()


def test_normalization_applied_to_chunks(tmp_path, fake_embedder):
    p = tmp_path / "dehyph.txt"
    # line-break hyphen before a lowercase letter joins without the hyphen
    p.write_text("The com-\nbat was fierce and long. " + "word " * 20, encoding="utf-8")
    idx = build_index(p, embedder=fake_embedder)
    out = query(idx, "combat fierce", embedder=fake_embedder)
    assert any("combat" in r.text for r in out.results)
