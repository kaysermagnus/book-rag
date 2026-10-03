"""rerank: optional decision-model pass inside query() — tested at the
public seam with an injected fake reranker (mirrors the embedder DI)."""

from __future__ import annotations

from book_rag import build_index, query


def _build(tmp_path, fake_embedder, sections=6):
    """An index with `sections` keyword-distinct sections to retrieve from."""
    body = "\n".join(
        f"# Section {i}\n\n"
        f"The quokka{i} alpaca{i} zebra{i} gather in meadow{i} to discuss topic {i}.\n"
        for i in range(sections)
    )
    src = tmp_path / "book.txt"
    src.write_text(body, encoding="utf-8")
    return build_index(src, embedder=fake_embedder)


class FakeReranker:
    """Canned (relevance, keep) verdicts per text; records what it saw."""

    def __init__(self, verdicts: dict[str, tuple[float, float]] | None = None):
        self.verdicts = verdicts or {}  # substring -> (relevance, keep_p)
        self.calls: list[list[str]] = []

    def evaluate(self, question: str, texts: list[str]) -> list[tuple[float, float]]:
        self.calls.append(list(texts))
        out = []
        for t in texts:
            hit = next((v for k, v in self.verdicts.items() if k in t), None)
            out.append(hit if hit else (3.0, 0.9))  # default: clearly relevant
        return out


class DeadReranker:
    def evaluate(self, question, texts):
        raise ConnectionError("laya-serve down")


def test_gate_drops_irrelevant_and_orders_survivors(tmp_path, fake_embedder):
    idx = _build(tmp_path, fake_embedder)
    rk = FakeReranker(
        {
            "quokka0": (4.5, 0.9),   # best
            "quokka2": (1.0, 0.1),   # gated out
            "quokka1": (3.5, 0.8),
        }
    )
    out = query(idx, "quokka alpaca meadow", top_k=3, embedder=fake_embedder, reranker=rk)
    texts = [r.text for r in out.results]
    assert not any("quokka2" in t for t in texts)
    assert out.results[0].relevance == 4.5
    assert [r.rank for r in out.results] == list(range(1, len(out.results) + 1))


def test_loop_widens_until_enough_survivors(tmp_path, fake_embedder):
    # 14 sections > first pool (top_k*2=6): round 2 always has new candidates
    idx = _build(tmp_path, fake_embedder, sections=14)
    # everything in the first pool gated; later pools pass -> second round
    rk = FakeReranker({})
    calls = []

    def gate(question, texts):
        calls.append(len(texts))
        round_ = len(calls)
        if round_ == 1:
            return [(1.0, 0.1)] * len(texts)  # nothing survives round 1
        return [(3.0, 0.9)] * len(texts)

    rk.evaluate = gate
    out = query(idx, "quokka alpaca meadow", top_k=3, embedder=fake_embedder, reranker=rk)
    meta = out.rerank
    assert meta is not None
    assert meta["status"] == "ok"
    assert meta["rounds_used"] == 2
    assert len(calls) == 2  # pool widened once


def test_never_reevaluates_candidates(tmp_path, fake_embedder):
    idx = _build(tmp_path, fake_embedder, sections=14)
    seen: list[str] = []
    rk = FakeReranker({})

    def gate(question, texts):
        seen.extend(texts)
        if len(seen) == len(texts):  # first call only
            return [(1.0, 0.1)] * len(texts)
        return [(3.0, 0.9)] * len(texts)

    rk.evaluate = gate
    query(idx, "quokka alpaca meadow", top_k=3, embedder=fake_embedder, reranker=rk)
    assert len(seen) == len(set(seen)), "a candidate was scored twice"


def test_exhaustion_returns_survivors_and_honest_metadata(tmp_path, fake_embedder):
    idx = _build(tmp_path, fake_embedder, sections=40)  # > top_k*8 pool: rounds still exhaust at 3
    rk = FakeReranker({})
    rk.evaluate = lambda question, texts: [
        (4.0, 0.9) if "quokka0" in t else (0.5, 0.1) for t in texts
    ]
    out = query(idx, "quokka alpaca meadow", top_k=5, embedder=fake_embedder, reranker=rk)
    meta = out.rerank
    assert meta is not None
    assert meta["status"] == "ok"
    assert meta["rounds_used"] == 3
    assert meta["passed"] < 5
    assert len(out.results) == meta["passed"]


def test_laya_url_env_wires_default_reranker(tmp_path, fake_embedder, monkeypatch):
    """LAYA_URL set + no injected reranker -> the env-built reranker runs."""
    from book_rag import rerank as rerank_mod

    monkeypatch.setenv("LAYA_URL", "http://laya-serve:8090")
    monkeypatch.setattr(rerank_mod, "LayaReranker", lambda url, **kw: FakeReranker())
    idx = _build(tmp_path, fake_embedder)
    out = query(idx, "quokka alpaca meadow", embedder=fake_embedder)
    assert out.rerank is not None and out.rerank["status"] == "ok"


def test_reranker_failure_degrades_never_fails(tmp_path, fake_embedder):
    idx = _build(tmp_path, fake_embedder)
    out = query(
        idx, "quokka alpaca meadow", embedder=fake_embedder, reranker=DeadReranker()
    )
    assert out.rerank is not None and out.rerank["status"] == "unavailable"
    assert len(out.results) > 0  # normal fused results still returned
    assert all(r.relevance is None for r in out.results)


def test_rerank_adds_metadata_and_relevance(tmp_path, fake_embedder):
    idx = _build(tmp_path, fake_embedder)
    out = query(idx, "quokka alpaca meadow", embedder=fake_embedder, reranker=FakeReranker())
    assert out.rerank is not None
    assert out.rerank["status"] == "ok"
    assert all(r.relevance is not None for r in out.results)


def test_no_reranker_is_byte_identical(tmp_path, fake_embedder):
    idx = _build(tmp_path, fake_embedder)
    out = query(idx, "quokka alpaca meadow", embedder=fake_embedder)
    assert out.rerank is None
    assert all(r.relevance is None for r in out.results)
