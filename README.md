# book-rag: High-Fidelity Book Indexer for Agent Grounding

**Tagline:** Transform large volumes of text into surgically precise, local SQLite indexes for verifiable Retrieval-Augmented Generation (RAG).

---

## 📖 About book-rag

`book-rag` is a command-line utility written in Python designed to solve the critical problem of grounding Large Language Models (LLMs) with high-fidelity, verifiable source material. Instead of feeding entire books into a context window and risking hallucination or information loss, `book-rag` creates a compact, local SQLite index (`.rag`) that allows querying agents to retrieve the *exact* passages needed for accurate response generation.

**This tool is an Indexer and Retriever; it does not generate text.** Generation belongs entirely to the querying agent.

## ✨ Features & Why It Exists

* **Verbatim Grounding:** Retrieves chunks with minimal loss of fidelity, ensuring the agent bases its answer on the original source text.
* **Local & Private:** All processing, including embedding generation via Ollama (`nomic-embed-text`), occurs entirely on your local machine. No cloud APIs or keys are required for indexing or retrieval.
* **Structure Preservation:** Supports complex source formats (EPUB, TXT) and preserves structural metadata alongside the content chunks.
* **Hybrid Retrieval:** Combines vector similarity search (KNN) with keyword matching (FTS5/BM25), fused using Reciprocal Rank Fusion ($\text{RRF}_{K=60}$) for optimal recall.
* **Efficiency:** Indexes are single-file SQLite databases (`<stem>.rag`), making management and recovery straightforward.

### Phase 0: Installation & Setup (One-Time)

This phase covers setting up the isolated environment required to run `book-rag`. This should be done once per machine/project clone.

1. **Clone Repository:** Clone the `book-rag` repository to your local machine.
2. **Create Virtual Environment:** Navigate into the project root and run:

   ```bash
   uv venv
   ```

3. **Activate Environment:** Activate the newly created virtual environment:

   ```bash
   source .venv/bin/activate
   ```

4. **Install Dependencies:** Install all required packages listed in the dependency file:

   ```bash
   uv sync --extra mcp   # plain `uv sync` also works; the extra is only needed for the MCP server (Phase 4)
   ```

### Phase 1: Prerequisites Check (One-Time Setup)

Before running any commands, ensure the following are operational on your machine:

1. **Python:** Ensure Python is installed and you have installed the `book-rag` package dependencies.
2. **Ollama:** Ensure Ollama is running locally and has pulled the required embedding model (`nomic-embed-text`). This handles all vectorization.

### Phase 2: Indexing (The Build Phase)

This step processes your source material into a searchable, local index file (`.rag`). This is the *only* time you need to point to the original book file.

**Command:**

```bash
book-rag index <source_file>
```

*Example:* `book-rag index MyBook.epub`

**What this does:** The tool reads `<source_file>`, chunks it into contextually relevant passages, generates embeddings using Ollama, and compiles everything into a local SQLite index file named `<stem>.rag` (e.g., `MyBook.rag`).

### Phase 3: Querying (The Run Phase)

Once you have the `.rag` file, you use it to ask questions. The tool retrieves the most relevant passages from the index for your agent to read.

**Command:**

```bash
book-rag query <index_file> "<your question>"
```

*Example:* `book-rag query MyBook.rag "What is the main theme of the novel?"`

**Output:** The command outputs the retrieved, contextually relevant passages to standard output (`stdout`). Use the `--text` flag if you want a human-readable summary of those passages printed to standard error (`stderr`) during testing.

### 🛑 Error Handling & Troubleshooting

* **Missing Index File:** If you run `book-rag query` but the `<index_file>` does not exist, the tool cannot proceed. You must complete Phase 2 first.
* **Retrieval Failure:** If the query runs but returns no context, it means the passages matching your question were not found in the index. Try rephrasing your question or checking if the original book file was indexed correctly.

### Phase 4: Agent Integration via MCP

Instead of having an agent shell out to `book-rag query` (parsing stdout, handling exit codes), run the bundled MCP server. It exposes retrieval as two structured, read-only tools over stdio:

* `list_indexes(directory)` — discover available `.rag` indexes with title/author.
* `query_book(index, question, top_k)` — the same hybrid retrieval as Phase 3, returned as structured JSON.

**Run it:**

```bash
book-rag-mcp   # stdio server; wire it into your agent's MCP client config
```

The server inherits the CLI's contracts: verbatim chunks with provenance, graceful degradation to keyword-only when Ollama is down (`mode: "keyword-fallback"`), and the citation obligation (the agent answers only from retrieved chunks). Index building is deliberately not exposed — see ADR-0002.

### Phase 5: Running in Docker

The repo ships a self-contained multi-stage image: slim Python + the built venv + a CPU-only Ollama binary (CUDA/Vulkan runners stripped for a minimal footprint; ~360 MB). The `nomic-embed-text` model is pulled into a volume on first run, so subsequent starts are offline and fast.

```bash
docker build -t book-rag .   # or: docker compose up --build
```

**MCP server (the image's default command):** the entrypoint starts Ollama, ensures `nomic-embed-text` is present, then serves streamable-http on port 8080. Books/`.rag` indexes live in `/data`, pulled Ollama models in `/ollama` — both survive container recreation:

```bash
docker run -d -p 8080:8080 -v $PWD/data:/data -v ollama-models:/ollama book-rag
```

**One-shot CLI use:** override the command, e.g. to index a book:

```bash
docker run --rm -v $PWD/data:/data -v ollama-models:/ollama \
  book-rag index /data/MyBook.epub
```

The image is self-contained — no host Ollama needed. To use a different embedding model, set `OLLAMA_MODEL=<name>`. To point at an external Ollama instead of the bundled one, override `OLLAMA_BASE_URL` (e.g. `http://host.docker.internal:11434`; on Linux add `--add-host=host.docker.internal:host-gateway`). `docker-compose.yml` wires up both volumes by default.

---
*This README is intentionally dense to serve as both a user guide and an architectural specification document.*

## 🔬 Technical Deep Dive & ADRs (Advanced Users)

This section details the architectural choices made to meet specific constraints:

### Architectural Decisions (ADR-0001)

* **Retrieval-Only Mandate:** `book-rag` is strictly a retrieval system. It never invokes a generative LLM. The responsibility for synthesis, summarization, and answer generation lies with the downstream querying agent.
* **Data Locality:** All processing is designed to be local and private, relying on local embedding models (Ollama) rather than external API services.

### Agent Interface (ADR-0002)

* **MCP Server:** A local stdio MCP server (`book-rag-mcp`, optional `mcp` extra) exposes retrieval to external agents as two read-only tools — `list_indexes` and `query_book`. Raw CLI access is fragile for agents (exact syntax, stdout parsing, exit codes); the MCP layer gives a structured, deterministic contract.
* **Read-Only Phase 1:** Index building is a write operation and is not exposed; adding it requires an explicit decision.

### Indexing & Storage

* **File Format Support:** Supports ingestion from **EPUB** (utilizing `ebooklib` v0.20 with namespace shims) and **TXT** (where Markdown headings are parsed to define document structure).
* **Storage Schema:** The `<stem>.rag` file is a self-contained SQLite database containing tables for `meta`, `chunks`, FTS5 indexing, and the vector store (`sqlite-vec`).
* **Recovery:** Index rebuilding is treated as a recovery operation, ensuring data integrity. No Write-Ahead Logging (WAL) mode is used for simplicity and predictable recovery paths.

### Chunking & Text Processing

* **Chunking Strategy:** Chunks are bounded by an estimated **1024 tokens**, with a controlled overlap of $\sim 128$ tokens occurring precisely at paragraph boundaries to maintain contextual flow.
* **Normalization:** Input text undergoes normalization (e.g., ligatures and soft hyphens are resolved) to create clean, searchable chunks, while the original source structure is meticulously preserved in associated metadata.

### Retrieval Protocol

* **Hybrid Search:** The system employs a dual-path retrieval mechanism: high-dimensional vector search (KNN) and full-text indexing (FTS5/BM25).
* **Fusion:** Results from both paths are combined using **Reciprocal Rank Fusion ($\text{RRF}_{K=60}$)**, and the top 5 candidates are passed to the agent.
* **Degradation:** If the embedding service (Ollama) is unavailable, the system gracefully degrades to keyword-only retrieval using FTS5.

### Protocols

* **Embedder Abstraction:** A swappable `Embedder` Protocol (`dim: int`, `embed(texts) -> list[list[float]]`) abstracts the underlying embedding service, allowing easy swapping between Ollama and mock/testing implementations.

---
*This README is intentionally dense to serve as both a user guide and an architectural specification document.*
