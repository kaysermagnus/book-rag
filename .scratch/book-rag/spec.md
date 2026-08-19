# Spec: book-rag v1

Status: ready-for-agent

A CLI utility that transforms a book (EPUB/TXT) into an index so agents can retrieve verbatim, high-fidelity chunks with provenance — grounding their answers in what the book actually says. See `CONTEXT.md` for vocabulary and ADR-0001 for the retrieve-only boundary.

## Problem Statement

When agents answer questions about a book, they hallucinate: invented quotes, misattributed ideas, plausible-but-absent details. The books I want them to reason about live on my machine as EPUB and TXT files, and there is no way for an agent to *read* them — only to confabulate about them. I need a way to make a book queryable with verbatim fidelity, locally, without sending my reading material to third-party APIs.

## Solution

`book-rag`, a local CLI utility with two commands:

- `book-rag index <file>` — transforms a book into an **index**: a single self-contained SQLite file created beside the source. The book is parsed, normalized to **verbatim** text, split into structure-aware **chunks**, embedded with a local model (`nomic-embed-text` via Ollama), and stored with **provenance** (title + structural path).
- `book-rag query <index> "<question>"` — retrieves the best-matching chunks via hybrid search (vector + keyword, rank-fused) and prints them as JSON: verbatim text plus provenance. No generative LLM anywhere in the pipeline (ADR-0001) — the agent that queries owns generation and citation.

Everything runs locally: books never leave the machine, no API keys, no servers. An index is one file — delete it and rebuild with one command.

## User Stories

1. As a user, I want to run `book-rag index <file.epub>` and have an index file appear beside the book, so that preparing a book for agent use is one command.
2. As a user, I want the same one-command indexing for `.txt` files, so that plain-text books work identically.
3. As a user, when I point the tool at an unsupported format (e.g. a PDF), I want a clear error naming the format and listing supported ones, so that I understand the refusal instead of getting a crash.
4. As a user, when a source has no extractable text (image-only EPUB, empty file), I want it rejected with a clear error, so that I never silently end up with an empty index.
5. As a user, on first use without Ollama or the model present, I want the exact setup command printed (`ollama pull nomic-embed-text`), so that friction is one copy-paste.
6. As a user, I want `book-rag query <index> "<question>"` to print ranked results as JSON on stdout, so that agents can parse output unambiguously.
7. As a user, I want a `--text` flag for human-readable output, so that I can spot-check retrieval quality in the terminal.
8. As a user, I want every result to carry provenance (book title + structural path like `Part II › Chapter 3`), so that I and my agents can cite exactly where a passage comes from.
9. As an agent, I want retrieved text to be verbatim — the book's exact words and punctuation minus mechanical extraction artifacts — so that I can quote it without drift.
10. As an agent, I want a `mode` field in the output (`hybrid` or `keyword-fallback`), so that I know when results are degraded rather than discovering it silently.
11. As a user with Ollama down, I still want keyword-only results with a loud warning, so that retrieval keeps working offline.
12. As a user asking paraphrased questions, I want vector matching to find semantically relevant chunks, so that I don't need the book's own wording.
13. As a user looking up exact names or technical terms, I want keyword (BM25) matching fused into the ranking, so that embeddings' classic weak spot is covered.
14. As a user, I want top-5 results by default with a `--top N` override, so that I control context volume.
15. As a user, I want re-running `book-rag index` on an already-indexed book to rebuild it from scratch, so that re-indexing after a tool upgrade never leaves stale state.
16. As a user, I want the book's title and author auto-extracted from EPUB metadata, falling back to the filename stem, overridable with `--title`/`--author`, so that provenance is meaningful without manual work.
17. As a user indexing long books, I want progress displayed on stderr while embedding, so that stdout stays pure JSON and I know the job is alive.
18. As a user, I want chunks bounded by the book's own structure (part › chapter › section), so that retrieved passages are semantically coherent units.
19. As a user with large chapters, I want them sub-split at paragraph boundaries with overlap, so that no chunk exceeds the embedding model's comfort zone and boundary context survives.
20. As a user with TXT books that use Markdown headings, I want those headings to become section boundaries, so that exported books keep their structure.
21. As a user with structureless TXT, I want paragraph-window chunks as the fallback, so that every book is indexable.
22. As a user with non-UTF-8 TXT files, I want automatic encoding detection, so that accented text isn't mojibake in results.
23. As a user, I want to inspect an index with any ordinary SQLite tool, so that the artifact is transparent and debuggable.
24. As an agent, I want a stable JSON output shape across versions, so that my parsing doesn't break on upgrades.

## Implementation Decisions

- **Toolchain**: Python 3.12 managed by `uv`; a single package exposing the `book-rag` console script; runtime deps: `ebooklib`, `sqlite-vec`, `charset-normalizer`; dev deps: `pytest`, `ruff`.
- **Architecture**: a thin CLI over two public entry points — `build_index(source_path) -> Index` and `query(index_path, question, top_k=5) -> results`. The pipeline inside is: parse → normalize (verbatim) → extract structure → chunk → embed → store. The CLI adds argument parsing, output formatting (JSON/`--text`), and progress on stderr; nothing else.
- **Format support**: EPUB via `ebooklib` (structure from the EPUB3 nav, falling back to the EPUB2 NCX TOC), TXT (Markdown `#`/`##` lines as section boundaries; otherwise flat), and PDF via `pypdfium2` (one section per page; `path` is `"Page N"`, `page` carries the 1-based page number). PDF outline / bookmark titles are a later refinement. Scanned / image-only PDFs yield no text and are rejected by the `MIN_TEXT_CHARS` guard; OCR is out of scope.
- **Normalization (verbatim)**: line-break hyphens rejoined, soft hyphens dropped, ligatures expanded, whitespace collapsed; words and punctuation otherwise untouched.
- **Chunking**: structure-first — a chunk is bounded by document structure and capped at 1024 tokens, sub-split at paragraph boundaries with ~128-token overlap; every chunk carries its structural path.
- **Embedding**: `nomic-embed-text` via the Ollama HTTP API, behind a small embedder interface so the model is swappable (e.g. `bge-m3` for non-English shelves) without touching the pipeline. Availability is checked up front; a missing model prints the exact pull command and exits.
- **Index storage**: one SQLite file per book, named `<stem>.rag`, created beside the source. Rebuilding is idempotent (delete + recreate). Schema, from the design session:

  ```
  meta(key TEXT PRIMARY KEY, value TEXT)          -- title, author, schema_version, embedder model
  chunks(id INTEGER PK, path TEXT, text TEXT)     -- verbatim chunk + structural path
  chunks_fts(chunks) USING fts5(text)             -- BM25 keyword index
  chunks_vec(id INTEGER PK, embedding FLOAT[768]) -- sqlite-vec KNN index
  ```

- **Retrieval**: vector KNN and FTS5/BM25 run in parallel, fused with reciprocal-rank-fusion, top-k (default 5). If the embedder is unavailable at query time, retrieval degrades to FTS5-only and the output carries `mode: "keyword-fallback"` plus a warning on stderr.
- **Output contract**, from the design session:

  ```json
  {
    "book": "Moby-Dick",
    "mode": "hybrid",
    "results": [
      { "rank": 1, "score": 0.83, "path": "Part II › Chapter 3", "text": "…" }
    ]
  }
  ```

  No `page` field for EPUB/TXT sources (no page concept); PDF sources populate it with the 1-based page number.
- **Metadata**: EPUB OPF title/author when present and sane, else the filename stem, overridable via `--title`/`--author`.
- **TXT encoding**: UTF-8 strict first, `charset-normalizer` detection as fallback.

## Testing Decisions

- **One seam**: the public entry points `build_index` / `query`. The CLI is a thin wrapper and gets smoke tests only. Good tests assert external behavior — stored chunk text, boundaries, and provenance as observed through `build_index`; ranking, fusion behavior, and JSON shape as observed through `query`. No unit tests on internals (normalizer, chunker, fusion are exercised *through* the seam).
- **Fake embedder**: injected through the already-decided embedder interface, so full-pipeline tests run fast and deterministically with no Ollama dependency.
- **Fixture books**: a small EPUB (nav + multiple chapters), a TXT with Markdown headings, a structureless TXT, an image-only EPUB (rejection case), and a non-UTF-8 TXT.
- **Ollama-gated integration tests** (skipped when Ollama is not running): real `nomic-embed-text` end-to-end on a small fixture book — for known questions, the correct chunk must rank first. This is what actually validates the high-fidelity promise; everything else tests mechanics, not quality.
- **Keyword-fallback path** is fully testable without Ollama (FTS5 needs no model).

## Out of Scope

- **Scanned PDF OCR** — text-layer PDFs are supported; image-only PDFs are rejected with the same "no extractable text" error as image-only EPUBs. OCR is a later addition.
- **PDF outline / bookmark structure** — PDFs currently use page numbers as provenance (`"Page N"`); mapping the PDF outline to chapter paths is a later refinement.
- **Generation** — no answer synthesis in the tool (ADR-0001). A future `ask` subcommand would be a new surface, not a change to this contract.
- **Multi-book shared index / cross-book search** — the schema carries book identity, so merging is a later query-layer feature.
- **Reranking models** — hybrid + RRF only in v1.
- **DRM-protected EPUBs** — rejected like any unreadable source.
- **HTTP or MCP server layers** — the library core makes these thin add-ons later; v1 is CLI.
- **Incremental indexing** — rebuild-from-scratch only.

## Further Notes

- Ollama must be running with `nomic-embed-text` pulled for hybrid indexing/querying; the CLI detects and instructs.
- `nomic-embed-text` is English-centric. Non-English books work but retrieve less well; swapping to `bge-m3` via the embedder interface is a configuration change, not an architectural one.
- The index file is disposable by design: delete + reindex is the recovery path for any corruption or staleness.
- Progress and warnings go to stderr; stdout is reserved for the JSON payload so agents can pipe cleanly.
