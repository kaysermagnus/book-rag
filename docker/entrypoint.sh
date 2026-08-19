#!/usr/bin/env sh
# Bring up the in-container Ollama, ensure the embedding model is present, then
# exec the book-rag command (default: the MCP server). The model is pulled into
# the /ollama volume on first run, so subsequent starts are offline and fast.
set -eu

OLLAMA_MODEL="${OLLAMA_MODEL:-nomic-embed-text}"

# 1. Start Ollama in the background. Logs go to stderr for visibility.
ollama serve >&2 &

# 2. Wait for the API to answer (max ~60s). `ollama list` hits the same endpoint,
#    so it doubles as a readiness probe without needing curl in the runtime image.
i=0
until ollama list >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -gt 60 ]; then
    echo "Ollama did not become ready in 60s" >&2
    exit 1
  fi
  sleep 1
done

# 3. Pull the embedding model if it isn't already in the volume. The first-run
#    pull can hit transient registry 503s, so retry a few times before giving up
#    (the compose `restart: unless-stopped` policy covers longer outages).
if ! ollama list 2>/dev/null | grep -q "^$OLLAMA_MODEL"; then
  echo "Pulling $OLLAMA_MODEL (first run only)..." >&2
  attempt=0
  until ollama pull "$OLLAMA_MODEL" >&2; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 5 ]; then
      echo "Failed to pull $OLLAMA_MODEL after 5 attempts" >&2
      exit 1
    fi
    echo "Pull failed (attempt $attempt/5), retrying in 5s..." >&2
    sleep 5
  done
fi

# 4. Hand off to the container CMD (book-rag-mcp ... or a one-shot CLI command).
exec "$@"
