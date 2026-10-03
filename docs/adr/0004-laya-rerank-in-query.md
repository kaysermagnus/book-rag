# Optional laya rerank pass inside query

Status: accepted

Hybrid retrieval maximizes recall, not relevance — fused candidates can merely *look* relevant. `query()` therefore gains an optional rerank: each candidate is scored (`score`) and kept or dropped (`noul` gate) by a laya decision model over HTTP (`LAYA_URL` → `laya-serve`); if fewer than `top_k` survive, the candidate pool doubles (up to 3 rounds) before giving up and reporting `rounds_used` / `passed`.

**Why inside `query` and not agent-side:** the score-gate-widen loop is a fixed pipeline. Run by the agent, it costs tool calls and tokens every query; run internally, agents get pre-filtered chunks for free and the loop stays deterministic.

**Why it doesn't break retrieve-only (ADR-0001):** rerank is a decision *about* chunks — it reorders and removes, never generates or alters text. The verbatim guarantee and the agent's citation contract are untouched.

**Trade-offs accepted:** extra latency (1–3 HTTP calls per query) and a new optional dependency, contained by degrade-and-say (`rerank.status: "unavailable"` returns normal results) and by being entirely off when `LAYA_URL` is unset — byte-identical behavior, no new required dependency.
