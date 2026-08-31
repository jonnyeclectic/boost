# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Near-identical copies -- translations, light rewrites -- still eat a result page.

`rag.dedupe_by_content` collapses byte-identical copies correctly and stops
there by design: it clusters on the exact body digest, so a translation or a
paraphrase of the same skill survives untouched, because it genuinely is a
different body. Measured on a real 466-tap install (see
``near-identical-copies-still-eat-the-slots``): a query for ``exa search``
returned ten rows that were all ``exa-search``, in Japanese, Chinese and five
English phrasings -- every one passed byte-identical dedup correctly and still
filled the whole page.

``dense.near_duplicate_clusters`` reaches this with the vectors the dense
store already has: it clusters candidates by cosine similarity of their
*first* chunk (name + description, see `rag.chunk`), the text a translation
still carries close together in embedding space. `rag._collapse_near_duplicates`
applies that clustering after byte-identical dedup, over a bounded window
(`NEAR_DUP_POOL_FACTOR`), and is a no-op wherever the dense store is not
ready -- a BM25-only install sees no behavior change at all.
"""
from __future__ import annotations

import math
import sqlite3

import pytest

from boost_cli.core import dense, rag


def _hit(name, tap, score, content=None, curated=False, skill_md=None):
    return {"entry": {"name": name, "tap": tap, "curated": curated,
                      "skill_md": skill_md or ("%s/SKILL.md" % name),
                      "kind": "skill", "description": ""},
            "score": score, "snippet": "", "content": content}


# --------------------------------------------------------- degrades cleanly

class TestNoDenseStoreIsANoOp:
    """The required, dependency-free search path must be untouched."""

    def test_collapse_returns_hits_unchanged_when_dense_not_ready(
            self, monkeypatch):
        monkeypatch.setattr(dense, "ready", lambda: False)
        hits = [_hit("a", "t/1", 3.0), _hit("b", "t/2", 2.0)]
        assert rag._collapse_near_duplicates(hits, limit=10) == hits

    def test_dedupe_hits_matches_dedupe_by_content_when_dense_not_ready(
            self, monkeypatch):
        monkeypatch.setattr(dense, "ready", lambda: False)
        hits = [_hit("rule", "a/x", 3.0, "same"),
                _hit("rule", "b/y", 2.0, "same"),
                _hit("other", "c/z", 1.0, "different")]
        assert (rag.dedupe_hits(hits, limit=10)
                == rag.dedupe_by_content(hits, limit=10))


class TestIncompleteEntriesDoNotCrash:
    """A hit assembled without a full catalog entry must degrade, not raise.

    `entry_key` is deliberately strict (a missing `skill_md` is a KeyError,
    by design -- see its docstring). `_collapse_near_duplicates` reads the
    same two fields but must not inherit that strictness: it runs after
    `dedupe_by_content`, which needs neither field, so a caller whose hits
    lack them (several existing tests stub `dense.retrieve` with a bare
    ``{"name": ..., "tap": ...}``) must still get an answer instead of an
    exception from an enhancement layer.
    """

    def test_a_hit_missing_skill_md_does_not_raise(self, monkeypatch):
        monkeypatch.setattr(dense, "ready", lambda: True)
        monkeypatch.setattr(dense, "near_duplicate_clusters", lambda keys, **k: {})
        hits = [{"entry": {"name": "d", "tap": "x/y"}, "score": 9.0,
                "snippet": "D"}]
        out = rag._collapse_near_duplicates(hits, limit=10)
        assert out == hits

    def test_dedupe_hits_end_to_end_with_a_bare_entry(self, monkeypatch):
        monkeypatch.setattr(dense, "ready", lambda: True)
        monkeypatch.setattr(dense, "near_duplicate_clusters", lambda keys, **k: {})
        hits = [{"entry": {"name": "d", "tap": "x/y"}, "score": 9.0,
                "snippet": "D", "content": None}]
        assert rag.dedupe_hits(hits, limit=10) == hits


class TestNearDuplicateClustersDegradesCleanly:
    def test_fewer_than_two_keys_returns_empty(self, monkeypatch):
        monkeypatch.setattr(dense, "ready", lambda: True)
        assert dense.near_duplicate_clusters([("t", "a.md")]) == {}
        assert dense.near_duplicate_clusters([]) == {}

    def test_not_ready_returns_empty(self, monkeypatch):
        monkeypatch.setattr(dense, "ready", lambda: False)
        out = dense.near_duplicate_clusters([("t", "a.md"), ("t", "b.md")])
        assert out == {}

    def test_no_store_on_disk_returns_empty(self, sandbox, monkeypatch):
        monkeypatch.setattr(dense, "ready", lambda: True)
        out = dense.near_duplicate_clusters([("t", "a.md"), ("t", "b.md")])
        assert out == {}


# ------------------------------------------------------- real vector store

def _vec_loadable() -> bool:
    con = sqlite3.connect(":memory:")
    try:
        import sqlite_vec
        con.enable_load_extension(True)
        sqlite_vec.load(con)
        con.enable_load_extension(False)
        con.execute("create virtual table t using vec0(embedding bit[8])")
        return True
    except Exception:
        return False
    finally:
        con.close()


_NEEDS_SQLITE_VEC = pytest.mark.skipif(
    not _vec_loadable(), reason="sqlite-vec extension not loadable here")


def _vec(angle: float, offset: int = 0, dim: int = 8):
    """A unit vector with cos/sin at ``[offset, offset+1]``, zero elsewhere.

    Two vectors built at the same ``offset`` have cosine similarity exactly
    ``cos(angle_a - angle_b)`` -- an analytic, exact way to place a pair on
    either side of :data:`dense.NEAR_DUP_THRESHOLD` (0.97, i.e. ~14.07 degrees
    apart) without depending on a real embedding model. Vectors built at
    *different* offsets are exactly orthogonal (similarity 0), which keeps
    unrelated clusters from interfering with each other in the same test.
    """
    v = [0.0] * dim
    v[offset] = math.cos(angle)
    v[offset + 1] = math.sin(angle)
    return v


# Group "a": origin and a close mirror (~4.6 degrees apart, cosine ~0.9968)
# clear the threshold; "distant" (~51.6 degrees, cosine ~0.622) does not.
_VECS = {
    "origin-a": _vec(0.00, offset=0),
    "mirror-a": _vec(0.08, offset=0),
    "distant-a": _vec(0.90, offset=0),
    # Group "b": three mutually close vectors -- exercises a cluster with
    # more than two members (transitive union, not just one pair).
    "origin-b": _vec(0.00, offset=2),
    "mirror-b1": _vec(0.05, offset=2),
    "mirror-b2": _vec(0.10, offset=2),
}


def _entries():
    return [{"name": n, "tap": "acme/skills", "kind": "skill",
             "skill_md": "skills/%s/SKILL.md" % n} for n in _VECS]


def _toy_embed(texts, input_type=None, timeout=60):
    return [_VECS[t.split("\n", 1)[0].strip()] for t in texts]


@pytest.fixture()
def vector_store(sandbox, monkeypatch):
    from boost_cli.core import embed
    monkeypatch.setattr(embed, "embed", _toy_embed)
    monkeypatch.setattr(embed, "provider", lambda: "openai")
    monkeypatch.setattr(embed, "model", lambda: "toy-8")
    monkeypatch.setattr(embed, "dimension", lambda: 8)
    monkeypatch.setattr(embed, "available", lambda: True)
    monkeypatch.setattr(rag, "_tap_paths", lambda: {"acme/skills": "/x"})
    monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c1"})
    # Each entry's body is just its own name -- the embedding is fully
    # controlled by `_toy_embed` above, so the real text does not matter.
    monkeypatch.setattr(dense, "read_body", lambda e, tp=None: e["name"])
    dense.build(entries=_entries(), force=True)
    return monkeypatch


def _key(name):
    return "acme/skills", "skills/%s/SKILL.md" % name


@_NEEDS_SQLITE_VEC
class TestClusteringByFirstChunkSimilarity:
    def test_a_close_pair_clusters_together(self, vector_store):
        clusters = dense.near_duplicate_clusters(
            [_key("origin-a"), _key("mirror-a"), _key("distant-a")])
        assert clusters[_key("origin-a")] == clusters[_key("mirror-a")]

    def test_a_distant_pair_does_not_cluster(self, vector_store):
        clusters = dense.near_duplicate_clusters(
            [_key("origin-a"), _key("mirror-a"), _key("distant-a")])
        assert clusters[_key("distant-a")] != clusters[_key("origin-a")]

    def test_a_three_member_cluster_unions_transitively(self, vector_store):
        keys = [_key("origin-b"), _key("mirror-b1"), _key("mirror-b2")]
        clusters = dense.near_duplicate_clusters(keys)
        assert len({clusters[k] for k in keys}) == 1

    def test_unrelated_groups_stay_apart(self, vector_store):
        clusters = dense.near_duplicate_clusters(
            [_key("origin-a"), _key("origin-b")])
        assert clusters[_key("origin-a")] != clusters[_key("origin-b")]

    def test_a_key_with_no_vector_is_absent_never_a_match(self, vector_store):
        clusters = dense.near_duplicate_clusters(
            [_key("origin-a"), ("nope/tap", "missing/SKILL.md")])
        assert ("nope/tap", "missing/SKILL.md") not in clusters

    def test_threshold_is_a_real_parameter(self, vector_store):
        # A mutant that hardcodes the module constant instead of reading the
        # argument fails this: tightening the threshold below the pair's
        # actual similarity (~0.9968) must break the cluster apart.
        keys = [_key("origin-a"), _key("mirror-a")]
        loose = dense.near_duplicate_clusters(keys, threshold=0.5)
        tight = dense.near_duplicate_clusters(keys, threshold=0.9999)
        assert loose[_key("origin-a")] == loose[_key("mirror-a")]
        assert tight[_key("origin-a")] != tight[_key("mirror-a")]


@_NEEDS_SQLITE_VEC
class TestCollapsingHitsThroughTheRealStore:
    def _hits(self, order, curated=None):
        curated = curated or {}
        return [_hit(n, "acme/skills", float(len(order) - i),
                     skill_md="skills/%s/SKILL.md" % n,
                     curated=curated.get(n, False))
                for i, n in enumerate(order)]

    def test_a_near_duplicate_pair_collapses_to_one_slot(self, vector_store):
        hits = self._hits(["origin-a", "mirror-a", "origin-b"])
        out = rag._collapse_near_duplicates(hits, limit=10)
        names = [h["entry"]["name"] for h in out]
        assert names == ["origin-a", "origin-b"]

    def test_the_earlier_ranked_copy_keeps_the_slot_by_default(
            self, vector_store):
        hits = self._hits(["origin-a", "mirror-a"])
        out = rag._collapse_near_duplicates(hits, limit=10)
        assert out[0]["entry"]["name"] == "origin-a"

    def test_a_curated_later_copy_promotes_the_displayed_source(
            self, vector_store):
        # Same question `dedupe_by_content` answers for byte-identical
        # copies: within a cluster, the curated source wins the display slot
        # even when it ranked lower.
        hits = self._hits(["origin-a", "mirror-a"],
                          curated={"mirror-a": True})
        out = rag._collapse_near_duplicates(hits, limit=10)
        assert len(out) == 1
        assert out[0]["entry"]["name"] == "mirror-a"

    def test_the_three_member_cluster_also_collapses_to_one(
            self, vector_store):
        hits = self._hits(["origin-b", "mirror-b1", "mirror-b2"])
        out = rag._collapse_near_duplicates(hits, limit=10)
        assert len(out) == 1

    def test_a_pair_outside_the_pool_window_is_left_alone(self, vector_store):
        # `limit=1` bounds the pool to `NEAR_DUP_POOL_FACTOR` survivors; a
        # near-duplicate ranked past that window is not fetched by the SQL
        # join at all, so it cannot be collapsed. Pins the window as a real
        # bound, not a decoration -- a mutant that ignores it collapses this
        # anyway.
        # limit=1 bounds the pool to NEAR_DUP_POOL_FACTOR (4) survivors: the
        # three "b" mirrors fill it, so "mirror-a" lands just past the
        # window and its "origin-a" partner is the last item inside it.
        filler = ["origin-b", "mirror-b1", "mirror-b2"]
        limit = 1
        assert limit * rag.NEAR_DUP_POOL_FACTOR == len(filler) + 1
        hits = self._hits([*filler, "origin-a", "mirror-a"])
        out = rag._collapse_near_duplicates(hits, limit=limit)
        names = [h["entry"]["name"] for h in out]
        assert names.count("origin-a") == 1 and names.count("mirror-a") == 1

    def test_dedupe_hits_collapses_and_then_truncates(self, vector_store):
        hits = self._hits(["origin-a", "mirror-a", "origin-b"])
        out = rag.dedupe_hits(hits, limit=1)
        assert len(out) == 1
        assert out[0]["entry"]["name"] == "origin-a"

    def test_byte_identical_dedup_still_runs_first(self, vector_store):
        # A byte-identical copy of `origin-a` must still collapse even
        # though its vector (in this fixture) differs -- content identity is
        # decided before near-duplicate clustering ever runs.
        hits = self._hits(["origin-a", "origin-b"])
        hits[0]["content"] = "same-body"
        hits.append(_hit("origin-a-mirror-file", "acme/skills", 0.5,
                         content="same-body",
                         skill_md="skills/origin-a/SKILL2.md"))
        out = rag.dedupe_hits(hits, limit=10)
        names = [h["entry"]["name"] for h in out]
        assert names.count("origin-a") + names.count("origin-a-mirror-file") == 1
