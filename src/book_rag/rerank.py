"""Optional decision-model pass over retrieval candidates.

A reranker answers two typed questions per candidate against laya-serve —
a relevance `score` and a keep `noul` — in one batch. Candidates survive on
`score >= SCORE_FLOOR or keep >= KEEP_P` (the calibrated noul sits mid-range
for borderline text, so the score floor carries recall). It reorders and
removes; it never generates or alters text (ADR-0001 holds).
"""

from __future__ import annotations

import os
from typing import Protocol

# Relevance-score floor: "partially relevant" on the 0-4 ordinal scale.
SCORE_FLOOR = 2.0
# noul keep probability that survives even below the floor.
KEEP_P = 0.5
# Conservative character budget for a candidate state (~750 tokens).
MAX_STATE_CHARS = 3000


class Reranker(Protocol):
    """Verdict per candidate text: (relevance, keep_probability)."""

    def evaluate(self, question: str, texts: list[str]) -> list[tuple[float, float]]: ...


def kept(relevance: float, keep: float) -> bool:
    return relevance >= SCORE_FLOOR or keep >= KEEP_P


class LayaReranker:
    """Reranker over laya-serve's /v1/systemone/batch (Jev wire protocol)."""

    def __init__(
        self,
        base_url: str,
        *,
        model: str = "typed-decisions",
        timeout: float = 30.0,
        transport=None,
    ):
        import httpx  # optional dependency: only needed when rerank is on

        self._model = model
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout, transport=transport
        )

    _QUESTIONS = {
        "relevance": {
            "type": "score",
            "instructions": "How relevant is this text for answering the question?",
            "criteria": [
                "completely irrelevant",
                "tangential",
                "partially relevant",
                "relevant",
                "directly answers the question",
            ],
        },
        "keep": {
            "type": "noul",
            "instructions": "Is this text relevant enough to help answer the question?",
        },
    }

    def evaluate(self, question: str, texts: list[str]) -> list[tuple[float, float]]:
        states = [f"Question: {question}\n\n{t}"[:MAX_STATE_CHARS] for t in texts]
        r = self._http.post(
            "/v1/systemone/batch",
            json={"states": states, "questions": self._QUESTIONS, "model": self._model},
        )
        r.raise_for_status()
        out = []
        for res in r.json()["results"]:
            answers = res.get("answers", {})
            out.append(
                (
                    float(answers.get("relevance", {}).get("score", 0.0)),
                    float(answers.get("keep", {}).get("noul", 0.0)),
                )
            )
        return out


def from_env() -> Reranker | None:
    """Default reranker from LAYA_URL; None disables the pass entirely."""
    url = os.environ.get("LAYA_URL")
    return LayaReranker(url) if url else None
