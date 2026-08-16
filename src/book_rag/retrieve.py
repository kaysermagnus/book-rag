"""Hybrid retrieval: vector KNN + FTS5/BM25, fused with reciprocal rank fusion.

RRF is score-free — it fuses the two rankings without needing to normalize
vector distances against BM25 scores. Each list contributes 1/(k + rank);
the fused score is the sum, so a chunk ranked high in both lists wins.
"""

from __future__ import annotations

RRF_K = 60


def fuse(
    vector_hits: list[tuple[int, float]],
    keyword_hits: list[tuple[int, float]],
    top_k: int,
) -> list[tuple[int, float]]:
    """Fuse two ranked id lists into one, best first."""
    scores: dict[int, float] = {}
    for hits in (vector_hits, keyword_hits):
        for rank, (chunk_id, _score) in enumerate(hits, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank)
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked[:top_k]
