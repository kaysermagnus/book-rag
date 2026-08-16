# syntax=docker/dockerfile:1

# --- Build stage: uv resolves and installs (wheels only, no compiler needed) ---
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
RUN uv sync --frozen --no-dev --extra mcp

# --- Runtime: slim Python + the built venv, nothing else ---
FROM python:3.12-slim
RUN useradd -m bookrag && mkdir /data && chown bookrag /data
WORKDIR /app
# The venv holds an editable install pointing at /app/src, so ship the source too.
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"
USER bookrag
WORKDIR /data
VOLUME /data
EXPOSE 8080
# Default: serve MCP over streamable-http. For one-shot CLI use, override the command:
#   docker run --rm -v $PWD/data:/data book-rag index /data/MyBook.epub
CMD ["book-rag-mcp", "--transport", "http", "--host", "0.0.0.0", "--port", "8080"]
