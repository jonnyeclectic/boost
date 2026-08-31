# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The dense store keeps one vector per distinct embedding, not one per copy.

`_embed_and_store` already bought each distinct text **once** — `seen`
de-duplicates before the provider call, which is why `build`'s progress total
counts distinct texts rather than rows. The *storage* never got the same
treatment: every chunk row had its own `vec_raw` blob and its own
`vec_chunks_bin` row, so a paragraph vendored into 1,464 skills was stored
1,464 times.

Measured on a real 657,587-chunk / 384-d store: those rows collapse to
**396,638 distinct** — 39.7% repeats. `vec_raw` is 1,287.6 MB and
`vec_chunks_bin` 45.1 MB of a 1,634 MB file, so vectors are 81.6% of it and
deduplicating them saves 529 MB; adding back `chunks.vid` and two indexes, the
honest figure is **1,634 -> ~1,140 MB, 1.43x whole-store**.

Three things this file pins, because each is a silent failure:

* **The key is the embedding blob, not the text.** `export_shard` ships
  `snip` (``text[:200]``), never the full chunk, so `import_shard` has nothing
  to hash — a text-keyed column would be unpopulatable on the import path.
  ``sha256(embedding)`` is equivalent by construction and works on every path.
* **Deletion GCs after the row delete, never before.** A refcount taken while
  the rows are still there counts references about to vanish, so every shared
  vector looks live and survives forever; every sweep in `dense` is scoped
  through `chunks`, so nothing revisits it.
* **A NULL hash never matches.** :func:`dense._adopt_vectors` joins a store
  built before this relation *without reading its blobs*, so those rows carry
  no hash. Treating two absences as a match would hand a build a vector it had
  never compared — CLAUDE.md's rule, one layer down.

Most of the file runs **without the sqlite-vec extension**, against plain
tables, so it keeps killing mutants on the default zero-dependency install.
The classes that need a real `vec0` store are marked, and cover the fourth
corner of the matrix: quantized *and* deduplicated.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import struct

import pytest

from boost_cli.core import dense, embed, rag
from boost_cli.errors import BoostError


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


needs_vec = pytest.mark.skipif(
    not _vec_loadable(), reason="sqlite-vec extension not loadable here")


class _FakeVec:
    """Stands in for the sqlite_vec module without the C extension."""

    @staticmethod
    def serialize_float32(vec):
        return b"".join(struct.pack("<f", x) for x in vec)

    @staticmethod
    def load(con):
        pass


def _toy_embed(texts, input_type=None, timeout=60):
    """One vector per distinct text, so identical bodies serialize identically."""
    out = []
    for t in texts:
        h = hashlib.sha256(t.encode()).digest()
        out.append([float(h[i]) / 255.0 for i in range(8)])
    return out


def _e(name, body, tap="acme/skills", kind="skill"):
    return {"name": name, "tap": tap, "kind": kind,
            "skill_md": "skills/%s/SKILL.md" % name, "_body": body,
            "content": "d-" + hashlib.sha256(body.encode()).hexdigest()[:8]}


def _plain_schema(con, dim):
    """`_ensure_schema` minus the vec0 virtual table it cannot create here.

    The `chunks` and `vectors` shapes are the real ones —
    ``test_dense_entry_reuse.TestTheStandInSchemaMatchesTheReal`` fails if
    either drifts, which is how the previous stand-in silently claimed to be
    the current INDEX_VERSION while building the version before it.
    """
    con.execute(
        "CREATE TABLE IF NOT EXISTS chunks (id INTEGER PRIMARY KEY"
        " AUTOINCREMENT, name TEXT, tap TEXT, path TEXT, kind TEXT,"
        " cix INTEGER, snip TEXT, digest TEXT, vid INTEGER)")
    con.execute("CREATE INDEX IF NOT EXISTS chunks_tap ON chunks(tap)")
    con.execute("CREATE INDEX IF NOT EXISTS chunks_entry ON chunks(tap, path)")
    con.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS vectors (vid INTEGER PRIMARY KEY"
                " AUTOINCREMENT, hash BLOB)")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS vectors_hash"
                " ON vectors(hash)")
    dense._adopt_vectors(con)
    con.execute("CREATE INDEX IF NOT EXISTS chunks_vid ON chunks(vid)")
    con.execute("CREATE TABLE IF NOT EXISTS vec_chunks (rowid INTEGER PRIMARY"
                " KEY, embedding BLOB)")


@pytest.fixture()
def store(sandbox, tmp_path, monkeypatch):
    """A real `dense.build` pipeline over plain tables — no extension needed."""
    dbfile = tmp_path / "vec.sqlite"
    monkeypatch.setattr(dense, "_load", lambda: _FakeVec)
    monkeypatch.setattr(dense, "_connect",
                        lambda: sqlite3.connect(str(dbfile)))
    monkeypatch.setattr(dense, "_ensure_schema", _plain_schema)
    monkeypatch.setattr(dense, "db_path", lambda: dbfile)
    monkeypatch.setattr(dense, "have_backend", lambda: True)
    monkeypatch.setattr(dense, "read_body", lambda e, tp=None: e["_body"])
    monkeypatch.setattr(embed, "available", lambda: True)
    monkeypatch.setattr(embed, "provider", lambda: "openai")
    monkeypatch.setattr(embed, "model", lambda: "toy-8")
    monkeypatch.setattr(embed, "dimension", lambda: 8)
    monkeypatch.setattr(embed, "embed", _toy_embed)
    monkeypatch.setattr(rag, "_tap_paths",
                        lambda: {"acme/skills": "/x", "other/skills": "/y"})
    monkeypatch.setattr(rag, "_tap_commits",
                        lambda: {"acme__skills": "c1", "other__skills": "c1"})
    return monkeypatch


def _open():
    return sqlite3.connect(str(dense.db_path()))


def _one(con, sql, params=()):
    return con.execute(sql, params).fetchone()[0]


def _counts(con):
    return {"chunks": _one(con, "SELECT COUNT(*) FROM chunks"),
            "vectors": _one(con, "SELECT COUNT(*) FROM vectors"),
            "blobs": _one(con, "SELECT COUNT(*) FROM vec_chunks")}


def _unresolved(con) -> int:
    """Chunks naming a vector the store does not hold. Must always be 0."""
    return _one(con, "SELECT COUNT(*) FROM chunks c WHERE NOT EXISTS "
                     "(SELECT 1 FROM vec_chunks v WHERE v.rowid = c.vid)")


def _orphans(con) -> int:
    """Vectors no chunk names. Must be 0 after any build or GC cycle."""
    return _one(con, "SELECT COUNT(*) FROM vec_chunks v WHERE NOT EXISTS "
                     "(SELECT 1 FROM chunks c WHERE c.vid = v.rowid)")


# --------------------------------------------------------------- one per text

class TestOneVectorPerDistinctEmbedding:
    def test_mirrored_copies_share_one_stored_vector(self, store):
        body = "one pasted paragraph"
        dense.build(entries=[_e("a", body), _e("b", body), _e("c", body)],
                    force=True)
        con = _open()
        try:
            assert _counts(con) == {"chunks": 3, "vectors": 1, "blobs": 1}
            assert _unresolved(con) == 0
        finally:
            con.close()

    def test_distinct_texts_each_get_their_own(self, store):
        dense.build(entries=[_e("a", "alpha"), _e("b", "beta")], force=True)
        con = _open()
        try:
            assert _counts(con) == {"chunks": 2, "vectors": 2, "blobs": 2}
        finally:
            con.close()

    def test_every_copy_still_gets_its_own_chunk_row(self, store):
        """Tap deletion is scoped by `chunks.tap`; collapsing rows would strand
        a tap's vectors. Only the storage behind them is shared."""
        body = "shared"
        dense.build(entries=[_e("a", body), _e("b", body, tap="other/skills")],
                    force=True)
        con = _open()
        try:
            per_tap = dict(con.execute(
                "SELECT tap, COUNT(*) FROM chunks GROUP BY tap"))
            assert per_tap == {"acme/skills": 1, "other/skills": 1}
            assert _one(con, "SELECT COUNT(DISTINCT vid) FROM chunks") == 1
        finally:
            con.close()

    def test_the_saving_crosses_builds_not_just_one_run(self, store):
        """`seen` was a local dict, so reuse died with the call.

        A blob-keyed table makes it persistent: a registry tapped later, whose
        content is already stored, costs no new vector row at all.
        """
        body = "vendored boilerplate"
        dense.build(entries=[_e("a", body)], force=True)
        con = _open()
        try:
            first = _one(con, "SELECT vid FROM chunks")
        finally:
            con.close()
        # A different tap, a later build, the same text.
        dense.build(entries=[_e("a", body), _e("z", body, tap="other/skills")])
        con = _open()
        try:
            assert _counts(con)["vectors"] == 1, "a second copy was stored"
            assert {r[0] for r in con.execute("SELECT vid FROM chunks")} \
                == {first}
        finally:
            con.close()

    def test_the_stored_bytes_are_the_ones_that_were_embedded(self, store):
        """The compression must be invisible: same text, same vector."""
        body = "alpha"
        dense.build(entries=[_e("a", body), _e("b", body)], force=True)
        expected = _FakeVec.serialize_float32(_toy_embed([body])[0])
        con = _open()
        try:
            rows = con.execute(
                "SELECT c.name, v.embedding FROM chunks c "
                "JOIN vec_chunks v ON v.rowid = c.vid ORDER BY c.name"
            ).fetchall()
        finally:
            con.close()
        assert [r[0] for r in rows] == ["a", "b"]
        assert {bytes(r[1]) for r in rows} == {expected}

    def test_the_hash_is_over_the_embedding_not_the_text(self, store):
        """`import_shard` has only the vector, so the key must be the vector.

        Pinned as the stored value rather than as source: a key derived from
        the text would be unpopulatable on the import path and this is the one
        assertion that catches it having been swapped back.
        """
        body = "alpha"
        dense.build(entries=[_e("a", body)], force=True)
        blob = _FakeVec.serialize_float32(_toy_embed([body])[0])
        con = _open()
        try:
            stored = con.execute("SELECT hash FROM vectors").fetchone()[0]
        finally:
            con.close()
        assert bytes(stored) == hashlib.sha256(blob).digest()


# ------------------------------------------------------------ refcounted GC

class TestDeletionCountsReferentsAfterTheRowsAreGone:
    def test_a_shared_vector_outlives_one_of_its_chunks(self, store):
        body = "shared"
        dense.build(entries=[_e("a", body), _e("b", body)], force=True)
        con = _open()
        try:
            dense._delete_entries(con, [("acme/skills", "skills/a/SKILL.md")])
            con.commit()
            assert _counts(con) == {"chunks": 1, "vectors": 1, "blobs": 1}
            assert _unresolved(con) == 0, \
                "the surviving chunk lost the vector it still names"
        finally:
            con.close()

    def test_the_last_referent_takes_the_vector_with_it(self, store):
        body = "shared"
        dense.build(entries=[_e("a", body), _e("b", body)], force=True)
        con = _open()
        try:
            dense._delete_taps(con, ["acme/skills"])
            con.commit()
            assert _counts(con) == {"chunks": 0, "vectors": 0, "blobs": 0}
        finally:
            con.close()

    def test_the_refcount_is_taken_after_the_rows_are_deleted(self, store):
        """The ordering, asserted where reversing it is observable.

        `_delete_matching` used to drop vectors *then* rows, which was right
        while the two were one-to-one. Counting referents before the DELETE
        sees the row that is about to go, so the vector reads as live, is kept,
        and no later sweep can reach it — every one of them is scoped through
        `chunks`.
        """
        dense.build(entries=[_e("a", "only-one")], force=True)
        con = _open()
        try:
            dense._delete_taps(con, ["acme/skills"])
            con.commit()
            assert _orphans(con) == 0, \
                "the vector was counted before its chunk was deleted"
            assert _counts(con)["vectors"] == 0
        finally:
            con.close()

    def test_gc_is_a_noop_when_handed_nothing(self, store):
        dense.build(entries=[_e("a", "alpha")], force=True)
        con = _open()
        try:
            assert dense._gc_vectors(con, []) == 0
            assert _counts(con)["vectors"] == 1
        finally:
            con.close()

    def test_gc_reports_how_many_it_dropped(self, store):
        dense.build(entries=[_e("a", "alpha"), _e("b", "beta")], force=True)
        con = _open()
        try:
            vids = [r[0] for r in con.execute("SELECT vid FROM chunks")]
            con.execute("DELETE FROM chunks")
            assert dense._gc_vectors(con, vids) == 2
            assert _counts(con) == {"chunks": 0, "vectors": 0, "blobs": 0}
        finally:
            con.close()

    def test_gc_de_duplicates_the_ids_it_is_handed(self, store):
        """Two chunks of one vector give `_delete_matching` the vid twice."""
        body = "shared"
        dense.build(entries=[_e("a", body), _e("b", body)], force=True)
        con = _open()
        try:
            vids = [r[0] for r in con.execute("SELECT vid FROM chunks")]
            assert len(vids) == 2 and len(set(vids)) == 1
            con.execute("DELETE FROM chunks")
            assert dense._gc_vectors(con, vids) == 1, "one vector, counted twice"
        finally:
            con.close()

    def test_a_rebuild_of_a_changed_entry_leaves_nothing_behind(self, store):
        dense.build(entries=[_e("a", "alpha"), _e("b", "beta")], force=True)
        store.setattr(rag, "_tap_commits",
                      lambda: {"acme__skills": "c2", "other__skills": "c1"})
        dense.build(entries=[_e("a", "alpha"), _e("b", "beta REWRITTEN")])
        con = _open()
        try:
            assert _counts(con) == {"chunks": 2, "vectors": 2, "blobs": 2}
            assert _orphans(con) == 0
            assert _unresolved(con) == 0
        finally:
            con.close()

    def test_the_orphan_sweep_removes_a_vector_nothing_names(self, store):
        dense.build(entries=[_e("a", "alpha")], force=True)
        con = _open()
        try:
            # An interrupted write, hand-made: a vector with no chunk row.
            vid = dense._vector_id(con, b"\x00" * 32)
            assert _orphans(con) == 1
            assert dense._gc_orphan_vectors(con) == 1
            assert _orphans(con) == 0
            assert con.execute("SELECT 1 FROM vectors WHERE vid = ?",
                               (vid,)).fetchone() is None
        finally:
            con.close()

    def test_the_orphan_sweep_survives_a_chunk_with_no_vid(self, store):
        """`NOT IN` against a set containing NULL matches nothing, ever.

        A half-written chunk row is enough to make the sweep silently stop
        sweeping — SQL's three-valued logic turns the whole predicate unknown —
        so the subquery filters the NULLs out rather than trusting there to be
        none.
        """
        dense.build(entries=[_e("a", "alpha")], force=True)
        con = _open()
        try:
            con.execute("INSERT INTO chunks (name, tap, path, kind, cix, vid) "
                        "VALUES ('half', 't', 'p', 'skill', 0, NULL)")
            dense._vector_id(con, b"\x00" * 32)      # the orphan to sweep
            assert dense._gc_orphan_vectors(con) == 1
            assert _counts(con)["vectors"] == 1
        finally:
            con.close()

    def test_dropping_more_vectors_than_one_batch_holds(self, store,
                                                        monkeypatch):
        """`deduplicate` hands this every duplicate at once — 260,949 on a real
        install — and SQLite caps a statement's bound parameters."""
        dense.build(entries=[_e("s%d" % i, "body-%d" % i) for i in range(5)],
                    force=True)
        monkeypatch.setattr(dense, "_DELETE_BATCH", 2)
        con = _open()
        try:
            vids = [r[0] for r in con.execute("SELECT vid FROM chunks")]
            assert len(vids) == 5
            con.execute("DELETE FROM chunks")
            dense._gc_vectors(con, vids)
            assert _counts(con) == {"chunks": 0, "vectors": 0, "blobs": 0}
        finally:
            con.close()

    def test_a_wipe_takes_the_identity_relation_with_it(self, store):
        """A surviving `vectors` row hands a rebuilt store a vid for nothing.

        `build` wipes when the embedding space changes. If the hashes outlived
        the vectors they describe, `_vector_id` would answer from the old table
        and every chunk in the new space would name a row `vec_chunks` no
        longer has — findable by nothing, reported by nothing.
        """
        dense.build(entries=[_e("a", "alpha"), _e("b", "beta")], force=True)
        store.setattr(embed, "model", lambda: "toy-other")
        stats = dense.build(entries=[_e("a", "alpha"), _e("b", "beta")])
        assert stats["model"] == "toy-other"
        con = _open()
        try:
            assert _counts(con) == {"chunks": 2, "vectors": 2, "blobs": 2}
            assert _unresolved(con) == 0, "a chunk named a wiped vector"
        finally:
            con.close()

    def test_the_orphan_sweep_is_a_noop_with_no_vector_relation(self, store):
        """Nothing built is the ordinary empty case, not the corrupt one."""
        con = _open()
        try:
            _plain_schema(con, 8)
            con.execute("DROP TABLE vec_chunks")
            assert dense._gc_orphan_vectors(con) == 0
        finally:
            con.close()

    def test_the_orphan_sweep_keeps_everything_referenced(self, store):
        dense.build(entries=[_e("a", "alpha"), _e("b", "beta")], force=True)
        con = _open()
        try:
            assert dense._gc_orphan_vectors(con) == 0
            assert _counts(con)["vectors"] == 2
        finally:
            con.close()


# ------------------------------------------------------------ shard exchange

class TestShardsTravelThroughVid:
    def test_an_export_carries_every_chunk_of_a_deduplicated_tap(self, store):
        body = "shared"
        dense.build(entries=[_e("a", body), _e("b", body), _e("c", "other")],
                    force=True)
        shard = dense.export_shard("acme/skills")
        assert sorted(c["name"] for c in shard["chunks"]) == ["a", "b", "c"]
        assert all(c["embedding"] for c in shard["chunks"])

    def test_the_copies_export_the_same_bytes(self, store):
        body = "shared"
        dense.build(entries=[_e("a", body), _e("b", body)], force=True)
        embs = {c["embedding"] for c in dense.export_shard("acme/skills")["chunks"]}
        assert len(embs) == 1

    def test_an_import_shares_storage_with_rows_already_here(self, store):
        """The download that costs no new vectors: a mirror of what is stored."""
        body = "shared"
        dense.build(entries=[_e("a", body)], force=True)
        exported = dense.export_shard("acme/skills")
        shard = dict(exported, tap="other/skills", commit="c1")
        for c in shard["chunks"]:
            c["tap"] = "other/skills"
        ok, why = dense.import_shard(shard, commit="c1")
        assert ok, why
        con = _open()
        try:
            assert _counts(con) == {"chunks": 2, "vectors": 1, "blobs": 1}
            assert _unresolved(con) == 0
        finally:
            con.close()

    def test_re_importing_a_tap_replaces_rather_than_doubles(self, store):
        dense.build(entries=[_e("a", "alpha")], force=True)
        shard = dict(dense.export_shard("acme/skills"), commit="c1")
        assert dense.import_shard(shard, commit="c1")[0]
        assert dense.import_shard(shard, commit="c1")[0]
        con = _open()
        try:
            assert _counts(con) == {"chunks": 1, "vectors": 1, "blobs": 1}
            assert _orphans(con) == 0
        finally:
            con.close()


# ------------------------------------------------------------ the pool expander

class TestExpandBoundsThePool:
    def _seeded(self, n_per_vector, vectors=2):
        con = sqlite3.connect(":memory:")
        _plain_schema(con, 8)
        ranked = []
        for v in range(vectors):
            con.execute("INSERT INTO vectors (vid) VALUES (NULL)")
            vid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
            for i in range(n_per_vector):
                con.execute(
                    "INSERT INTO chunks (name, tap, path, kind, cix, vid) "
                    "VALUES (?, 't', ?, 'skill', 0, ?)",
                    ("c%d-%d" % (v, i), "p%d-%d" % (v, i), vid))
            ranked.append((vid, 0.1 * v, b"k%d" % v))
        return con, ranked

    def test_no_vector_contributes_more_than_the_cap(self):
        con, ranked = self._seeded(n_per_vector=20)
        try:
            out = dense._expand(con, ranked, pool=100)
        finally:
            con.close()
        from collections import Counter
        per = Counter(v for _c, _d, v in out)
        assert max(per.values()) == dense.MAX_PER_VECTOR, per
        assert len(per) == 2, "the freed slots went to the next vector"

    def test_the_walk_stops_at_the_pool(self):
        con, ranked = self._seeded(n_per_vector=20, vectors=8)
        try:
            out = dense._expand(con, ranked, pool=5)
        finally:
            con.close()
        assert len(out) == 5

    def test_the_distance_travels_with_every_copy(self):
        con, ranked = self._seeded(n_per_vector=2, vectors=2)
        try:
            out = dense._expand(con, ranked, pool=100)
        finally:
            con.close()
        assert {d for _c, d, _v in out} == {0.0, 0.1}

    def test_a_vector_with_no_chunks_yields_nothing(self):
        con, ranked = self._seeded(n_per_vector=1, vectors=1)
        try:
            out = dense._expand(con, [*ranked, (999, 0.9, b"ghost")], pool=10)
        finally:
            con.close()
        assert len(out) == 1

    def test_nothing_ranked_expands_to_nothing(self):
        con, _ranked = self._seeded(n_per_vector=1)
        try:
            assert dense._expand(con, [], pool=10) == []
        finally:
            con.close()

    def test_it_works_on_a_store_that_predates_the_relation(self):
        """The window is over `id` there, and every group has one row.

        A user who upgrades and searches before reindexing runs this shape, so
        it has to answer with the same rows the previous `_knn` returned rather
        than raise on a column that is not there yet.
        """
        con = sqlite3.connect(":memory:")
        try:
            con.execute(
                "CREATE TABLE chunks (id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " name TEXT, tap TEXT, path TEXT, kind TEXT, cix INTEGER,"
                " snip TEXT, digest TEXT)")
            for i in range(3):
                con.execute(
                    "INSERT INTO chunks (name, tap, path, kind, cix) "
                    "VALUES (?, 't', ?, 'skill', 0)", ("c%d" % i, "p%d" % i))
            assert dense._vid_col(con) == "id"
            out = dense._expand(con, [(1, 0.1, b"a"), (3, 0.2, b"b")], pool=10)
        finally:
            con.close()
        assert out == [(1, 0.1, b"a"), (3, 0.2, b"b")]


class TestVidColNamesTheRightColumn:
    def test_a_missing_table_reads_as_a_missing_column(self):
        con = sqlite3.connect(":memory:")
        try:
            assert dense._has_column(con, "chunks", "vid") is False
        finally:
            con.close()

    def test_an_unusable_connection_reads_as_a_missing_column(self):
        """`_vid_col` runs on the search path, where raising is the worst answer.

        A store that cannot answer a PRAGMA is a store dense cannot serve;
        reporting "no such column" routes the caller down the pre-migration
        query, which is wrong but harmless, where an exception out of `_knn`
        takes the whole `boost search` down with it.
        """
        con = sqlite3.connect(":memory:")
        con.close()
        assert dense._has_column(con, "chunks", "vid") is False
        assert dense._vid_col(con) == "id"

    def test_it_reads_id_before_the_relation_and_vid_after(self):
        con = sqlite3.connect(":memory:")
        try:
            con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY)")
            assert dense._vid_col(con) == "id"
            con.execute("ALTER TABLE chunks ADD COLUMN vid INTEGER")
            assert dense._vid_col(con) == "vid"
            assert dense._has_column(con, "chunks", "nope") is False
        finally:
            con.close()


# ------------------------------------------------------------ in-place migration

def _legacy_store(dbfile, rows, dim=8):
    """A v3 store as boost wrote one BEFORE the vectors relation existed.

    No `vid` column, no `vectors` table, one `vec_chunks` row per chunk keyed
    by the chunk's own id — which is exactly why `vid = id` is the identity
    those two numbers already had rather than a placeholder.
    """
    con = sqlite3.connect(str(dbfile))
    try:
        con.execute(
            "CREATE TABLE chunks (id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " name TEXT, tap TEXT, path TEXT, kind TEXT, cix INTEGER,"
            " snip TEXT, digest TEXT)")
        con.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
        con.execute("CREATE TABLE vec_chunks (rowid INTEGER PRIMARY KEY,"
                    " embedding BLOB)")
        for name, body in rows:
            cur = con.execute(
                "INSERT INTO chunks (name, tap, path, kind, cix, snip, digest)"
                " VALUES (?, 'acme/skills', ?, 'skill', 0, ?, ?)",
                (name, "skills/%s/SKILL.md" % name, body[:200],
                 "d-" + hashlib.sha256(body.encode()).hexdigest()[:8]))
            con.execute("INSERT INTO vec_chunks (rowid, embedding) VALUES (?, ?)",
                        (cur.lastrowid,
                         _FakeVec.serialize_float32(_toy_embed([body])[0])))
        meta = {"version": dense.INDEX_VERSION, "provider": "openai",
                "model": "toy-8", "dim": dim,
                "commits": {"acme__skills": "c1"}}
        con.executemany("INSERT OR REPLACE INTO meta (k, v) VALUES (?, ?)",
                        [(k, json.dumps(v)) for k, v in meta.items()])
        con.commit()
    finally:
        con.close()


class TestAdoptingAStoreBuiltBeforeTheRelation:
    def test_the_column_is_added_and_reads_as_the_identity(self, store,
                                                           tmp_path):
        _legacy_store(dense.db_path(), [("a", "alpha"), ("b", "beta")])
        con = _open()
        try:
            assert dense._vid_col(con) == "id", "the pre-migration shape"
            _plain_schema(con, 8)
            con.commit()
            assert dense._vid_col(con) == "vid"
            assert [r[0] for r in con.execute(
                "SELECT id FROM chunks WHERE vid IS NOT id")] == []
            assert _counts(con) == {"chunks": 2, "vectors": 2, "blobs": 2}
        finally:
            con.close()

    def test_it_reads_no_embeddings(self, store):
        """Structural only — that is what lets it run inside an ordinary build.

        Reading blobs is `deduplicate()`'s job and costs a pass over gigabytes;
        this one touches an integer column. Pinned by the hashes it leaves
        alone: every adopted row keeps a NULL.
        """
        _legacy_store(dense.db_path(), [("a", "same"), ("b", "same")])
        con = _open()
        try:
            _plain_schema(con, 8)
            con.commit()
            hashes = [r[0] for r in con.execute("SELECT hash FROM vectors")]
        finally:
            con.close()
        assert hashes == [None, None]

    def test_a_null_hash_is_never_a_match(self, store):
        """Two absences are two unknowns — CLAUDE.md's rule, one layer down.

        The adopted rows have not been compared to anything, so a build must
        store its own copy rather than claim one of them. The cost is a missed
        saving, which `deduplicate()` reclaims; the alternative is a wrong
        vector that nothing later notices.
        """
        _legacy_store(dense.db_path(), [("a", "same"), ("b", "same")])
        con = _open()
        try:
            _plain_schema(con, 8)
            blob = _FakeVec.serialize_float32(_toy_embed(["same"])[0])
            vid = dense._vector_id(con, blob)
            con.commit()
            assert vid not in (1, 2), "an unhashed row was claimed as a match"
            assert _counts(con)["vectors"] == 3
        finally:
            con.close()

    def test_adopting_twice_changes_nothing(self, store):
        _legacy_store(dense.db_path(), [("a", "alpha")])
        con = _open()
        try:
            _plain_schema(con, 8)
            assert dense._adopt_vectors(con) == 0
            assert _counts(con)["vectors"] == 1
        finally:
            con.close()

    def test_a_build_onto_a_legacy_store_needs_no_version_bump(self, store):
        """The promise `INDEX_VERSION` makes: v3's re-embed was the last one.

        A bump would wipe the store, and `build` would then pay the provider
        for every vector the user already has. The adopted store must instead
        take an ordinary incremental build.
        """
        _legacy_store(dense.db_path(), [("a", "alpha")])
        calls = []
        store.setattr(embed, "embed",
                      lambda *a, **k: calls.append(a) or _toy_embed(*a, **k))
        stats = dense.build(entries=[_e("a", "alpha")])
        assert stats["reused"] == ["acme__skills"], stats
        assert calls == [], "an adopted store was re-embedded"
        con = _open()
        try:
            assert _counts(con) == {"chunks": 1, "vectors": 1, "blobs": 1}
            assert _unresolved(con) == 0
        finally:
            con.close()


class TestDeduplicateCollapsesWhatIsAlreadyOnDisk:
    def test_it_collapses_the_copies_without_losing_a_chunk(self, store):
        _legacy_store(dense.db_path(),
                      [("a", "same"), ("b", "same"), ("c", "same"),
                       ("d", "other")])
        res = dense.deduplicate()
        assert res is not None
        assert res["vectors"] == 2
        assert res["freed"] == 2
        con = _open()
        try:
            assert _counts(con) == {"chunks": 4, "vectors": 2, "blobs": 2}
            assert _unresolved(con) == 0
            assert _orphans(con) == 0
            assert sorted(r[0] for r in con.execute(
                "SELECT name FROM chunks")) == ["a", "b", "c", "d"]
        finally:
            con.close()

    def test_it_re_embeds_nothing(self, store):
        _legacy_store(dense.db_path(), [("a", "same"), ("b", "same")])
        calls = []
        store.setattr(embed, "embed", lambda *a, **k: calls.append(a))
        dense.deduplicate()
        assert calls == [], "deduplicate called the provider"

    def test_the_survivor_is_the_lowest_id(self, store):
        """Why nothing is rewritten: that row is already at that rowid."""
        _legacy_store(dense.db_path(), [("a", "same"), ("b", "same")])
        dense.deduplicate()
        con = _open()
        try:
            assert {r[0] for r in con.execute("SELECT vid FROM chunks")} == {1}
            assert [r[0] for r in con.execute(
                "SELECT rowid FROM vec_chunks")] == [1]
        finally:
            con.close()

    def test_the_bytes_are_untouched(self, store):
        _legacy_store(dense.db_path(), [("a", "same"), ("b", "same")])
        before = _FakeVec.serialize_float32(_toy_embed(["same"])[0])
        dense.deduplicate()
        con = _open()
        try:
            stored = con.execute("SELECT embedding FROM vec_chunks").fetchone()[0]
        finally:
            con.close()
        assert bytes(stored) == before

    def test_it_backfills_the_hashes_so_the_saving_persists(self, store):
        """Without this the next build stores its own copy all over again."""
        _legacy_store(dense.db_path(), [("a", "same"), ("b", "same")])
        dense.deduplicate()
        calls = []
        store.setattr(embed, "embed",
                      lambda *a, **k: calls.append(a) or _toy_embed(*a, **k))
        store.setattr(rag, "_tap_commits",
                      lambda: {"acme__skills": "c2", "other__skills": "c1"})
        dense.build(entries=[_e("a", "same"), _e("b", "same"),
                             _e("z", "same", tap="other/skills")])
        con = _open()
        try:
            assert _counts(con)["vectors"] == 1, \
                "a re-embedded copy was stored beside the migrated one"
        finally:
            con.close()

    def test_running_it_again_reads_nothing(self, store):
        """`reindex --dense` calls this every time, so "done" has to be cheap.

        `vectors.hash` is UNIQUE, so two hashed rows cannot hold the same
        bytes: once nothing is unhashed there is provably nothing to collapse,
        and the probe that says so is a b-tree descent. Re-hashing instead
        would re-read 1.3 GB of blobs on every reindex to reach the same
        answer.
        """
        _legacy_store(dense.db_path(), [("a", "same"), ("b", "same")])
        assert dense.deduplicate() is not None
        assert dense.deduplicate() is None
        con = _open()
        try:
            assert _counts(con) == {"chunks": 2, "vectors": 1, "blobs": 1}
        finally:
            con.close()

    def test_a_store_this_release_built_needs_no_pass_at_all(self, store):
        dense.build(entries=[_e("a", "same"), _e("b", "same")], force=True)
        assert dense.deduplicate() is None

    def test_an_identity_row_naming_no_vector_is_swept(self, store):
        """Otherwise the probe answers "work to do" on every reindex, forever."""
        _legacy_store(dense.db_path(), [("a", "alpha")])
        con = _open()
        try:
            _plain_schema(con, 8)
            con.execute("INSERT INTO vectors (vid, hash) VALUES (99, NULL)")
            con.commit()
        finally:
            con.close()
        assert dense.deduplicate() is not None
        assert dense.deduplicate() is None
        con = _open()
        try:
            assert con.execute("SELECT 1 FROM vectors WHERE vid = 99"
                               ).fetchone() is None
        finally:
            con.close()

    def test_an_unhashed_row_collapses_onto_a_hashed_one(self, store):
        """The seeded map, which a scan of only the unhashed rows still needs.

        A store adopted and then built has both kinds, and a NULL-hash row can
        be a duplicate of one the newer build already stored under its hash.
        """
        _legacy_store(dense.db_path(), [("a", "same")])
        con = _open()
        try:
            _plain_schema(con, 8)
            blob = _FakeVec.serialize_float32(_toy_embed(["same"])[0])
            vid = dense._vector_id(con, blob)     # hashed, stored beside it
            con.execute(
                "INSERT INTO chunks (name, tap, path, kind, cix, vid) VALUES "
                "('b', 'acme/skills', 'skills/b/SKILL.md', 'skill', 0, ?)",
                (vid,))
            con.commit()
            assert _counts(con) == {"chunks": 2, "vectors": 2, "blobs": 2}
        finally:
            con.close()
        res = dense.deduplicate()
        assert res is not None and res["freed"] == 1
        con = _open()
        try:
            assert _counts(con) == {"chunks": 2, "vectors": 1, "blobs": 1}
            assert _unresolved(con) == 0
        finally:
            con.close()

    def test_it_sweeps_an_orphan_before_counting(self, store):
        """An untidy store must migrate, not be refused by its own arithmetic."""
        _legacy_store(dense.db_path(), [("a", "same"), ("b", "same")])
        con = _open()
        try:
            con.execute("INSERT INTO vec_chunks (rowid, embedding) "
                        "VALUES (99, ?)", (b"\x01" * 32,))
            con.commit()
        finally:
            con.close()
        res = dense.deduplicate()
        assert res is not None and res["vectors"] == 1
        con = _open()
        try:
            assert _orphans(con) == 0
            assert _unresolved(con) == 0
        finally:
            con.close()

    def test_it_refuses_and_rolls_back_when_the_arithmetic_disagrees(
            self, store, monkeypatch):
        """The one step that can lose vectors verifies before it commits."""
        _legacy_store(dense.db_path(), [("a", "same"), ("b", "same"),
                                        ("c", "other")])
        real = dense._drop_vectors

        def over_delete(con, vids):
            # Take one row too many — the shape of a migration that loses data.
            real(con, [*vids, 1] if vids else vids)

        monkeypatch.setattr(dense, "_drop_vectors", over_delete)
        with pytest.raises(BoostError, match="store left unchanged"):
            dense.deduplicate()
        con = _open()
        try:
            assert _counts(con)["blobs"] == 3, "the store was left damaged"
        finally:
            con.close()

    def test_it_refuses_when_a_chunk_resolves_to_nothing(self, store):
        """The other half of the verification, and not the same failure.

        A store can end the pass with exactly the right number of vectors and
        still have a chunk naming one that was never there. Counting vectors
        alone would call that a success, and the chunk would simply stop being
        findable — the failure this whole change has to avoid.
        """
        _legacy_store(dense.db_path(), [("a", "same"), ("b", "other")])
        con = _open()
        try:
            _plain_schema(con, 8)         # adopts, so there is work to do
            con.execute("INSERT INTO chunks (name, tap, path, kind, cix, vid) "
                        "VALUES ('ghost', 'acme/skills', 'p', 'skill', 0, 999)")
            con.commit()
        finally:
            con.close()
        with pytest.raises(BoostError, match="store left unchanged"):
            dense.deduplicate()
        con = _open()
        try:
            assert _counts(con)["blobs"] == 2, "the store was left damaged"
        finally:
            con.close()

    def test_it_is_a_no_op_with_no_store(self, store):
        assert dense.deduplicate() is None

    def test_it_is_a_no_op_without_the_backend(self, store, monkeypatch):
        """`reindex --dense` calls this unconditionally; it must not raise."""
        _legacy_store(dense.db_path(), [("a", "alpha")])
        monkeypatch.setattr(dense, "_connect", lambda: None)
        assert dense.deduplicate() is None

    def test_it_is_a_no_op_when_the_width_was_never_recorded(self, store):
        _legacy_store(dense.db_path(), [("a", "alpha")])
        con = _open()
        try:
            con.execute("DELETE FROM meta WHERE k = 'dim'")
            con.commit()
        finally:
            con.close()
        assert dense.deduplicate() is None

    def test_it_is_a_no_op_on_a_store_with_no_vector_relation(self, store,
                                                              monkeypatch):
        con = _open()
        try:
            _plain_schema(con, 8)
            con.execute("DROP TABLE vec_chunks")
            dense._write_meta(con, {"version": dense.INDEX_VERSION, "dim": 8})
            con.commit()
        finally:
            con.close()
        # The stand-in schema would put the table back, which is right for a
        # build and wrong for this question.
        monkeypatch.setattr(dense, "_ensure_schema", lambda con, dim: None)
        assert dense.deduplicate() is None


# ------------------------------------------------------- what reindex runs

class TestReindexRunsTheMigration:
    """`boost reindex --dense` is the only surface, so the wiring is behaviour.

    Both migrations are offline and free, so a user gets the disk back without
    having to know either word — the same argument that put `quantize` here.
    """

    @pytest.fixture()
    def wired(self, monkeypatch):
        from boost_cli.commands import discovery
        monkeypatch.setattr(dense, "have_backend", lambda: True)
        monkeypatch.setattr(embed, "available", lambda: True)
        monkeypatch.setattr(dense, "quantize", lambda: None)
        monkeypatch.setattr(dense, "deduplicate", lambda: None)
        monkeypatch.setattr(dense, "build",
                            lambda force=False, on_progress=None: {"chunks": 9})
        return discovery, monkeypatch

    def test_it_reports_what_was_reclaimed(self, wired):
        discovery, mp = wired
        mp.setattr(dense, "deduplicate",
                   lambda: {"vectors": 4, "freed": 6, "bytes": 1})
        assert discovery._reindex_dense(force=False)["deduplicated"] == 6

    def test_a_store_with_nothing_to_reclaim_says_nothing(self, wired):
        discovery, mp = wired
        mp.setattr(dense, "deduplicate",
                   lambda: {"vectors": 4, "freed": 0, "bytes": 1})
        assert "deduplicated" not in discovery._reindex_dense(force=False)

    def test_it_runs_after_quantize_not_before(self, wired):
        """Order, not decoration.

        `quantize` moves vectors out of `vec_chunks` one rowid at a time and
        verifies the count against the chunk rows; deduplicating first makes
        those two numbers differ by design, and it would refuse.
        """
        discovery, mp = wired
        seen: list[str] = []
        mp.setattr(dense, "quantize", lambda: seen.append("quantize") or None)
        mp.setattr(dense, "deduplicate", lambda: seen.append("dedupe") or None)
        mp.setattr(dense, "build", lambda force=False, on_progress=None:
                   seen.append("build") or {"chunks": 9})
        discovery._reindex_dense(force=False)
        assert seen == ["quantize", "dedupe", "build"]

    def test_nothing_runs_without_a_backend(self, wired, monkeypatch):
        discovery, _mp = wired
        monkeypatch.setattr(dense, "have_backend", lambda: False)
        monkeypatch.setattr(dense, "deduplicate",
                            lambda: pytest.fail("migrated with no backend"))
        assert discovery._reindex_dense(force=False) is None

    def test_the_success_line_names_the_saving(self):
        # Pinned as source because the emitter needs a TTY and a spinner; what
        # must not go missing is the line that tells the user their disk came
        # back, since nothing else reports it.
        import inspect

        from boost_cli.commands import discovery
        src = inspect.getsource(discovery.cmd_reindex)
        assert 'dense_stats.get("deduplicated")' in src
        assert "duplicate vector" in src


def _legacy_quantized_store(entries, dim=8):
    """A quantized store as boost wrote one BEFORE the vectors relation.

    Built with the real `vec0` rather than demoted from a fresh build: the
    thing under test is a shape this release cannot produce, so producing it
    from this release's own output would only prove a round trip. One
    `vec_raw` row and one `vec_chunks_bin` row per CHUNK, no `vid`, no
    `vectors` — which is exactly the 39.7% of rows the migration reclaims.
    """
    from boost_cli.core import paths
    paths.ensure_dirs()
    con = dense._connect()
    assert con is not None, "the extension loads here — see the class marker"
    try:
        con.execute(
            "CREATE TABLE chunks (id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " name TEXT, tap TEXT, path TEXT, kind TEXT, cix INTEGER,"
            " snip TEXT, digest TEXT)")
        con.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
        con.execute("CREATE VIRTUAL TABLE vec_chunks_bin USING "
                    "vec0(embedding bit[%d])" % dim)
        con.execute("CREATE TABLE vec_raw (id INTEGER PRIMARY KEY,"
                    " embedding BLOB)")
        mod = dense._load()
        for e in entries:
            blob = mod.serialize_float32(_toy_embed([e["_body"]])[0])
            cur = con.execute(
                "INSERT INTO chunks (name, tap, path, kind, cix, snip, digest)"
                " VALUES (?, ?, ?, 'skill', 0, ?, ?)",
                (e["name"], e["tap"], e["skill_md"], e["_body"][:200],
                 e["content"]))
            con.execute("INSERT INTO vec_raw (id, embedding) VALUES (?, ?)",
                        (cur.lastrowid, blob))
            con.execute("INSERT INTO vec_chunks_bin (rowid, embedding) VALUES "
                        "(?, vec_quantize_binary(vec_f32(?)))",
                        (cur.lastrowid, blob))
        meta = {"version": dense.INDEX_VERSION, "provider": "openai",
                "model": "toy-8", "dim": dim,
                "commits": {"acme__skills": "c1"}, "chunks": len(entries)}
        con.executemany("INSERT OR REPLACE INTO meta (k, v) VALUES (?, ?)",
                        [(k, json.dumps(v)) for k, v in meta.items()])
        con.commit()
    finally:
        con.close()


# ------------------------------------------- the fourth corner: quantized too

@needs_vec
class TestQuantizedAndDeduplicated:
    """Both branches at once, which no other file reaches.

    `dense` already forked float32-vs-quantized through every vector-touching
    function; "deduplicated or not" makes four combinations, and this is the
    one a real install runs.
    """

    @pytest.fixture()
    def real(self, sandbox, monkeypatch):
        monkeypatch.setattr(embed, "embed", _toy_embed)
        monkeypatch.setattr(embed, "provider", lambda: "openai")
        monkeypatch.setattr(embed, "model", lambda: "toy-8")
        monkeypatch.setattr(embed, "dimension", lambda: 8)
        monkeypatch.setattr(embed, "available", lambda: True)
        monkeypatch.setattr(rag, "_tap_paths", lambda: {"acme/skills": "/x"})
        monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c1"})
        monkeypatch.setattr(dense, "read_body", lambda e, tp=None: e["_body"])
        return monkeypatch

    def test_both_vector_relations_hold_one_row_per_distinct_vector(self, real):
        body = "pasted"
        dense.build(entries=[_e("a", body), _e("b", body), _e("c", "own")],
                    force=True)
        con = dense._connect()
        try:
            assert dense.quantized(con) is True
            assert _one(con, "SELECT COUNT(*) FROM chunks") == 3
            assert _one(con, "SELECT COUNT(*) FROM vec_raw") == 2
            assert _one(con, "SELECT COUNT(*) FROM vec_chunks_bin") == 2
            assert _one(con, "SELECT COUNT(*) FROM chunks c WHERE NOT EXISTS "
                             "(SELECT 1 FROM vec_raw v WHERE v.id = c.vid)") == 0
        finally:
            con.close()

    def test_every_copy_is_still_retrievable(self, real):
        body = "pasted"
        entries = [_e("a", body), _e("b", body), _e("c", "own")]
        dense.build(entries=entries, force=True)
        hits = dense.retrieve(body, k=10, entries=entries)
        assert hits is not None
        names = {h["entry"]["name"] for h in hits}
        assert {"a", "b"} <= names, names

    def test_one_vector_still_cannot_own_the_page(self, real):
        body = "pasted"
        entries = [_e("s%02d" % i, body) for i in range(10)]
        dense.build(entries=entries, force=True)
        hits = dense.retrieve(body, k=10, entries=entries)
        assert hits is not None
        assert len(hits) <= dense.MAX_PER_VECTOR, [
            h["entry"]["name"] for h in hits]

    def test_deleting_one_copy_leaves_the_others_findable(self, real):
        body = "pasted"
        entries = [_e("a", body), _e("b", body)]
        dense.build(entries=entries, force=True)
        real.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c2"})
        dense.build(entries=[entries[1]])
        hits = dense.retrieve(body, k=5, entries=[entries[1]])
        assert hits is not None
        assert [h["entry"]["name"] for h in hits] == ["b"]

    def test_a_shard_round_trips_through_the_quantized_layout(self, real):
        body = "pasted"
        dense.build(entries=[_e("a", body), _e("b", body)], force=True)
        shard = dense.export_shard("acme/skills")
        assert len(shard["chunks"]) == 2
        assert len({c["embedding"] for c in shard["chunks"]}) == 1

    def test_a_fresh_build_has_nothing_left_to_collapse(self, real):
        dense.build(entries=[_e("a", "pasted"), _e("b", "pasted")], force=True)
        assert dense.deduplicate() is None

    def test_the_migration_collapses_both_vector_relations(self, real):
        """The fourth corner: quantized *and* not yet deduplicated.

        `vec_raw` and `vec_chunks_bin` are keyed alike, so a migration that
        forgot one would leave a binary row ranking a vector the rescore can no
        longer fetch — a candidate that silently drops out of every page.
        """
        entries = [_e("a", "pasted"), _e("b", "pasted"), _e("c", "own")]
        _legacy_quantized_store(entries)
        before = [h["entry"]["name"]
                  for h in dense.retrieve("pasted", k=5, entries=entries)]
        res = dense.deduplicate()
        assert res is not None
        assert res["vectors"] == 2 and res["freed"] == 1
        con = dense._connect()
        try:
            assert _one(con, "SELECT COUNT(*) FROM chunks") == 3
            assert _one(con, "SELECT COUNT(*) FROM vec_raw") == 2
            assert _one(con, "SELECT COUNT(*) FROM vec_chunks_bin") == 2
            assert _one(con, "SELECT COUNT(*) FROM chunks c WHERE NOT EXISTS "
                             "(SELECT 1 FROM vec_raw v WHERE v.id = c.vid)") == 0
        finally:
            con.close()
        after = [h["entry"]["name"]
                 for h in dense.retrieve("pasted", k=5, entries=entries)]
        assert after == before, "the migration changed the ranking"

    def test_an_adopted_store_takes_an_incremental_build(self, real):
        """No `INDEX_VERSION` bump, so no re-embed — on the real layout too."""
        entries = [_e("a", "pasted"), _e("b", "pasted")]
        _legacy_quantized_store(entries)
        calls = []
        real.setattr(embed, "embed",
                     lambda *a, **k: calls.append(a) or _toy_embed(*a, **k))
        stats = dense.build(entries=entries)
        assert stats["reused"] == ["acme__skills"], stats
        assert calls == [], "an adopted store was re-embedded"
