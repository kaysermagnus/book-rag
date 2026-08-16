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

## 🚀 Getting Started

### Prerequisites

Before running commands, ensure you have the following installed and configured:

1. **Python:** The runtime environment for `book-rag`.
2. **Ollama:** Running locally with the required model (`nomic-embed-text`) to generate embeddings.
3. **Dependencies:** Install the Python package dependencies required by `book-rag`.

### Usage Guide (CLI)

All operations are performed via the command line. Output is directed to `stdout` by default (JSON format). Use `--text` flag for human-readable output, and monitor `stderr` for progress/warnings.

#### 1. Indexing a Book (Build the Knowledge Base)

This command processes your source file and builds the searchable `.rag` index.

```bash
# Index a book using its original file path
book-rag index /path/to/my_masterpiece.epub

# Index a book and output human-readable progress to stderr
book-rag index /path/to/my_masterpiece.epub --text
```

#### 2. Querying the Index (Retrieve Context)

This command searches the pre-built index and outputs the most relevant chunks.

```bash
# Query the index for context on a specific topic
book-rag query my_masterpiece.rag "What is the role of the protagonist in Act II?"

# Query and receive human-readable context chunks
book-rag query my_masterpiece.rag "main theme" --text
```

## 🔬 Technical Deep Dive & ADRs (Advanced Users)

This section details the architectural choices made to meet specific constraints:

### Architectural Decisions (ADR-0001)

* **Retrieval-Only Mandate:** `book-rag` is strictly a retrieval system. It never invokes a generative LLM. The responsibility for synthesis, summarization, and answer generation lies with the downstream querying agent.
* **Data Locality:** All processing is designed to be local and private, relying on local embedding models (Ollama) rather than external API services.

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
