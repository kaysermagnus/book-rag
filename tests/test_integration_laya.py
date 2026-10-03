"""End-to-end rerank against a real laya-serve (opt-in).

Needs laya-serve reachable on LAYA_URL (default http://localhost:8090) —
e.g. `docker compose up -d` in ../laya-mcp. Auto-skips when down.
"""

from __future__ import annotations

import os
import time
import urllib.request

import pytest

from book_rag import build_index, query

pytest.importorskip("httpx")

from book_rag.rerank import LayaReranker

URL = os.environ.get("LAYA_URL", "http://localhost:8090")


def _laya_up() -> bool:
    for attempt in range(2):
        try:
            with urllib.request.urlopen(f"{URL}/health", timeout=3) as r:
                return r.status == 200
        except Exception:
            if attempt == 0:
                time.sleep(0.5)
    return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _laya_up(), reason=f"laya-serve not running on {URL}"),
]


def test_real_laya_gates_irrelevant_chunk(tmp_path, fake_embedder):
    src = tmp_path / "book.txt"
    src.write_text(
        "# Voyage\n"
        "\n"
        "The green ship sailed from the harbor at dawn, sails filling with the offshore wind.\n"
        "\n"
        "# Tax Code\n"
        "\n"
        "Form 1040 instructions: enter adjusted gross income on line 11 before computing tax.\n",
        encoding="utf-8",
    )
    idx = build_index(src, embedder=fake_embedder)
    out = query(
        idx,
        "how did the ship leave the harbor?",
        embedder=fake_embedder,
        reranker=LayaReranker(URL),
    )
    assert out.rerank is not None and out.rerank["status"] == "ok"
    paths = [r.path for r in out.results]
    assert "Voyage" in paths and "Tax Code" not in paths
    assert out.results[0].relevance is not None
