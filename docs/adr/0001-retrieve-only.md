# Retrieve-only: generation is the agent's job

Status: accepted

A "RAG" tool is usually expected to generate answers, so this needs recording: `book-rag query` returns verbatim chunks with provenance and never calls a generative LLM — the only model in the pipeline is the local embedding model. Generation belongs to the agent that queries, which owns the citation contract (answer only from retrieved chunks, and cite them); keeping generation out of the tool keeps it deterministic, offline-capable, and free of per-query API cost.
