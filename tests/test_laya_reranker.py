"""LayaReranker: the HTTP adapter to laya-serve, tested at the transport seam."""

from __future__ import annotations

import json

import httpx
import pytest

pytest.importorskip("httpx")

from book_rag.rerank import LayaReranker


def _serve(results):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.url.path == "/v1/systemone/batch"
        assert body["model"] == "typed-decisions"
        assert len(body["states"]) == len(results)
        assert set(body["questions"]) == {"relevance", "keep"}
        return httpx.Response(200, json={"results": results})

    return handler


def _answer(score: float, noul: float) -> dict:
    return {"answers": {"relevance": {"score": score}, "keep": {"noul": noul}}}


def test_maps_batch_response_to_verdicts_in_order():
    rk = LayaReranker(
        "http://laya-serve:8090",
        transport=httpx.MockTransport(_serve([_answer(4.2, 0.9), _answer(1.1, 0.2)])),
    )
    assert rk.evaluate("q?", ["text a", "text b"]) == [(4.2, 0.9), (1.1, 0.2)]


def test_question_reaches_model_inside_state():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content)["states"][0])
        return httpx.Response(200, json={"results": [_answer(3.0, 0.8)]})

    rk = LayaReranker("http://x", transport=httpx.MockTransport(handler))
    rk.evaluate("who is Ahab?", ["chunk text"])
    assert "who is Ahab?" in seen[0] and "chunk text" in seen[0]
