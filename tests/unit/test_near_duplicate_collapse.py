# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Collapsing near-identical entries that survive byte-identical dedup.

`rag.dedupe_by_content` collapses copies that share a body digest, and proved
it safe before shipping: of 14,153 distinct bodies over 77 taps, zero clusters
spanned more than one name. It cannot reach a translation or a paraphrase —
those are genuinely different bytes — which is the residual this module
targets: observed on a real 466-tap install, the query ``exa search`` returned
ten rows that were all one skill in Japanese, Chinese and five English
variants, none sharing a content hash.

`collapse_near_duplicate_hits` is the same "keep the earliest rank slot,
promote a better source" contract as `dedupe_by_content`, run over embeddings
instead of a hash. It has no equivalent safety count yet — no measurement over
a real corpus establishes that 0.97 cosine similarity never merges two
genuinely different entries — so it stays reachable only opt-in
(`retrieve_any(..., collapse_near_duplicates=True)`, `boost search
--collapse-near-duplicates`) rather than wired into the default search path.
"""
from __future__ import annotations

import array
import math

from boost_cli.core import rag


def _vecbytes(values):
    return array.array("f", values).tobytes()


# Two directions in 4-d, far enough apart that no floating-point noise could
# push their cosine near the 0.97 threshold.
_A = [1.0, 0.0, 0.0, 0.0]
_B = [0.0, 1.0, 0.0, 0.0]


def _near(base, nudge=0.001):
    """A vector barely perturbed from ``base`` — cosine similarity > 0.999."""
    return [v + nudge for v in base]


def _hit(name, tap, score, curated=False, skill_md=None, content=None):
    return {"entry": {"name": name, "tap": tap, "curated": curated,
                      "skill_md": skill_md or ("%s/SKILL.md" % name),
                      "kind": "skill", "description": ""},
            "score": score, "snippet": "", "content": content}


def _key(hit):
    return rag.entry_key(hit["entry"])


class TestCollapsesNearIdenticalEmbeddings:
    def test_two_near_identical_vectors_become_one(self):
        hits = [_hit("exa-search-en", "a/x", 3.0),
                _hit("exa-search-ja", "b/y", 2.0)]
        vectors = {_key(hits[0]): _vecbytes(_A),
                  _key(hits[1]): _vecbytes(_near(_A))}
        out = rag.collapse_near_duplicate_hits(hits, vectors, limit=10)
        assert len(out) == 1

    def test_the_best_ranked_copy_is_the_one_kept(self):
        hits = [_hit("exa-search-en", "a/x", 3.0),
                _hit("exa-search-ja", "b/y", 2.0)]
        vectors = {_key(hits[0]): _vecbytes(_A),
                  _key(hits[1]): _vecbytes(_near(_A))}
        out = rag.collapse_near_duplicate_hits(hits, vectors, limit=10)
        assert out[0]["entry"]["tap"] == "a/x"

    def test_order_of_surviving_hits_is_preserved(self):
        hits = [_hit("a", "t/1", 5.0), _hit("b", "t/2", 4.0),
                _hit("a2", "t/3", 3.0)]     # near-dup of the first
        vectors = {_key(hits[0]): _vecbytes(_A), _key(hits[1]): _vecbytes(_B),
                  _key(hits[2]): _vecbytes(_near(_A))}
        out = rag.collapse_near_duplicate_hits(hits, vectors, limit=10)
        assert [h["entry"]["name"] for h in out] == ["a", "b"]

    def test_exactly_the_threshold_merges(self):
        # `_cosine(a, a) == 1.0`, and 1.0 >= any threshold <= 1.0 — the merge
        # test is `>=`, not `>`.
        hits = [_hit("a", "t/1", 2.0), _hit("a2", "t/2", 1.0)]
        vectors = {k: _vecbytes(_A) for k in (_key(hits[0]), _key(hits[1]))}
        out = rag.collapse_near_duplicate_hits(hits, vectors, limit=10,
                                                threshold=1.0)
        assert len(out) == 1


class TestNeverMergesDistinctEmbeddings:
    def test_orthogonal_vectors_stay_two_results(self):
        hits = [_hit("a", "t/1", 3.0), _hit("b", "t/2", 2.0)]
        vectors = {_key(hits[0]): _vecbytes(_A), _key(hits[1]): _vecbytes(_B)}
        out = rag.collapse_near_duplicate_hits(hits, vectors, limit=10)
        assert len(out) == 2

    def test_a_hit_with_no_vector_is_never_merged(self):
        # One hit has an embedding, the other does not: an unknown must not
        # collapse into a known, or a real result could silently vanish.
        hits = [_hit("a", "t/1", 3.0), _hit("b", "t/2", 2.0)]
        vectors = {_key(hits[0]): _vecbytes(_A)}      # hits[1] absent
        out = rag.collapse_near_duplicate_hits(hits, vectors, limit=10)
        assert len(out) == 2

    def test_two_hits_with_no_vector_both_stay(self):
        hits = [_hit("a", "t/1", 3.0), _hit("b", "t/2", 2.0)]
        out = rag.collapse_near_duplicate_hits(hits, {}, limit=10)
        assert len(out) == 2

    def test_mismatched_dimensions_never_merge(self):
        # Different embedding widths mean different models — an ambiguous
        # comparison, never a match.
        hits = [_hit("a", "t/1", 3.0), _hit("b", "t/2", 2.0)]
        vectors = {_key(hits[0]): _vecbytes(_A),
                  _key(hits[1]): _vecbytes([*_A, 0.0])}
        out = rag.collapse_near_duplicate_hits(hits, vectors, limit=10)
        assert len(out) == 2

    def test_zero_vectors_never_merge(self):
        hits = [_hit("a", "t/1", 3.0), _hit("b", "t/2", 2.0)]
        vectors = {_key(hits[0]): _vecbytes([0.0, 0.0, 0.0, 0.0]),
                  _key(hits[1]): _vecbytes([0.0, 0.0, 0.0, 0.0])}
        out = rag.collapse_near_duplicate_hits(hits, vectors, limit=10)
        assert len(out) == 2


class TestQualityPrior:
    def test_a_curated_copy_wins_over_a_better_ranked_uncurated_one(self):
        hits = [_hit("a", "rando/x", 3.0, curated=False),
                _hit("a2", "trusted/y", 2.0, curated=True)]
        vectors = {_key(hits[0]): _vecbytes(_A),
                  _key(hits[1]): _vecbytes(_near(_A))}
        kept = rag.collapse_near_duplicate_hits(hits, vectors, limit=10)[0]
        assert kept["entry"]["tap"] == "trusted/y"

    def test_the_kept_hit_keeps_the_best_score_in_its_cluster(self):
        hits = [_hit("a", "rando/x", 3.0, curated=False),
                _hit("a2", "trusted/y", 2.0, curated=True)]
        vectors = {_key(hits[0]): _vecbytes(_A),
                  _key(hits[1]): _vecbytes(_near(_A))}
        kept = rag.collapse_near_duplicate_hits(hits, vectors, limit=10)[0]
        assert kept["score"] == 3.0


class TestLimit:
    def test_limit_is_applied_after_collapsing_not_before(self):
        dups = [_hit("dup%d" % i, "t%d/r" % i, 20.0 - i) for i in range(5)]
        vectors = {_key(h): _vecbytes(_near(_A, nudge=i * 1e-4))
                  for i, h in enumerate(dups)}
        distinct = [_hit("x", "t/a", 5.0), _hit("y", "t/b", 4.0),
                    _hit("z", "t/c", 3.0)]
        vectors[_key(distinct[0])] = _vecbytes(_B)
        vectors[_key(distinct[1])] = _vecbytes([0.0, 0.0, 1.0, 0.0])
        vectors[_key(distinct[2])] = _vecbytes([0.0, 0.0, 0.0, 1.0])
        out = rag.collapse_near_duplicate_hits(dups + distinct, vectors,
                                               limit=4)
        assert [h["entry"]["name"] for h in out] == ["dup0", "x", "y", "z"]

    def test_empty_input_is_empty_output(self):
        assert rag.collapse_near_duplicate_hits([], {}, limit=10) == []


class TestCosineHelper:
    """`_cosine` and `_decode_vector` directly — the arithmetic the merge
    decision above rests on."""

    def test_identical_vectors_are_similarity_one(self):
        v = rag._decode_vector(_vecbytes(_A))
        assert math.isclose(rag._cosine(v, v), 1.0)

    def test_orthogonal_vectors_are_similarity_zero(self):
        a, b = rag._decode_vector(_vecbytes(_A)), rag._decode_vector(_vecbytes(_B))
        assert math.isclose(rag._cosine(a, b), 0.0, abs_tol=1e-6)

    def test_opposite_vectors_are_similarity_negative_one(self):
        a = rag._decode_vector(_vecbytes(_A))
        b = rag._decode_vector(_vecbytes([-x for x in _A]))
        assert math.isclose(rag._cosine(a, b), -1.0)

    def test_dimension_mismatch_is_never_a_match(self):
        a = rag._decode_vector(_vecbytes(_A))
        b = rag._decode_vector(_vecbytes([*_A, 0.0]))
        assert rag._cosine(a, b) == 0.0

    def test_a_zero_vector_is_never_a_match(self):
        a = rag._decode_vector(_vecbytes(_A))
        z = rag._decode_vector(_vecbytes([0.0, 0.0, 0.0, 0.0]))
        assert rag._cosine(a, z) == 0.0

    def test_empty_vectors_are_never_a_match(self):
        assert rag._cosine(array.array("f", []), array.array("f", [])) == 0.0
