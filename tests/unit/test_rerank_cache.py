# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""The LLM rerank cache: repeat searches must not pay the LLM again.

The MCP `boost_search` path passes ``smart=True`` on every call and measured
11.7-17 s per search, nearly all of it the rerank. The cache keys on a hash of
*exactly what the LLM sees* (query, limit, candidate listing), so it
self-invalidates on any reindex, ranking change, snippet change or candidate
drift — and stores only the parsed name order, so a hit replays through the
same deterministic reorder code as a live reply.
"""
from __future__ import annotations

import json

import pytest

from boost_cli.core import ai, paths, rag


def _hit(name, score, snippet=""):
    return {"entry": {"name": name, "tap": "acme/skills",
                      "skill_md": "%s/SKILL.md" % name},
            "score": score, "snippet": snippet, "content": "h-" + name}


@pytest.fixture()
def asked(monkeypatch, sandbox):
    """AI available; every ask recorded. Returns the call log."""
    calls: list[str] = []

    def fake_ask(prompt, *a, **k):
        calls.append(prompt)
        return '["beta", "alpha"]'

    monkeypatch.setattr(ai, "available", lambda: True)
    monkeypatch.setattr(ai, "ask", fake_ask)
    return calls


HITS = [_hit("alpha", 2.0, "alpha snippet"), _hit("beta", 1.0, "beta snippet")]


class TestCacheHit:
    def test_identical_rerank_answers_from_cache(self, asked):
        first, label1 = rag.rerank("find the widget", list(HITS))
        again, label2 = rag.rerank("find the widget", list(HITS))
        assert len(asked) == 1                       # one LLM call, not two
        assert label1 == label2 == rag.LLM_RANKER    # a hit IS the LLM's order
        assert first == again
        assert [h["entry"]["name"] for h in again][:2] == ["beta", "alpha"]

    def test_cached_order_applies_to_the_hits_passed_now(self, asked):
        """The cache stores the ORDER, not the hits: scores sit outside the
        candidate listing, so rescored hits still key to the same entry and
        get the cached order applied to their fresh values."""
        rag.rerank("find the widget", list(HITS))
        rescored = [_hit("alpha", 9.9, "alpha snippet"),
                    _hit("beta", 8.8, "beta snippet")]
        again, _ = rag.rerank("find the widget", rescored)
        assert len(asked) == 1
        assert [h["entry"]["name"] for h in again][:2] == ["beta", "alpha"]
        assert again[0]["score"] == 8.8              # fresh hit, cached order


class TestCacheKey:
    def test_a_different_query_misses(self, asked):
        rag.rerank("find the widget", list(HITS))
        rag.rerank("find the gadget", list(HITS))
        assert len(asked) == 2

    def test_a_different_candidate_listing_misses(self, asked):
        rag.rerank("find the widget", list(HITS))
        changed = [_hit("alpha", 2.0, "reworded snippet"), HITS[1]]
        rag.rerank("find the widget", changed)
        assert len(asked) == 2

    def test_a_different_limit_misses(self, asked):
        rag.rerank("find the widget", list(HITS), limit=10)
        rag.rerank("find the widget", list(HITS), limit=5)
        assert len(asked) == 2


class TestDegradation:
    def test_a_non_array_reply_is_not_cached(self, asked, monkeypatch):
        monkeypatch.setattr(ai, "ask", lambda *a, **k: (asked.append("x"),
                                                        "no json here")[1])
        _hits, label = rag.rerank("q", list(HITS), engine="BM25 full-content")
        assert label == "BM25 full-content"          # degrade, as today
        rag.rerank("q", list(HITS))
        assert len(asked) == 2                       # second call asks again

    def test_no_ai_means_no_cache_file(self, sandbox, monkeypatch):
        monkeypatch.setattr(ai, "available", lambda: False)
        _hits, label = rag.rerank("q", list(HITS), engine="dense vectors")
        assert label == "dense vectors"
        assert not rag.rerank_cache_path().exists()

    def test_corrupt_cache_file_degrades_and_heals(self, asked):
        paths.ensure_dirs()
        rag.rerank_cache_path().write_text("not json{", encoding="utf-8")
        rag.rerank("find the widget", list(HITS))
        assert len(asked) == 1                       # worked, asked live
        data = json.loads(rag.rerank_cache_path().read_text(encoding="utf-8"))
        assert len(data) == 1                        # rewritten valid

    def test_kill_switch_bypasses_read_and_write(self, asked, monkeypatch):
        monkeypatch.setenv("BOOST_NO_RERANK_CACHE", "1")
        rag.rerank("find the widget", list(HITS))
        rag.rerank("find the widget", list(HITS))
        assert len(asked) == 2
        assert not rag.rerank_cache_path().exists()


class TestEviction:
    def test_cache_is_capped_fifo(self, asked, monkeypatch):
        monkeypatch.setattr(rag, "RERANK_CACHE_CAP", 3)
        for q in ("q1", "q2", "q3", "q4"):
            rag.rerank(q, list(HITS))
        data = json.loads(rag.rerank_cache_path().read_text(encoding="utf-8"))
        assert len(data) == 3                        # capped
        rag.rerank("q4", list(HITS))
        assert len(asked) == 4                       # newest still cached
        rag.rerank("q1", list(HITS))
        assert len(asked) == 5                       # oldest was evicted


class TestRegistration:
    def test_registered_so_boost_clean_spares_it(self):
        assert rag.rerank_cache_path().name in paths.INTERNAL_CACHE_FILES
