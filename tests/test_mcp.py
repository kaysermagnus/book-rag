"""MCP tools: discovery and retrieval, tested through the real query path."""

from __future__ import annotations

import pytest

from book_rag import build_index
from book_rag.mcp_server import list_indexes, query_book


def _build(tmp_path, fake_embedder):
    src = tmp_path / "book.txt"
    src.write_text(
        "# Alpha\n"
        "\n"
        "The zebra quokka alpaca gather in the meadow to discuss alpha topics at length.\n"
        "\n"
        "# Beta\n"
        "\n"
        "The fjord glacier tundra stretch across the north where beta topics are debated.\n",
        encoding="utf-8",
    )
    return build_index(src, embedder=fake_embedder)


@pytest.fixture(autouse=True)
def _no_ollama(monkeypatch):
    """Keep tests offline: the default embedder is never constructed."""
    monkeypatch.setattr("book_rag.OllamaEmbedder", lambda: pytest.fail("ollama used"))


def test_list_indexes_returns_metadata(tmp_path, fake_embedder):
    _build(tmp_path, fake_embedder)
    out = list_indexes(str(tmp_path))
    assert len(out["indexes"]) == 1
    entry = out["indexes"][0]
    assert entry["path"].endswith("book.rag")
    assert entry["title"] == "book"  # no title in .txt -> stem fallback
    assert entry["author"] == ""


def test_list_indexes_empty_directory(tmp_path):
    assert list_indexes(str(tmp_path)) == {"indexes": []}


def test_list_indexes_missing_directory_raises(tmp_path):
    with pytest.raises(Exception, match="no such directory"):
        list_indexes(str(tmp_path / "nowhere"))


def test_query_book_returns_verbatim_results_with_provenance(tmp_path, fake_embedder, monkeypatch):
    idx = _build(tmp_path, fake_embedder)
    monkeypatch.setattr("book_rag.OllamaEmbedder", lambda: fake_embedder)
    out = query_book(str(idx), "zebra quokka alpaca meadow")
    assert out["mode"] == "hybrid"
    top = out["results"][0]
    assert top["path"] == "Alpha"
    assert "zebra" in top["text"]  # verbatim, not paraphrased
    assert isinstance(top["score"], float) and top["score"] > 0


def test_query_book_degrades_to_keyword_fallback(
    tmp_path, fake_embedder, dead_embedder, monkeypatch
):
    idx = _build(tmp_path, fake_embedder)
    monkeypatch.setattr("book_rag.OllamaEmbedder", lambda: dead_embedder)
    out = query_book(str(idx), "zebra quokka")
    assert out["mode"] == "keyword-fallback"
    assert out["results"][0]["path"] == "Alpha"


def test_query_book_missing_index_raises(tmp_path, monkeypatch):
    with pytest.raises(Exception, match="no such index"):
        query_book(str(tmp_path / "missing.rag"), "anything")
