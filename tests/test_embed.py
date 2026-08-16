"""OllamaEmbedder: env-var configuration (containers pointing at remote Ollama)."""

from __future__ import annotations

from book_rag.embed import OllamaEmbedder


def test_defaults_when_no_env(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    e = OllamaEmbedder()
    assert e.base_url == "http://localhost:11434"
    assert e.model == "nomic-embed-text"


def test_env_base_url_used_when_no_arg(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434/")
    e = OllamaEmbedder()
    assert e.base_url == "http://host.docker.internal:11434"  # trailing slash stripped


def test_env_model_used_when_no_arg(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "some-other-model")
    e = OllamaEmbedder()
    assert e.model == "some-other-model"


def test_explicit_args_win_over_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "some-other-model")
    e = OllamaEmbedder(model="nomic-embed-text", base_url="http://ollama:11434")
    assert e.model == "nomic-embed-text"
    assert e.base_url == "http://ollama:11434"
