# Spec Delta

## Purpose

An optional decision-model pass inside `query()` that scores retrieval candidates for true relevance, drops weak ones, retries with a wider pool when too few survive, and reports what happened.

## ADDED Requirements

### Requirement: Opt-in rerank activation
`query()` SHALL run the rerank pass only when a reranker is injected or `LAYA_URL` is set in the environment. With neither, `query()` SHALL return exactly the same output shape and content as before this change (no `rerank` metadata, no `relevance` on results).

#### Scenario: Rerank configured
- **WHEN** `LAYA_URL` is set and `query()` runs
- **THEN** results reflect the rerank pass and `QueryOutput` carries `rerank` metadata

#### Scenario: Rerank not configured
- **WHEN** neither a reranker nor `LAYA_URL` is present
- **THEN** output is identical to pre-change behavior

### Requirement: Score-and-gate pass
Each candidate chunk SHALL be evaluated by a relevance `score` and a keep/drop `noul` gate. Survivors SHALL be ordered by relevance score; dropped candidates SHALL NOT appear in results. Surviving results SHALL carry `relevance` (the laya score) alongside the existing fused `score`.

#### Scenario: Mixed candidates
- **WHEN** the candidate pool contains both relevant and irrelevant chunks
- **THEN** results contain only gate-passing chunks ordered best-first by relevance

#### Scenario: Everything dropped
- **WHEN** no candidate passes the gate and the retry budget is exhausted
- **THEN** results are empty and `rerank` metadata reports zero passed — this is not an error

### Requirement: Bounded widening loop
If fewer than `top_k` candidates pass the gate, the candidate pool SHALL widen (doubling per round, up to 3 rounds total) and scoring SHALL repeat on the new pool, until `top_k` survivors exist or the budget is exhausted.

#### Scenario: Second round finds enough
- **WHEN** round 1 yields too few survivors but the widened pool contains enough relevant chunks
- **THEN** `query()` returns `top_k` results and metadata reports `rounds_used: 2`

#### Scenario: Budget exhausted
- **WHEN** 3 rounds still yield fewer than `top_k` survivors
- **THEN** `query()` returns only the survivors with metadata `rounds_used: 3` and the true `passed` count

### Requirement: Rerank metadata
`QueryOutput.rerank` SHALL report `status`, `rounds_used`, `candidates_evaluated`, and `passed` whenever the pass ran or was attempted.

#### Scenario: Metadata present
- **WHEN** the rerank pass ran
- **THEN** the caller can read how many candidates were evaluated and how many survived

### Requirement: Degrade on reranker failure
If the reranker is unreachable or errors, `query()` SHALL return the normal un-reranked results and set `rerank.status` to indicate unavailability — never fail the query.

#### Scenario: laya-serve down
- **WHEN** the reranker raises a connection error
- **THEN** `query()` returns fused results as usual with `rerank.status: "unavailable"`

### Requirement: MCP metadata passthrough
`query_book` SHALL include the `rerank` metadata and per-result `relevance` in its JSON output when present, with no change to its signature or existing fields.

#### Scenario: Agent sees rerank outcome
- **WHEN** `query_book` is called with rerank active
- **THEN** the JSON response contains `rerank` metadata and `relevance` per result
