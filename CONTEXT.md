# Book-to-RAG

A CLI utility that transforms books into indexes so agents can retrieve verbatim source text with provenance — grounding their answers in what the book actually says.

## Language

**Book**:
The input document — an EPUB or TXT file — that the tool ingests.
_Avoid_: source, corpus, dataset

**Chunk**:
A contiguous span of text bounded by the document's structure (part › chapter › section), sub-split at paragraph boundaries when it exceeds a maximum size. A chunk is both the unit stored in an index and what retrieval returns.
_Avoid_: passage, snippet, shard

**Index**:
The artifact a book is transformed into: one book's chunks with their embeddings and provenance, stored as a single file. One index per book.
_Avoid_: RAG, vector database

**Provenance**:
The metadata attached to a chunk: book title, structural path (part › chapter › section), and page number when the source format has pages.
_Avoid_: citation — a citation is what an agent writes in its answer; the tool produces provenance

**Verbatim**:
Faithful to the book's words and punctuation, with mechanical extraction artifacts removed — line-break hyphens rejoined, soft hyphens dropped, ligatures expanded, whitespace collapsed. Not byte-identity to the source file.
_Avoid_: "byte-identical", "raw extraction"

**RAG**:
The general technique (retrieval-augmented generation). Not a thing this repo produces — the repo produces indexes.
_Avoid_: "a rag" as a noun for the artifact
