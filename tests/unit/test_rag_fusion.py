"""Unit tests: reciprocal rank fusion in ``rag.retrieve_any``.

``retrieve_any`` used to *choose* an engine — dense whenever it was ready and
returned anything, BM25 otherwise. The golden-set eval showed why that is the
wrong shape: over 91 queries BM25 and local dense tie on hit@1 (71 each), with
recall and MRR gaps inside the noise floor, while on human-phrased queries the
two separate sharply in opposite directions. Preferring one silently hands
keyword queries to an engine that is, at best, tied for them.

RRF fuses instead of choosing: ``score = sum over engines of 1/(k + rank)``,
with k=60 from the original paper. The point is that it fuses on **ranks, not
scores** — a BM25 score and a cosine similarity live on incomparable scales, so
any score-blending needs calibration that rank fusion sidesteps entirely. The
test that matters most here is ``test_a_huge_bm25_score_does_not_dominate``:
it is what distinguishes this from score blending, and it would pass trivially
if someone "simplified" the implementation into a weighted sum.

Every degradation path in the old contract is re-asserted, because fusion adds
a way to get them wrong: dense returning ``None`` (failure), dense returning
``[]`` (thin index, not a verdict), and no index at all (``None``, so the caller
can fall back to ``catalog.search``).
"""
from __future__ import annotations

import pytest

from boost_cli.core import rag


def _hit(name: str, score: float = 1.0, tap: str = "t") -> dict:
    return {"entry": {"name": name, "tap": tap, "kind": "skill",
                      "skill_md": "skills/%s/SKILL.md" % name},
            "score": score, "snippet": "%s snippet" % name}


def _names(hits) -> list:
    return [h["entry"]["name"] for h in hits]


class TestRrfFuse:
    """The pure fusion function."""

    def test_an_item_found_by_both_beats_one_found_by_one(self):
        # The whole premise: agreement between independent engines is signal.
        fused = rag.rrf_fuse([[_hit("both"), _hit("only_a")],
                              [_hit("both"), _hit("only_b")]])
        assert _names(fused)[0] == "both"

    def test_a_huge_bm25_score_does_not_dominate(self):
        # THE DESIGN POINT. Rank fusion ignores magnitude, so a BM25 score of
        # 9999 confers no more than being rank 1. A weighted score blend — the
        # obvious "simplification" — would fail this.
        fused = rag.rrf_fuse([[_hit("keyword", score=9999.0), _hit("shared")],
                              [_hit("shared", score=0.9),
                               _hit("semantic", score=0.8)]])
        assert _names(fused)[0] == "shared", \
            "rank 2 + rank 1 must beat rank 1 alone, whatever the scores"

    def test_rank_one_in_both_lists_scores_two_over_sixty_one(self):
        fused = rag.rrf_fuse([[_hit("x")], [_hit("x")]])
        assert fused[0]["score"] == pytest.approx(2.0 / 61.0)

    def test_a_single_list_is_ordered_by_reciprocal_rank(self):
        fused = rag.rrf_fuse([[_hit("a"), _hit("b"), _hit("c")]])
        assert _names(fused) == ["a", "b", "c"]

    def test_the_damping_constant_is_sixty(self):
        # k=60 is the original paper's default and the reason plain RRF needs
        # no tuning. Asserted against a literal so changing it is deliberate.
        assert rag.RRF_K == 60

    def test_entries_are_deduplicated_by_name_and_tap(self):
        fused = rag.rrf_fuse([[_hit("x", tap="a"), _hit("x", tap="b")]])
        assert len(fused) == 2, "same name in two taps is two different skills"

    def test_the_first_lists_hit_object_wins(self):
        # BM25 is passed first and its snippet is query-term highlighted, so it
        # is the better one to show when both engines found the same entry.
        a = _hit("x")
        a["snippet"] = "highlighted"
        b = _hit("x")
        b["snippet"] = "plain"
        fused = rag.rrf_fuse([[a], [b]])
        assert fused[0]["snippet"] == "highlighted"

    def test_ties_break_deterministically(self):
        one = rag.rrf_fuse([[_hit("b"), _hit("a")]])
        two = rag.rrf_fuse([[_hit("b"), _hit("a")]])
        assert _names(one) == _names(two)

    def test_an_empty_ranking_contributes_nothing(self):
        fused = rag.rrf_fuse([[], [_hit("x")]])
        assert _names(fused) == ["x"]

    def test_no_rankings_yields_nothing(self):
        assert rag.rrf_fuse([]) == []

    def test_the_limit_is_applied_after_fusing(self):
        # Truncating before the fuse would drop a candidate that the other
        # engine ranked highly — the opposite of what over-fetching is for.
        fused = rag.rrf_fuse([[_hit("a"), _hit("b"), _hit("c")]], limit=2)
        assert _names(fused) == ["a", "b"]


class TestRetrieveAnyFuses:
    """The seam every retrieval path goes through."""

    @staticmethod
    def _wire(monkeypatch, bm25, dense_hits, bm25_ready=True, dense_ready=True):
        from boost_cli.core import dense as dense_mod
        monkeypatch.setattr(rag, "ready", lambda: bm25_ready)
        monkeypatch.setattr(rag, "retrieve",
                            lambda *_a, **_k: list(bm25) if bm25 is not None else [])
        monkeypatch.setattr(dense_mod, "ready", lambda: dense_ready)
        monkeypatch.setattr(dense_mod, "retrieve", lambda *_a, **_k: dense_hits)

    def test_both_engines_are_fused(self, monkeypatch):
        self._wire(monkeypatch, [_hit("shared"), _hit("kw")],
                   [_hit("shared"), _hit("sem")])
        hits, label = rag.retrieve_any("q")
        assert _names(hits)[0] == "shared"
        assert "hybrid" in label.lower(), label

    def test_the_label_names_both_engines(self, monkeypatch):
        self._wire(monkeypatch, [_hit("a")], [_hit("b")])
        _hits, label = rag.retrieve_any("q")
        assert "BM25" in label and "dense" in label, label

    def test_dense_alone_is_unchanged(self, monkeypatch):
        self._wire(monkeypatch, None, [_hit("d")], bm25_ready=False)
        hits, label = rag.retrieve_any("q")
        assert _names(hits) == ["d"]
        assert label == "dense vectors"

    def test_bm25_alone_is_unchanged(self, monkeypatch):
        self._wire(monkeypatch, [_hit("b")], None, dense_ready=False)
        hits, label = rag.retrieve_any("q")
        assert _names(hits) == ["b"]
        assert label == "BM25 full-content"

    def test_a_dense_failure_falls_back_to_bm25(self, monkeypatch):
        # dense.retrieve returns None when the store is unusable.
        self._wire(monkeypatch, [_hit("b")], None)
        hits, label = rag.retrieve_any("q")
        assert _names(hits) == ["b"]
        assert label == "BM25 full-content"

    def test_a_thin_dense_index_still_falls_back(self, monkeypatch):
        # `[]` means every neighbour was filtered out — a thin index, not a
        # verdict on the query. The old contract; fusion must not lose it.
        self._wire(monkeypatch, [_hit("b")], [])
        hits, label = rag.retrieve_any("q")
        assert _names(hits) == ["b"]
        assert label == "BM25 full-content"

    def test_no_index_at_all_returns_none(self, monkeypatch):
        # None, not [], so the caller knows to try catalog.search instead.
        self._wire(monkeypatch, None, None, bm25_ready=False, dense_ready=False)
        hits, label = rag.retrieve_any("q")
        assert hits is None and label == ""

    def test_an_empty_bm25_result_is_still_an_answer(self, monkeypatch):
        # A built index that matched nothing is a real answer; only a missing
        # index is None.
        self._wire(monkeypatch, [], None, dense_ready=False)
        hits, label = rag.retrieve_any("q")
        assert hits == [] and label == "BM25 full-content"

    def test_it_returns_at_most_k(self, monkeypatch):
        many = [_hit("n%d" % i) for i in range(50)]
        self._wire(monkeypatch, many, list(many))
        hits, _label = rag.retrieve_any("q", k=5)
        assert len(hits) == 5

    def test_it_over_fetches_before_fusing(self, monkeypatch):
        # Fusing only the top-k of each engine throws away the candidates the
        # other engine would have promoted, which is most of the value.
        asked = {}
        from boost_cli.core import dense as dense_mod
        monkeypatch.setattr(rag, "ready", lambda: True)
        monkeypatch.setattr(dense_mod, "ready", lambda: True)

        def spy_bm25(_q, k=60, **_kw):
            asked["bm25"] = k
            return [_hit("a")]

        def spy_dense(_q, k=60, **_kw):
            asked["dense"] = k
            return [_hit("b")]

        monkeypatch.setattr(rag, "retrieve", spy_bm25)
        monkeypatch.setattr(dense_mod, "retrieve", spy_dense)
        rag.retrieve_any("q", k=5)
        assert asked["bm25"] >= rag.RRF_K, asked
        assert asked["dense"] >= rag.RRF_K, asked

    def test_kind_and_entries_reach_both_engines(self, monkeypatch):
        seen = []
        from boost_cli.core import dense as dense_mod
        monkeypatch.setattr(rag, "ready", lambda: True)
        monkeypatch.setattr(dense_mod, "ready", lambda: True)
        monkeypatch.setattr(rag, "retrieve",
                            lambda _q, k=60, kind=None, entries=None:
                            (seen.append(("bm25", kind, entries)), [_hit("a")])[1])
        monkeypatch.setattr(dense_mod, "retrieve",
                            lambda _q, k=60, kind=None, entries=None:
                            (seen.append(("dense", kind, entries)), [_hit("b")])[1])
        ents = [{"name": "a", "tap": "t", "skill_md": "skills/a/SKILL.md"}]
        rag.retrieve_any("q", kind="rule", entries=ents)
        assert ("bm25", "rule", ents) in seen
        assert ("dense", "rule", ents) in seen


class TestRerankPreservesTheEngineLabel:
    """The engine that actually retrieved must survive the rerank stage.

    ``rerank`` hard-coded ``"BM25 full-content"`` on both of its degrade paths,
    and ``search`` discards ``retrieve_any``'s label whenever ``smart`` is on —
    which is the default, and what the MCP ``boost_search`` tool uses. So a user
    whose dense store and fusion were working perfectly, but who had no
    ``ANTHROPIC_API_KEY``, was told they were on BM25.

    That is the same class of silent misreport the dense-status work existed to
    kill: the label is the only signal a user has about which engine answered,
    and a wrong one sends the investigation somewhere else entirely. Worse here
    than a missing label, because it names a specific wrong engine confidently.
    """

    @staticmethod
    def _hits():
        return [_hit("a", 2.0), _hit("b", 1.0)]

    def test_no_ai_reports_the_engine_that_retrieved(self, monkeypatch):
        # THE regression. Fusion ran, the LLM was absent, and the old code
        # answered "BM25 full-content" — naming an engine that did not rank
        # these hits alone.
        monkeypatch.setattr(rag.ai, "available", lambda: False)
        _out, label = rag.rerank("q", self._hits(), limit=5,
                                 engine="hybrid RRF (BM25 + dense)")
        assert label == "hybrid RRF (BM25 + dense)"

    def test_no_ai_reports_dense_when_dense_retrieved(self, monkeypatch):
        monkeypatch.setattr(rag.ai, "available", lambda: True)
        monkeypatch.setattr(rag.ai, "ask", lambda *_a, **_k: "not json at all")
        _out, label = rag.rerank("q", self._hits(), limit=5,
                                 engine="dense vectors")
        assert label == "dense vectors"

    def test_an_unparseable_reply_keeps_the_engine_too(self, monkeypatch):
        # The second degrade path: the model answered, but not with a JSON
        # array. Ordering falls back, so the label must fall back with it.
        monkeypatch.setattr(rag.ai, "available", lambda: True)
        monkeypatch.setattr(rag.ai, "ask", lambda *_a, **_k: "sorry, I can't")
        _out, label = rag.rerank("q", self._hits(), limit=5,
                                 engine="hybrid RRF (BM25 + dense)")
        assert label == "hybrid RRF (BM25 + dense)"

    def test_a_successful_rerank_still_says_claude(self, monkeypatch):
        # The LLM really did decide the order here, so crediting the retrieval
        # engine instead would be the same bug pointing the other way.
        monkeypatch.setattr(rag.ai, "available", lambda: True)
        monkeypatch.setattr(rag.ai, "ask", lambda *_a, **_k: '["b", "a"]')
        out, label = rag.rerank("q", self._hits(), limit=5,
                                engine="hybrid RRF (BM25 + dense)")
        assert _names(out) == ["b", "a"]
        assert label == "Claude relevance"

    def test_the_default_keeps_existing_callers_honest(self, monkeypatch):
        # Back-compat: an omitted engine still reads "BM25 full-content", so
        # this is additive for anything that calls rerank directly.
        monkeypatch.setattr(rag.ai, "available", lambda: False)
        _out, label = rag.rerank("q", self._hits(), limit=5)
        assert label == "BM25 full-content"


class TestSearchReportsTheTruthEndToEnd:
    """`search` is where the label is chosen, so the bug is only really fixed
    if it survives the whole path an MCP call takes."""

    @staticmethod
    def _wire(monkeypatch, engine_hits, ai_ok):
        from boost_cli.core import dense as dense_mod
        monkeypatch.setattr(rag, "ready", lambda: True)
        monkeypatch.setattr(rag, "retrieve", lambda *_a, **_k: list(engine_hits))
        monkeypatch.setattr(dense_mod, "ready", lambda: True)
        monkeypatch.setattr(dense_mod, "retrieve", lambda *_a, **_k: list(engine_hits))
        monkeypatch.setattr(rag.ai, "available", lambda: ai_ok)

    def test_fused_retrieval_without_a_key_is_not_called_bm25(self, monkeypatch):
        # Exactly the MCP boost_search path: smart defaults on, no key.
        self._wire(monkeypatch, [_hit("a"), _hit("b")], ai_ok=False)
        result = rag.search("q", limit=5)
        assert result is not None
        _hits, label = result
        assert label != "BM25 full-content"
        assert "dense" in label, label

    def test_smart_off_is_unaffected(self, monkeypatch):
        self._wire(monkeypatch, [_hit("a")], ai_ok=True)
        result = rag.search("q", limit=5, smart=False)
        assert result is not None
        _hits, label = result
        assert "dense" in label, label
