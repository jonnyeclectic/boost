# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`retrieve_any`'s opt-in near-duplicate collapsing.

`collapse_near_duplicate_hits` (see `test_near_duplicate_collapse.py`) is pure
and already covered on its own; this file is only the wiring at the
`retrieve_any` seam — that the flag defaults off, that turning it on actually
reaches `dense.entry_vectors` and applies the collapse, and that it degrades
to a no-op wherever the embeddings it needs are not available. See
`rag.NEAR_DUPLICATE_THRESHOLD` for why this stays opt-in rather than wired
into the default search path.
"""
from __future__ import annotations

import array

from boost_cli.core import rag


def _hit(name: str, score: float = 1.0, tap: str = "t") -> dict:
    return {"entry": {"name": name, "tap": tap, "kind": "skill",
                      "skill_md": "skills/%s/SKILL.md" % name},
            "score": score, "snippet": "%s snippet" % name}


def _names(hits) -> list:
    return [h["entry"]["name"] for h in hits]


def _vecbytes(values) -> bytes:
    return array.array("f", values).tobytes()


class TestRetrieveAnyNearDuplicateFlag:
    @staticmethod
    def _wire(monkeypatch, bm25, dense_hits, vectors=None, dense_ready=True):
        from boost_cli.core import dense as dense_mod
        monkeypatch.setattr(rag, "ready", lambda: True)
        monkeypatch.setattr(rag, "retrieve", lambda *_a, **_k: list(bm25))
        monkeypatch.setattr(dense_mod, "ready", lambda: dense_ready)
        monkeypatch.setattr(dense_mod, "retrieve", lambda *_a, **_k: dense_hits)
        monkeypatch.setattr(dense_mod, "entry_vectors",
                            lambda _keys: dict(vectors or {}))

    def test_off_by_default(self, monkeypatch):
        # Two near-identical vectors, but the flag is not passed: nothing
        # collapses. This is the backward-compatibility guarantee — every
        # existing caller of `retrieve_any` must see no change at all.
        a, b = _hit("a", tap="x"), _hit("a2", tap="y")
        vecs = {("x", "skills/a/SKILL.md"): _vecbytes([1.0, 0.0]),
                ("y", "skills/a2/SKILL.md"): _vecbytes([1.0, 0.0001])}
        self._wire(monkeypatch, [a], [b], vectors=vecs)
        hits, _label = rag.retrieve_any("q")
        assert _names(hits) == ["a", "a2"]

    def test_flag_off_never_calls_entry_vectors(self, monkeypatch):
        from boost_cli.core import dense as dense_mod
        called = []
        self._wire(monkeypatch, [_hit("a")], [_hit("b")])
        monkeypatch.setattr(dense_mod, "entry_vectors",
                            lambda keys: called.append(keys) or {})
        rag.retrieve_any("q", collapse_near_duplicates=False)
        assert called == []

    def test_flag_on_collapses_near_identical_entries(self, monkeypatch):
        a, b = _hit("a", tap="x", score=3.0), _hit("a2", tap="y", score=2.0)
        vecs = {("x", "skills/a/SKILL.md"): _vecbytes([1.0, 0.0]),
                ("y", "skills/a2/SKILL.md"): _vecbytes([1.0, 0.0001])}
        self._wire(monkeypatch, [a], [b], vectors=vecs)
        hits, _label = rag.retrieve_any("q", collapse_near_duplicates=True)
        assert _names(hits) == ["a"]

    def test_flag_on_but_no_dense_store_is_a_no_op(self, monkeypatch):
        # No vectors exist to collapse on without a dense store, whatever the
        # BM25-only hits look like.
        a = _hit("a", tap="x")
        self._wire(monkeypatch, [a], None, dense_ready=False)
        hits, _label = rag.retrieve_any("q", collapse_near_duplicates=True)
        assert _names(hits) == ["a"]

    def test_flag_on_with_no_matching_vectors_is_a_no_op(self, monkeypatch):
        a, b = _hit("a", tap="x"), _hit("b", tap="y")
        self._wire(monkeypatch, [a], [b], vectors={})
        hits, _label = rag.retrieve_any("q", collapse_near_duplicates=True)
        assert _names(hits) == ["a", "b"]

    def test_flag_on_never_collapses_dissimilar_entries(self, monkeypatch):
        a, b = _hit("a", tap="x"), _hit("b", tap="y")
        vecs = {("x", "skills/a/SKILL.md"): _vecbytes([1.0, 0.0]),
                ("y", "skills/b/SKILL.md"): _vecbytes([0.0, 1.0])}
        self._wire(monkeypatch, [a], [b], vectors=vecs)
        hits, _label = rag.retrieve_any("q", collapse_near_duplicates=True)
        assert _names(hits) == ["a", "b"]
