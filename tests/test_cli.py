"""cli: exit codes, JSON contract on stdout, progress/warnings on stderr.

The default embedder (OllamaEmbedder) is swapped for a fake via monkeypatch so
these tests are hermetic — no Ollama required.
"""

from __future__ import annotations

import json

import pytest
from conftest import FakeEmbedder

import book_rag
from book_rag.cli import main


class FakeOllama(FakeEmbedder):
    """FakeEmbedder + the ensure_ready() hook build_index calls on the default embedder."""

    def ensure_ready(self) -> None:
        return None


@pytest.fixture
def fake_ollama(monkeypatch):
    # build_index/query construct OllamaEmbedder() when no embedder is passed; swap in the fake
    monkeypatch.setattr(book_rag, "OllamaEmbedder", FakeOllama)


def _book(tmp_path) -> str:
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
    return str(src)


def test_index_success(tmp_path, fake_ollama, capsys):
    assert main(["index", _book(tmp_path)]) == 0
    assert "indexed" in capsys.readouterr().out


def test_index_unsupported_format_exit_1(tmp_path, fake_ollama, capsys):
    docx = tmp_path / "book.docx"
    docx.write_bytes(b"PK fake docx")
    assert main(["index", str(docx)]) == 1
    assert "error" in capsys.readouterr().err


def test_index_progress_on_stderr_not_stdout(tmp_path, fake_ollama, capsys):
    main(["index", _book(tmp_path)])
    captured = capsys.readouterr()
    assert "embedded" in captured.err  # progress goes to stderr
    assert "embedded" not in captured.out  # stdout stays machine-clean


def test_query_json_contract(tmp_path, fake_ollama, capsys):
    assert main(["index", _book(tmp_path)]) == 0
    capsys.readouterr()  # discard the "indexed →" line
    assert main(["query", str(tmp_path / "book.rag"), "zebra quokka alpaca"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload.keys()) == {"book", "mode", "results"}
    assert payload["mode"] in ("hybrid", "keyword-fallback")
    for r in payload["results"]:
        assert set(r.keys()) == {"rank", "score", "path", "page", "text"}


def test_query_text_output_is_not_json(tmp_path, fake_ollama, capsys):
    assert main(["index", _book(tmp_path)]) == 0
    capsys.readouterr()
    assert main(["query", str(tmp_path / "book.rag"), "zebra quokka", "--text"]) == 0
    out = capsys.readouterr().out
    assert "mode:" in out  # human-readable header, not JSON
    with pytest.raises(json.JSONDecodeError):
        json.loads(out)


def test_query_top_flag(tmp_path, fake_ollama, capsys):
    assert main(["index", _book(tmp_path)]) == 0
    capsys.readouterr()
    assert (
        main(
            ["query", str(tmp_path / "book.rag"), "zebra quokka alpaca fjord glacier", "--top", "1"]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["results"]) <= 1


def test_query_no_such_index_exit_1(tmp_path, fake_ollama, capsys):
    assert main(["query", str(tmp_path / "missing.rag"), "q"]) == 1
    assert "error" in capsys.readouterr().err


def test_pdf_index_and_query_page_in_json(tmp_path, fake_ollama, pdf_factory, capsys):
    pdf = pdf_factory(
        tmp_path / "book.pdf",
        [
            "The emerald canopy of the forest shelters one-unique creatures "
            "at considerable length and with great enthusiasm."
        ],
    )
    assert main(["index", str(pdf)]) == 0
    capsys.readouterr()  # discard "indexed →"
    assert main(["query", str(tmp_path / "book.rag"), "emerald canopy forest"]) == 0
    payload = json.loads(capsys.readouterr().out)
    top = payload["results"][0]
    assert top["page"] == 1
    assert top["path"] == "Page 1"
