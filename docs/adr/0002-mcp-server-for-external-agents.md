# MCP server as the interface for external agents

Status: accepted

External LLM agents need to query books indexed by this CLI, but raw CLI access is fragile — an agent must know the exact `book-rag query` syntax, parse JSON from stdout, and treat exit codes as errors. We will run a local MCP server (stdio by default, streamable-http for networked agents and the Docker image) that exposes the CLI's retrieval as two structured, read-only tools: `list_indexes` (discover available book indexes with title/author) and `query_book` (hybrid retrieval of verbatim chunks with provenance, degrading to keyword-only when the embedder is down — same contract as `book-rag query`). This keeps the agent-facing interface deterministic and side-effect-free in phase 1, and gives a single place to gate index building (a write operation) behind an explicit decision later.
