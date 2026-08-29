# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Binary quantization: the same answers, 27x less work.

`vec0` has no ANN index, so a float32 `MATCH` computes a distance against every
vector in the store. On a real 750,416-chunk / 1024-d install that is 3.08 GB
read per query and **28.2 s measured**, which was the bulk of a 33.9 s
`boost search` (`~/.boost/logs/boost.log`). The variance users saw — the same
query answering in 2.5 s — was not caching: it was the query-embedding call
failing, `dense.retrieve` returning None, and the search silently falling back
to BM25.

The fix is the standard two-stage: rank on 1-bit-per-dimension vectors (32x
smaller, Hamming distance is a popcount), then re-rank the survivors on their
exact float32 vectors. Measured end to end: 28.2 s -> 1.05 s at **recall@60 of
1.000**.

Both halves are load-bearing and this file pins both:

* without the rescore, the binary pass alone recovers only 0.667 of the true
  top 60 — a quality regression, so `test_the_rescore_is_load_bearing` fails if
  anyone deletes it as an optimization;
* the rescore is only cheap because `vec_raw` is an ordinary rowid-keyed table.
  The same `id IN (...)` against a vec0 table plans as a full scan.

The store fixtures embed with a toy 8-d model — 8 because `bit[N]` packs eight
dimensions to a byte, so sqlite-vec rejects any other width. The 3-d toys
elsewhere in the suite are what keep the float32 fallback covered.
"""
import math
import sqlite3

import pytest

from boost_cli.core import dense, embed, paths, rag


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


pytestmark = pytest.mark.skipif(
    not _vec_loadable(), reason="sqlite-vec extension not loadable here")


# Sixteen directions in 8-d, deterministic and well spread, so a ranking has
# something to get wrong. Signs matter more than magnitudes here: binary
# quantization keeps only the sign, which is exactly why the rescore exists.
def _vec_for(seed: int) -> list[float]:
    v = [math.sin(seed * 1.7 + i * 0.9) for i in range(8)]
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


_BODIES = {"skill-%02d" % i: "body of skill %02d" % i for i in range(16)}
_VEC = {name: _vec_for(i) for i, name in enumerate(sorted(_BODIES))}


def _toy_embed(texts, input_type=None, timeout=60):
    out = []
    for t in texts:
        name = t.split("\n", 1)[0].strip()
        out.append(_VEC.get(name, _vec_for(999)))
    return out


def _e(name, tap="acme/skills"):
    return {"name": name, "tap": tap, "kind": "skill",
            "skill_md": "skills/%s/SKILL.md" % name}


_ENTRIES = [_e(n) for n in sorted(_BODIES)]


@pytest.fixture()
def dense_env(sandbox, monkeypatch):
    monkeypatch.setattr(embed, "embed", _toy_embed)
    monkeypatch.setattr(embed, "provider", lambda: "openai")
    monkeypatch.setattr(embed, "model", lambda: "toy-8")
    monkeypatch.setattr(embed, "dimension", lambda: 8)
    monkeypatch.setattr(embed, "available", lambda: True)
    monkeypatch.setattr(rag, "_tap_paths", lambda: {"acme/skills": "/x"})
    monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c1"})
    monkeypatch.setattr(dense, "read_body", lambda e, tp=None: e["name"])
    return monkeypatch


def _tables() -> set:
    con = sqlite3.connect(str(dense.db_path()))
    try:
        return {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    finally:
        con.close()


def _expected_order(query_name: str) -> list[str]:
    """The true cosine ranking, computed independently of sqlite-vec."""
    q = _VEC[query_name]
    scored = [(sum(a * b for a, b in zip(q, _VEC[n], strict=True)), n)
              for n in sorted(_BODIES)]
    return [n for _s, n in sorted(scored, key=lambda sn: (-sn[0], sn[1]))]


# ------------------------------------------------------------------ layout

class TestLayout:
    def test_a_build_produces_the_two_stage_layout(self, dense_env):
        dense.build(entries=_ENTRIES, force=True)
        t = _tables()
        assert "vec_chunks_bin" in t, "no binary index — every query is a full scan"
        assert "vec_raw" in t, "no exact vectors — nothing to rescore against"

    def test_the_float32_vec0_table_is_gone(self, dense_env):
        """`vec_raw` replaces it: same blobs, in a table that can be indexed."""
        dense.build(entries=_ENTRIES, force=True)
        assert "vec_chunks" not in _tables()

    def test_a_non_quantizable_width_keeps_the_float32_layout(self, sandbox,
                                                              monkeypatch):
        """3 is not a multiple of 8, so `bit[3]` is not a thing sqlite-vec has."""
        monkeypatch.setattr(embed, "dimension", lambda: 3)
        con = dense._connect()
        try:
            dense._ensure_schema(con, 3)
            assert dense.quantized(con) is False
        finally:
            con.close()
        assert "vec_chunks" in _tables()

    @pytest.mark.parametrize(("dim", "ok"), [(0, False), (3, False), (7, False),
                                             (8, True), (384, True), (1024, True),
                                             (1536, True)])
    def test_quantizable_widths(self, dim, ok):
        assert dense._quantizable(dim) is ok

    def test_half_a_migration_is_not_quantized(self, sandbox):
        """One table without the other must not route queries into a rescore."""
        paths.ensure_dirs()
        con = sqlite3.connect(str(dense.db_path()))
        try:
            con.execute("CREATE TABLE vec_raw (id INTEGER PRIMARY KEY, embedding BLOB)")
            assert dense.quantized(con) is False
        finally:
            con.close()


# ------------------------------------------------------------- correctness

class TestRankingIsUnchanged:
    """The claim the whole change rests on: same answers, less work."""

    def test_quantized_retrieval_matches_exact_cosine(self, dense_env):
        dense.build(entries=_ENTRIES, force=True)
        for query in ("skill-00", "skill-07", "skill-13"):
            hits = dense.retrieve(query, k=16, entries=_ENTRIES)
            got = [h["entry"]["name"] for h in hits]
            assert got == _expected_order(query), (
                "quantized ranking diverged from exact cosine for %r" % query)

    def test_the_top_hit_is_the_query_itself(self, dense_env):
        dense.build(entries=_ENTRIES, force=True)
        for query in sorted(_BODIES):
            hits = dense.retrieve(query, k=3, entries=_ENTRIES)
            assert hits[0]["entry"]["name"] == query

    def test_the_rescore_is_load_bearing(self, dense_env):
        """The binary pass alone gets this ranking wrong, and the rescore fixes it.

        Two assertions, because either one alone is misleading. The first
        proves quantization really does lose ordering on this fixture — at
        scale it cost 0.333 of the true top 60 — so the second is not passing
        merely because the data is too easy to get wrong. Delete the rescore as
        "an optimization" and this fails.
        """
        dense.build(entries=_ENTRIES, force=True)
        exact = _expected_order("skill-07")

        con = dense._connect()
        try:
            names = dict(con.execute("SELECT id, name FROM chunks"))
            qblob = dense._load().serialize_float32(_VEC["skill-07"])
            coarse = [names[r[0]] for r in con.execute(
                "SELECT rowid FROM vec_chunks_bin "
                "WHERE embedding MATCH vec_quantize_binary(vec_f32(?)) "
                "ORDER BY distance LIMIT ?", (qblob, len(_BODIES)))]
        finally:
            con.close()

        assert coarse != exact, (
            "the binary pass happened to reproduce the exact ranking here, so "
            "this fixture cannot show whether the rescore does anything")
        rescored = [h["entry"]["name"]
                    for h in dense.retrieve("skill-07", k=16, entries=_ENTRIES)]
        assert rescored == exact

    def test_a_legacy_store_still_ranks_correctly(self, dense_env):
        """The float32 path stays correct — it is what an unmigrated user runs."""
        dense.build(entries=_ENTRIES, force=True)
        _demote_to_legacy()
        con = dense._connect()
        try:
            assert dense.quantized(con) is False
        finally:
            con.close()
        got = [h["entry"]["name"]
               for h in dense.retrieve("skill-00", k=16, entries=_ENTRIES)]
        assert got == _expected_order("skill-00")


def _demote_to_legacy() -> None:
    """Rewrite a quantized store into the old float32 layout.

    Used to build the "user who has not migrated" fixture from a real build,
    rather than hand-rolling a second store shape that could drift from what
    the previous release actually wrote.
    """
    con = dense._connect()
    try:
        dim = int(dense._read_meta(con).get("dim") or 8)
        con.execute("CREATE VIRTUAL TABLE vec_chunks USING "
                    "vec0(embedding float[%d] distance_metric=cosine)" % dim)
        for rid, blob in con.execute("SELECT id, embedding FROM vec_raw").fetchall():
            con.execute("INSERT INTO vec_chunks (rowid, embedding) VALUES (?, ?)",
                        (rid, blob))
        con.execute("DROP TABLE vec_chunks_bin")
        con.execute("DROP TABLE vec_raw")
        con.commit()
    finally:
        con.close()


# --------------------------------------------------------------- migration

class TestQuantizeMigration:
    def test_it_converts_a_legacy_store_without_re_embedding(self, dense_env):
        dense.build(entries=_ENTRIES, force=True)
        _demote_to_legacy()
        calls = []
        dense_env.setattr(embed, "embed",
                          lambda *a, **k: calls.append(a) or _toy_embed(*a, **k))
        res = dense.quantize()
        assert res is not None
        assert res["chunks"] == len(_ENTRIES)
        assert calls == [], "quantize re-embedded — it must be offline and free"
        t = _tables()
        assert "vec_chunks_bin" in t and "vec_raw" in t
        assert "vec_chunks" not in t

    def test_the_ranking_survives_the_migration(self, dense_env):
        dense.build(entries=_ENTRIES, force=True)
        before = [h["entry"]["name"]
                  for h in dense.retrieve("skill-04", k=16, entries=_ENTRIES)]
        _demote_to_legacy()
        dense.quantize()
        after = [h["entry"]["name"]
                 for h in dense.retrieve("skill-04", k=16, entries=_ENTRIES)]
        assert after == before == _expected_order("skill-04")

    def test_it_records_the_chunk_total(self, dense_env):
        """So the next `status()` answers from `meta` instead of counting."""
        dense.build(entries=_ENTRIES, force=True)
        _demote_to_legacy()
        dense.quantize()
        assert dense._recorded_meta().get("chunks") == len(_ENTRIES)

    def test_it_is_a_no_op_on_an_already_quantized_store(self, dense_env):
        dense.build(entries=_ENTRIES, force=True)
        assert dense.quantize() is None

    def test_it_is_a_no_op_with_no_store(self, dense_env):
        assert dense.quantize() is None

    def test_it_is_a_no_op_without_the_backend(self, dense_env, monkeypatch):
        """`reindex --dense` calls this unconditionally; it must not raise."""
        dense.build(entries=_ENTRIES, force=True)
        _demote_to_legacy()
        monkeypatch.setattr(dense, "_connect", lambda: None)
        assert dense.quantize() is None

    def test_it_is_a_no_op_for_a_width_it_cannot_quantize(self, dense_env):
        """A 3-d store stays float32 rather than being half-converted."""
        con = dense._connect()
        try:
            dense._ensure_schema(con, 3)
            dense._write_meta(con, {"version": dense.INDEX_VERSION, "dim": 3})
            con.commit()
        finally:
            con.close()
        assert dense.quantize() is None
        assert "vec_chunks" in _tables()

    def test_it_is_a_no_op_when_the_width_was_never_recorded(self, dense_env):
        """No `dim` in meta means no way to size `bit[N]` — leave it alone."""
        paths.ensure_dirs()
        con = dense._connect()
        try:
            dense._ensure_schema(con, 3)
            con.commit()
        finally:
            con.close()
        assert dense.quantize() is None

    def test_a_short_copy_leaves_the_store_intact(self, dense_env, monkeypatch):
        """The one step that can lose vectors must verify before it destroys.

        Re-embedding 750,416 chunks is a bill, not an inconvenience, so a
        partial copy has to abort with the float32 table still standing.
        """
        from boost_cli.errors import BoostError
        dense.build(entries=_ENTRIES, force=True)
        _demote_to_legacy()
        real = dense._chunk_total
        monkeypatch.setattr(
            dense, "_chunk_total",
            lambda con, meta, *, exact: (real(con, meta, exact=exact)[0] + 5, True))
        with pytest.raises(BoostError, match="store left unchanged"):
            dense.quantize()
        assert "vec_chunks" in _tables(), "vectors were dropped after a short copy"


class TestEmptyStore:
    def test_no_candidates_yields_no_hits_rather_than_an_error(self, dense_env):
        """An empty binary index is a thin store, not a failed query.

        `retrieve_any` treats `[]` and `None` differently on purpose — `[]`
        means "dense had nothing to say", which must still let BM25 answer, and
        raising here would take the whole search down with it.
        """
        dense.build(entries=_ENTRIES, force=True)
        con = dense._connect()
        try:
            con.execute("DELETE FROM vec_chunks_bin")
            con.commit()
            qblob = dense._load().serialize_float32(_VEC["skill-00"])
            assert dense._knn(con, qblob, 60) == []
        finally:
            con.close()
        assert dense.retrieve("skill-00", k=5, entries=_ENTRIES) == []


# ------------------------------------------------------------------ upkeep

class TestTapDeletion:
    def test_removing_a_tap_clears_every_vector_relation(self, dense_env):
        """A row left in one table and not the other resurfaces as a ghost hit."""
        entries = [*_ENTRIES, _e("other-00", tap="other/repo")]
        dense_env.setattr(rag, "_tap_paths",
                          lambda: {"acme/skills": "/x", "other/repo": "/y"})
        dense_env.setattr(rag, "_tap_commits",
                          lambda: {"acme__skills": "c1", "other__repo": "c1"})
        dense.build(entries=entries, force=True)
        con = dense._connect()
        try:
            ids = [r[0] for r in con.execute(
                "SELECT id FROM chunks WHERE tap = ?", ("other/repo",))]
            assert ids
            dense._drop_vectors(con, ids)
            con.commit()
            q = ",".join("?" * len(ids))
            for tbl, col in (("vec_raw", "id"), ("vec_chunks_bin", "rowid")):
                left = con.execute(
                    "SELECT COUNT(*) FROM %s WHERE %s IN (%s)"  # noqa: S608
                    % (tbl, col, q), ids).fetchone()[0]
                assert left == 0, "%s kept vectors for a deleted tap" % tbl
        finally:
            con.close()
