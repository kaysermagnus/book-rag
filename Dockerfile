# syntax=docker/dockerfile:1

# --- Build stage 1: uv resolves and installs (wheels only, no compiler needed) ---
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
RUN uv sync --frozen --no-dev --extra mcp

# --- Build stage 2: fetch Ollama, strip GPU libs for a CPU-only minimal footprint ---
# The full linux tarball ships CUDA + Vulkan runners (~1GB+). We keep only the
# CPU subset: the binary + libggml/libllama CPU runners. zstd is needed only to
# extract here, never ships in the runtime image.
FROM debian:bookworm-slim AS ollama
ARG OLLAMA_VERSION=0.32.14
# TARGETARCH is injected by BuildKit (amd64 on x86, arm64 on Apple Silicon).
ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends curl zstd ca-certificates \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /tmp/ollama
RUN curl -fsSLO "https://github.com/ollama/ollama/releases/download/v${OLLAMA_VERSION}/ollama-linux-${TARGETARCH}.tar.zst" \
 && tar --zstd -xf ollama-linux-${TARGETARCH}.tar.zst \
 && rm ollama-linux-${TARGETARCH}.tar.zst \
 && rm -rf lib/ollama/cuda_v12 lib/ollama/cuda_v13 lib/ollama/vulkan

# --- Runtime: slim Python + the built venv + CPU-only Ollama, nothing else ---
FROM python:3.12-slim
# ca-certificates so Ollama can reach ollama.com on first model pull.
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Ollama binary + CPU-only libs, in the layout the official installer uses
# (binary in /usr/local/bin, libs in /usr/local/lib/ollama).
COPY --from=ollama /tmp/ollama/bin/ollama /usr/local/bin/ollama
COPY --from=ollama /tmp/ollama/lib/ollama /usr/local/lib/ollama

RUN useradd -m bookrag && mkdir /data /ollama && chown bookrag /data /ollama

WORKDIR /app
# The venv holds an editable install pointing at /app/src, so ship the source too.
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    # Point book-rag at the in-container Ollama, and pin Ollama to localhost.
    OLLAMA_BASE_URL=http://127.0.0.1:11434 \
    OLLAMA_HOST=127.0.0.1:11434 \
    # Persist pulled models in the /ollama volume (not the throwaway image layer).
    OLLAMA_MODELS=/ollama

USER bookrag
WORKDIR /data
VOLUME /data /ollama
EXPOSE 8080
# Entrypoint brings up Ollama, pulls nomic-embed-text on first run, then execs the CMD.
# For one-shot CLI use, override the command:
#   docker run --rm -v $PWD/data:/data book-rag index /data/MyBook.epub
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["book-rag-mcp", "--transport", "http", "--host", "0.0.0.0", "--port", "8080"]
