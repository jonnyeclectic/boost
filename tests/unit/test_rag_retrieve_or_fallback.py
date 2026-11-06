# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""rag.retrieve_or_fallback: `boost search`'s engine choice, never None.

A library caller (boost_langchain's retriever) has no "no index" branch of
its own, and answering [] there told a chain nothing matched about items
`boost search` found on the same machine — ensure() swallows every build
failure, so "no index" is not "nothing tapped".
"""
from __future__ import annotations

from boost_cli.core import catalog, rag

SKILL = {"name": "zebra-skill", "kind": "skill", "tap": "t"}
RULE = {"name": "zebra-rule", "kind": "rule", "tap": "t"}
BARE = {"name": "zebra-bare", "tap": "t"}            # no kind: a skill
WORKFLOW = {"name": "zebra-flow", "kind": "workflow", "tap": "t"}
SCORED = [(SKILL, 90), (RULE, 70), (BARE, 50), (WORKFLOW, 30)]


def _no_index(monkeypatch):
    monkeypatch.setattr(rag, "ensure", lambda: False)
    monkeypatch.setattr(rag, "retrieve_any", lambda *a, **kw: (
        _ for _ in ()).throw(AssertionError("retrieve_any must not run")))
    monkeypatch.setattr(catalog, "search", lambda q: list(SCORED))


def test_failed_build_falls_back_to_catalog_search(sandbox, monkeypatch):
    _no_index(monkeypatch)
    hits, engine = rag.retrieve_or_fallback("zebra", k=10)
    assert engine == "heuristic relevance" == rag.HEURISTIC_ENGINE
    assert hits == [{"entry": SKILL, "score": 90.0},
                    {"entry": RULE, "score": 70.0},
                    {"entry": BARE, "score": 50.0},
                    {"entry": WORKFLOW, "score": 30.0}]
    assert all(type(h["score"]) is float for h in hits)


def test_fallback_cuts_to_k(sandbox, monkeypatch):
    _no_index(monkeypatch)
    hits, _ = rag.retrieve_or_fallback("zebra", k=2)
    assert [h["entry"]["name"] for h in hits] == ["zebra-skill", "zebra-rule"]


def test_fallback_narrows_to_kind_before_cutting(sandbox, monkeypatch):
    _no_index(monkeypatch)
    skills, _ = rag.retrieve_or_fallback("zebra", k=10, kind="skill")
    # An entry with no kind is a skill, exactly as everywhere else.
    assert [h["entry"]["name"] for h in skills] == ["zebra-skill", "zebra-bare"]
    one, _ = rag.retrieve_or_fallback("zebra", k=1, kind="workflow")
    assert [h["entry"]["name"] for h in one] == ["zebra-flow"]


def test_an_index_that_answers_none_also_falls_back(sandbox, monkeypatch):
    monkeypatch.setattr(rag, "ensure", lambda: True)
    monkeypatch.setattr(rag, "retrieve_any", lambda *a, **kw: (None, ""))
    monkeypatch.setattr(catalog, "search", lambda q: list(SCORED))
    hits, engine = rag.retrieve_or_fallback("zebra", k=1)
    assert (hits, engine) == ([{"entry": SKILL, "score": 90.0}],
                              "heuristic relevance")


def test_a_working_index_answers_untouched(sandbox, monkeypatch):
    seen = {}
    ranked = [{"entry": RULE, "score": 3.5}]

    def fake(query, k, kind):
        seen.update(query=query, k=k, kind=kind)
        return ranked, "BM25 full-content"

    monkeypatch.setattr(rag, "ensure", lambda: True)
    monkeypatch.setattr(rag, "retrieve_any", fake)
    monkeypatch.setattr(catalog, "search", lambda q: list(SCORED))
    assert rag.retrieve_or_fallback("zebra", k=4, kind="rule") == (
        ranked, "BM25 full-content")
    assert seen == {"query": "zebra", "k": 4, "kind": "rule"}
    # An empty ranking is the index's answer, not a cue to fall back.
    monkeypatch.setattr(rag, "retrieve_any", lambda *a, **kw: ([], "BM25 full-content"))
    assert rag.retrieve_or_fallback("zebra", k=4) == ([], "BM25 full-content")


def test_a_real_failed_build_still_finds_the_tapped_item(tapped, monkeypatch):
    """End to end over a real tap: the build raises, the item is still found."""
    def boom():
        raise OSError("read-only cache dir")

    monkeypatch.setattr(rag, "build", boom)
    assert not rag.ready()
    hits, engine = rag.retrieve_or_fallback("brainstorming", k=3)
    assert engine == "heuristic relevance"
    assert hits and hits[0]["entry"]["name"] == "brainstorming"


def test_nothing_tapped_is_an_empty_answer(sandbox):
    assert rag.retrieve_or_fallback("anything", k=5) == ([], "heuristic relevance")
