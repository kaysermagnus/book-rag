# Design

## Context

See proposal.md — Why. Facts that shape the approach:

- `book_rag.query()` is the public seam for CLI and MCP (`query_book`); it already takes `embedder=None` as a DI hook and degrades to `keyword-fallback` when the embedder fails. The reranker follows both conventions exactly.
- Candidates fetched per source = `top_k * 2`; `fuse()` merges ranked id lists. Chunk texts are capped ~1024 tokens — inside `laya-typed-decisions`' 1024-token context (question head consumes part of it, so texts get a safety truncation).
- `Result.score` is documented as "fused score" (RRF). Laya's judgment is a *different* number — it goes on a new optional `relevance` field rather than redefining `score`.
- laya-serve contract (Jev): `POST /v1/systemone/batch` — `{state, questions}` per item; answers give `score` (ordinal level), `noul` (P true), `answer_confidence`.

## Goals / Non-Goals

**Goals:**
- Rerank inside `query()` — agents keep calling one tool and get pre-filtered, best-first chunks.
- Honest degradation everywhere: unconfigured → old behavior; unreachable → un-reranked results + status.
- Metadata lets the agent see retrieval struggled (`passed < top_k`, `rounds_used`).

**Non-Goals:**
- No generative model, no text rewriting — verbatim guarantee untouched (ADR-0001 holds).
- No rerank of `build_index`, no async API changes, no per-call `rerank=` flag (configuration-driven per repo decision; a caller param is a future option).
- The laya-serve service itself is built in the laya-mcp repo; here it is only a client.

## Decisions

- **DI over env-detection**: `query(..., reranker=None)`; `None` → build `LayaReranker` from `LAYA_URL` if set, else disabled. Mirrors `embedder` exactly; tests inject a fake reranker — no HTTP mocks needed at the query seam.
- **`Reranker` protocol**: one method — `evaluate(question: str, texts: list[str]) -> list[Decision]` where `Decision` = `(relevance: float, keep: bool)`. One method keeps the seam minimal; batching lives inside it.
- **Loop inside `query()`**: pool sizes `top_k*2 → top_k*4 → top_k*8` (cap 3 rounds); each round re-fuses only the *newly fetched* slice's superset and re-evaluates unseen candidates — evaluated results are cached by chunk id so a candidate is never scored twice.
- **Order by relevance, keep `score` as fused**: survivors sorted by `relevance` desc; `rank` recomputed 1..N on the final list.
- **Gate threshold**: `noul` P ≥ 0.5 keeps (module constant, tunable later); `relevance` = the score answer.
- **`LayaReranker`** maps each candidate to `{state: <chunk text truncated to budget>, questions: {relevance: score(1–5), keep: noul}}` over `/v1/systemone/batch`, one HTTP call per round.

## Risks / Trade-offs

- **Extra latency per query (1–3 HTTP round-trips)** → opt-in by config; CPU ONNX keeps each batch ~100–300 ms for ≤16 candidates.
- **Fewer-than-top_k results surprise existing agents** → metadata reports the shortfall; the verbatim contract (what you get is real text) is unchanged.
- **`relevance`/`score` duality could confuse** → CONTEXT.md defines Rerank; docstrings state `score` = retrieval fusion, `relevance` = decision-model judgment.

## Migration Plan

Additive and env-gated: deploy with `LAYA_URL` unset → zero behavior change; set it + add the compose service → rerank activates. Rollback: unset `LAYA_URL`.

## Open Questions

- None blocking. Threshold (0.5), pool schedule (×2, 3 rounds), and score scale (1–5) are tunable constants — calibration against real books can adjust them without spec changes.
