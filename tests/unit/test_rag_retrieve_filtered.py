# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""``rag.retrieve_filtered``: widen the pool until enough hits pass a filter.

``boost search --category`` filtered one page of ``max(60, limit * 4)`` hits
and returned what passed, so a category whose items ranked past the page came
back short with nothing saying why.
"""
from __future__ import annotations

from boost_cli.core import rag


def _wire(monkeypatch, total, ui_from):
    """A fake engine holding ``total`` hits; those from ``ui_from`` on are ui."""
    calls: list[int] = []

    def fake(query, k=60, kind=None, collapse_near_duplicates=False):
        calls.append(k)
        hits = [{"entry": {"name": "i%d" % i,
                           "category": "ui" if i >= ui_from else "x"},
                 "score": float(total - i)} for i in range(min(k, total))]
        return hits, "BM25 full-content"
    monkeypatch.setattr(rag, "retrieve_any", fake)
    return calls


def _ui(entry):
    return entry["category"] == "ui"


def test_widens_fourfold_until_enough_pass(monkeypatch):
    calls = _wire(monkeypatch, total=1000, ui_from=300)
    hits, engine, k = rag.retrieve_filtered("q", k=60, want=15, keep=_ui)
    assert calls == [60, 240, 960]
    assert (len(hits), engine, k) == (960, "BM25 full-content", 960)


def test_one_round_when_the_first_page_suffices(monkeypatch):
    calls = _wire(monkeypatch, total=1000, ui_from=0)
    _hits, _engine, k = rag.retrieve_filtered("q", k=60, want=60, keep=_ui)
    assert (calls, k) == ([60], 60)


def test_exactly_want_passing_stops(monkeypatch):
    calls = _wire(monkeypatch, total=1000, ui_from=45)
    rag.retrieve_filtered("q", k=60, want=15, keep=_ui)
    assert calls == [60]


def test_stops_when_the_engine_runs_out(monkeypatch):
    calls = _wire(monkeypatch, total=100, ui_from=99)
    hits, _engine, k = rag.retrieve_filtered("q", k=60, want=15, keep=_ui)
    assert calls == [60, 240]
    assert (len(hits), k) == (100, 240)


def test_stops_at_the_ceiling(monkeypatch):
    calls = _wire(monkeypatch, total=10_000, ui_from=10_000)
    hits, _engine, k = rag.retrieve_filtered("q", k=60, want=15, keep=_ui,
                                             ceiling=500)
    assert calls == [60, 240, 500]
    assert (len(hits), k) == (500, 500)


def test_no_index_is_passed_through(monkeypatch):
    monkeypatch.setattr(rag, "retrieve_any", lambda *_a, **_k: (None, ""))
    assert rag.retrieve_filtered("q", k=60, want=15, keep=_ui) == (None, "", 60)


def test_kind_and_collapse_reach_the_engine(monkeypatch):
    seen = {}

    def fake(query, k=60, kind=None, collapse_near_duplicates=False):
        seen.update(query=query, kind=kind, collapse=collapse_near_duplicates)
        return [], "BM25 full-content"
    monkeypatch.setattr(rag, "retrieve_any", fake)
    rag.retrieve_filtered("q", k=60, want=1, keep=_ui, kind="rule",
                          collapse_near_duplicates=True)
    assert seen == {"query": "q", "kind": "rule", "collapse": True}


def test_the_default_ceiling():
    assert rag.FILTER_POOL_CEILING == 16384
