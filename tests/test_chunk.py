"""Chunking: structure-bounded windows, word cap, overlap, path preservation."""

from __future__ import annotations

from book_rag.chunk import MAX_TOKENS, OVERLAP_TOKENS, chunk_sections
from book_rag.models import Section


def test_small_section_is_single_chunk():
    section = Section(path="Ch 1", text="First para.\n\nSecond para.")
    chunks = chunk_sections([section])
    assert len(chunks) == 1
    assert chunks[0].path == "Ch 1"
    assert chunks[0].text == "First para.\n\nSecond para."


def test_empty_section_is_skipped():
    sections = [Section(path="A", text="   \n\t  ")]
    assert chunk_sections(sections) == []


def test_paths_preserved_across_split():
    paras = [f"p{i:03d} " + " ".join(["w"] * 19) for i in range(60)]
    section = Section(path="Long Chapter", text="\n\n".join(paras))
    chunks = chunk_sections([section])
    assert len(chunks) >= 2
    assert all(c.path == "Long Chapter" for c in chunks)


def test_windows_respect_word_cap():
    paras = [f"p{i:03d} " + " ".join(["w"] * 19) for i in range(60)]
    section = Section(path="Long", text="\n\n".join(paras))
    chunks = chunk_sections([section])
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c.text.split()) <= MAX_TOKENS


def test_overlap_carries_tail_forward():
    paras = [f"marker{i:03d} " + " ".join(["filler"] * 19) for i in range(60)]
    section = Section(path="Long", text="\n\n".join(paras))
    chunks = chunk_sections([section])
    assert len(chunks) >= 2
    last_para_of_prev = chunks[0].text.split("\n\n")[-1]
    # the trailing paragraph of one window reappears at the head of the next
    assert last_para_of_prev in chunks[1].text


def test_oversized_single_paragraph_hard_split():
    # one paragraph far over the cap is split at word boundaries, with overlap
    para = " ".join(["word"] * (MAX_TOKENS + 50))
    section = Section(path="Wall", text=para)
    chunks = chunk_sections([section])
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c.text.split()) <= MAX_TOKENS + OVERLAP_TOKENS


def test_multiple_sections_keep_order():
    sections = [
        Section(path="One", text="alpha content here"),
        Section(path=None, text="flat content here"),
        Section(path="Two", text="beta content here"),
    ]
    chunks = chunk_sections(sections)
    assert [c.path for c in chunks] == ["One", None, "Two"]
