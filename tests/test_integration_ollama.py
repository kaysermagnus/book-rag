"""End-to-end with the real Ollama embedder (nomic-embed-text).

Skipped automatically when Ollama is not running, so the hermetic suite above
stays green in any environment. When Ollama is up, this validates real
embedding fidelity: a ship/ocean question must retrieve the "The Ship" section.
"""

from __future__ import annotations

import time
import urllib.request

import pytest


def _ollama_up() -> bool:
    # One retry: Ollama can be briefly slow on a cold start, which would otherwise
    # cause a false skip of the real-fidelity test below.
    for attempt in range(2):
        try:
            with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as r:
                return r.status == 200
        except Exception:
            if attempt == 0:
                time.sleep(0.5)
    return False


pytestmark = pytest.mark.skipif(not _ollama_up(), reason="Ollama not running on localhost:11434")


def test_real_ollama_roundtrip(tmp_path):
    from book_rag import build_index, query

    src = tmp_path / "book.txt"
    src.write_text(
        "# The Ship\n"
        "\n"
        "The great ship sailed across the grey and endless ocean under a heavy black sky.\n"
        "\n"
        "# The Land\n"
        "\n"
        "The green land rose from the shore, covered in dark forests and quiet rivers.\n",
        encoding="utf-8",
    )

    idx = build_index(src)  # default OllamaEmbedder -> real nomic-embed-text vectors
    assert idx.is_file()

    out = query(idx, "the ship sailing on the ocean")  # real embeddings
    assert out.mode == "hybrid"
    assert out.results[0].path == "The Ship"
