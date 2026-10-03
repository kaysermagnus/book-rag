# Tasks

## 1. Rerank pass in query() (TDD: red → green, seam = query() with fake reranker)

- [x] 1.1 Write failing test: injected all-pass reranker → `QueryOutput.rerank` metadata present, results carry `relevance` (extends `Result`, `QueryOutput` in models.py) → verify fails
- [x] 1.2 Implement `Reranker` protocol + rerank pass in `query()` → verify 1.1 and all existing query tests still pass (old shape when reranker=None)
- [x] 1.3 Write failing test: gate drops candidates → dropped absent, survivors ordered by relevance, `rank` recomputed → implement → verify passes
- [x] 1.4 Write failing test: insufficient survivors → pool widens (×2, ≤3 rounds), candidates never re-evaluated, `rounds_used`/`candidates_evaluated`/`passed` reported → implement → verify passes
- [x] 1.5 Write failing test: exhaustion → returns survivors only, honest metadata → implement → verify passes
- [x] 1.6 Write failing test: reranker raises → un-reranked results + `rerank.status: "unavailable"` → implement → verify passes

## 2. Env wiring + HTTP adapter

- [x] 2.1 Write failing test: `LAYA_URL` set → `query()` uses `LayaReranker` without one being injected → implement env construction → verify passes
- [x] 2.2 Write failing test for `LayaReranker` payload mapping via `httpx.MockTransport` (request shape → `(relevance, keep)` per candidate, in order) → implement adapter → verify passes

## 3. MCP passthrough + docs

- [x] 3.1 Write failing test: `query_book` output includes `rerank` metadata + `relevance` when present → implement → verify passes
- [x] 3.2 Add **Rerank** term to `CONTEXT.md`; write `docs/adr/0004-laya-rerank-in-query.md` → verify files exist and match repo formats
- [x] 3.3 `docker-compose.yml`: add `laya-serve` service (`build: ../laya-mcp`, internal network only) + `LAYA_URL` env on book-rag → verify `docker compose config` validates
- [x] 3.4 Update README retrieval section with rerank behavior + env flag → verify doc matches implementation

## 4. Integration

- [x] 4.1 End-to-end (opt-in/slow marker): real `laya-serve` + a small fixture index → verify gate drops a deliberately-irrelevant chunk → verify passes with services running
