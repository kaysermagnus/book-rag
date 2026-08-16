"""Embedding: local Ollama by default, swappable behind a small interface.

The embedder is the one piece of the pipeline that talks to the outside
world — and the only thing retrieval can degrade without. Tests inject a
fake; the CLI uses Ollama (``nomic-embed-text``, 768 dims, local).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Protocol

DEFAULT_MODEL = "nomic-embed-text"
DEFAULT_BASE_URL = "http://localhost:11434"


class Embedder(Protocol):
    """Anything that turns texts into fixed-size vectors."""

    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class EmbedderError(RuntimeError):
    """The embedder is unavailable (Ollama down, model not pulled)."""


class OllamaEmbedder:
    """Embeds via the local Ollama HTTP API (stdlib only)."""

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        dim: int = 768,
    ) -> None:
        # Env vars let containers point at a host or sibling-container Ollama
        # (e.g. OLLAMA_BASE_URL=http://host.docker.internal:11434); explicit
        # constructor args still win.
        self.model = model or os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL)
        env_base_url = os.environ.get("OLLAMA_BASE_URL", DEFAULT_BASE_URL)
        self.base_url = (base_url or env_base_url).rstrip("/")
        self.dim = dim

    def ensure_ready(self) -> None:
        """Fail fast with an actionable message if we cannot embed."""
        try:
            data = self._get("/api/tags")
        except (urllib.error.URLError, OSError) as e:
            raise EmbedderError(
                f"Ollama is not reachable at {self.base_url} — start it with `ollama serve`"
            ) from e
        names = {m.get("name", "") for m in data.get("models", [])}
        if not any(n == self.model or n.startswith(self.model + ":") for n in names):
            raise EmbedderError(
                f"model `{self.model}` is not pulled — run: ollama pull {self.model}"
            )

    def embed(self, texts: list[str]) -> list[list[float]]:
        # Ollama accepts a batch of inputs and returns one vector each,
        # in order, under the (always plural) "embeddings" key.
        try:
            data = self._post("/api/embed", {"model": self.model, "input": texts})
        except (urllib.error.URLError, OSError) as e:
            raise EmbedderError(f"Ollama request failed ({self.base_url}): {e}") from e
        vectors = data.get("embeddings")
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise EmbedderError("unexpected Ollama response shape")
        return vectors

    def _get(self, path: str) -> dict:
        request = urllib.request.Request(f"{self.base_url}{path}")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                return self._load_json(response)
        except (urllib.error.URLError, OSError) as e:
            raise EmbedderError(f"Ollama request failed ({self.base_url}): {e}") from e

    def _post(self, path: str, payload: dict) -> dict:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
                return self._load_json(response)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:200]
            raise EmbedderError(f"Ollama error {e.code}: {body}") from e
        except (urllib.error.URLError, OSError) as e:
            raise EmbedderError(f"Ollama request failed ({self.base_url}): {e}") from e

    @staticmethod
    def _load_json(response) -> dict:
        try:
            return json.load(response)
        except ValueError as e:  # non-JSON response body
            raise EmbedderError("Ollama returned a non-JSON response") from e
