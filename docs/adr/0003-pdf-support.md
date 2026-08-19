# PDF support: pypdfium2 + page as first-class provenance

Status: accepted

PDF support was deferred in v1 (ADR/spec: "the pipeline is format-agnostic, so PDF support is a later extension, not a rework"). This records the two decisions made when it landed.

**Library: pypdfium2.** Books are prose-heavy; reading order and layout matter more than tables. pypdfium2 (Google PDFium bindings) gives reading-order text per page via `get_textpage().get_text_range()` — good enough for prose without paying for a full layout engine (pdfplumber) or a heavier native stack. It's a single binary-wheel dependency. Each page becomes one section; `path` is `"Page N"`.

**Page as first-class provenance.** The spec said the `page` field "appears when PDF support lands." Rather than smuggling page numbers into the existing `path` string, `page: int | None` was added to `Section`, `Chunk`, and `Result`; the `chunks` table gained a `page INTEGER` column (schema bumped to 2); and the JSON / MCP output contracts now include `page` (null for EPUB/TXT). This cost ~80% of the diff but makes page queryable as structured data rather than parseable text — the right time to do it, since retrofitting it later would touch every stored index.

Schema-version mismatch on read is handled by failing fast with `CorruptIndexError` and a "delete and reindex" message, matching the spec's "delete + reindex is the recovery path" — no in-place migration.

Out of scope here: PDF outline / bookmark titles as chapter paths (page numbers only for now), and OCR for scanned/image-only PDFs (rejected by the existing `MIN_TEXT_CHARS` guard).
