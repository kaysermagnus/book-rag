# Proposal

## Why

Hybrid retrieval (KNN + BM25 + RRF) maximizes recall but returns chunks that merely *look* relevant — agents then ground answers on weak candidates or must re-query blindly. A local decision model (laya-typed-decisions via `laya-serve`) can score and gate candidates in ~100 ms, turning retrieval into "loop until top-best" without any generative model in the loop.

## What Changes

- `query()` gains an optional rerank pass: fused candidates are scored (`score`) and kept/dropped (`noul` gate) by a reranker; survivors are returned in laya relevance order.
- Bounded retry loop: if fewer than `top_k` candidates pass the gate, the candidate pool widens (×2 per round, ≤3 rounds) and the gate re-runs; the output reports how retrieval went.
- Rerank is **opt-in by configuration**: active only when `LAYA_URL` is set (or a reranker is injected); unset → byte-identical current behavior.
- `QueryOutput` gains optional `rerank` metadata (status, rounds_used, candidates_evaluated, passed); `Result` gains optional `relevance` (the laya score). Existing fields unchanged.
- Degrade-and-say: if the reranker is unreachable, `query()` returns un-reranked results and marks the rerank status — mirroring the existing `keyword-fallback` convention.
- `query_book` MCP tool exposes the new metadata verbatim; signature unchanged.
- New adapter `LayaReranker` (HTTP → `laya-serve`); `CONTEXT.md` gains the term **Rerank**; ADR-0004 records the decision.

## Capabilities

### New Capabilities
- `retrieval-rerank`: an optional typed-decision pass inside `query()` that scores and gates retrieval candidates, retries with a widened pool on insufficient survivors, and reports the outcome.

### Modified Capabilities
- (none — no existing capability specs; OpenSpec initialized with this change)

## Impact

- `src/book_rag/__init__.py` (`query()`), `src/book_rag/models.py` (`Result`, `QueryOutput`), new `src/book_rag/rerank.py`, `src/book_rag/mcp_server.py` (metadata passthrough), `docker-compose.yml` (`LAYA_URL` env + `laya-serve` service), `CONTEXT.md`, `docs/adr/0004-*.md`, tests.
- Preserves the retrieve-only boundary (ADR-0001): rerank is a *decision about* retrieved chunks — it removes and reorders, never generates or alters text. Verbatim guarantee untouched.
- Depends on the `laya-mcp` project's `laya-serve` service (`build: ../laya-mcp`) — optional; without it nothing changes.
