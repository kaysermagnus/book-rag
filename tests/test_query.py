"""query: hybrid ranking, keyword fallback, top_k bounds, error handling."""

from __future__ import annotations

import pytest

from book_rag import BookError, build_index, query


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


def test_hybrid_mode_ranks_best_section_first(tmp_path, fake_embedder):
    idx = _build(tmp_path, fake_embedder)
    out = query(idx, "zebra quokka alpaca meadow", embedder=fake_embedder)
    assert out.mode == "hybrid"
    assert out.results[0].path == "Alpha"


def test_keyword_fallback_when_embedder_down(tmp_path, fake_embedder, dead_embedder):
    idx = _build(tmp_path, fake_embedder)
    out = query(idx, "zebra quokka", embedder=dead_embedder)
    assert out.mode == "keyword-fallback"
    assert out.results  # BM25 still returns matches without vectors
    assert out.results[0].path == "Alpha"


def test_top_k_limits_results(tmp_path, fake_embedder):
    idx = _build(tmp_path, fake_embedder)
    out = query(idx, "zebra quokka alpaca fjord glacier", embedder=fake_embedder, top_k=2)
    assert len(out.results) <= 2
    assert [r.rank for r in out.results] == list(range(1, len(out.results) + 1))


def test_results_carry_verbatim_text_path_score(tmp_path, fake_embedder):
    idx = _build(tmp_path, fake_embedder)
    out = query(idx, "zebra quokka alpaca", embedder=fake_embedder)
    top = out.results[0]
    assert "zebra" in top.text  # verbatim content preserved, not paraphrased
    assert top.path == "Alpha"
    assert isinstance(top.score, float) and top.score > 0


def test_no_such_index_raises(tmp_path, fake_embedder):
    with pytest.raises(BookError, match="no such index"):
        query(tmp_path / "missing.rag", "anything", embedder=fake_embedder)
