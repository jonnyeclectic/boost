# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/dense.py WITHOUT the sqlite-vec extension.

``test_dense.py`` exercises the real vector store, but its whole module is
``skipif``-gated on the sqlite-vec C extension being loadable — so on the
default zero-dependency install (no ``[rag]`` extra, the common case), *every*
one of those tests skips and dense.py's graceful-degradation and pure-ranking
paths go completely untested. That is precisely the configuration most users
run in.

These tests never touch the extension: they force ``dense._load() -> None`` to
simulate its absence, drive the SQL helpers against a plain in-memory sqlite,
and feed :func:`dense.retrieve`'s ranking reducer canned rows through a fake
connection. So they run — and kill mutants — on every machine, extension or
not. Nothing here is ``skipif``-gated.
"""
from __future__ import annotations

import json
import sqlite3
import struct
from typing import ClassVar

import pytest

from boost_cli.core import dense, embed, rag

# --------------------------------------------------------------- toy doubles

def _toy_embed(texts, input_type=None, timeout=60):
    """A deterministic 3-D embedder; values are irrelevant to these tests."""
    return [[float(len(t) % 3), 1.0, 0.0] for t in texts]


class _FakeVec:
    """Stands in for the sqlite_vec module without the C extension."""

    @staticmethod
    def serialize_float32(vec):
        return b"".join(struct.pack("<f", x) for x in vec)

    @staticmethod
    def load(con):            # never actually called (we patch _connect)
        pass


class _Cur(list):
    """A list that also quacks like a sqlite cursor (``.fetchall()``)."""

    def fetchall(self):
        return list(self)

    def fetchone(self):
        return self[0] if self else None


class _FakeCon:
    """A connection whose ``execute`` returns canned rows keyed off the SQL.

    Enough for :func:`dense.retrieve`, which issues exactly two reads: the KNN
    ``... WHERE embedding MATCH ...`` and the ``... WHERE id IN (...)`` lookup.
    """

    def __init__(self, knn, chunks):
        self._knn = knn
        self._chunks = chunks
        self.closed = False

    def execute(self, sql, params=()):
        if "MATCH" in sql:
            return _Cur(self._knn)
        if "ROW_NUMBER" in sql:
            # `_expand` maps ranked vector ids to the chunk rows naming them.
            # This store predates the `vectors` relation, so `_vid_col` reads
            # `id` and the map is the identity — including for a vector whose
            # chunk row is gone, which is what
            # `test_knn_row_without_a_chunk_row_is_skipped` needs to reach
            # `retrieve`'s own guard.
            return _Cur([(rid, rid) for rid, _d in self._knn])
        if "id IN" in sql:
            return _Cur(self._chunks)
        return _Cur([])

    def close(self):
        self.closed = True


def _e(name, body, tap="acme/skills", kind="skill"):
    return {"name": name, "tap": tap, "kind": kind,
            "skill_md": "skills/%s/SKILL.md" % name,
            "_body": body}


_ENTRIES = [_e("jest", "react testing"), _e("pytest", "python testing")]


# ------------------------------------------------------- backend absent path

class TestBackendAbsent:
    """With ``_load() -> None`` every entry point degrades, writing nothing."""

    @pytest.fixture(autouse=True)
    def _no_backend(self, monkeypatch):
        monkeypatch.setattr(dense, "_load", lambda: None)

    def test_have_backend_false(self):
        assert dense.have_backend() is False

    def test_connect_returns_none(self, sandbox):
        assert dense._connect() is None

    def test_build_returns_none_and_writes_nothing(self, sandbox):
        assert dense.build(entries=_ENTRIES) is None
        assert not dense.db_path().exists()

    def test_ready_false(self, sandbox):
        assert dense.ready() is False

    def test_retrieve_returns_none(self, sandbox):
        assert dense.retrieve("react", entries=_ENTRIES) is None


class TestEmbeddingsAbsent:
    """Backend present but no embeddings provider -> same graceful None/False."""

    @pytest.fixture(autouse=True)
    def _have_backend_no_embed(self, monkeypatch):
        monkeypatch.setattr(dense, "have_backend", lambda: True)
        monkeypatch.setattr(embed, "available", lambda: False)

    def test_build_none(self, sandbox):
        assert dense.build(entries=_ENTRIES) is None

    def test_ready_false(self, sandbox):
        assert dense.ready() is False


# ------------------------------------------------------------- ready() guards

class TestReadyGuards:
    """Each early-out branch of ready() with a plain (extension-free) con."""

    def _seed(self, meta, rows=1, with_chunks=True):
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
        for k, v in meta.items():
            con.execute("INSERT INTO meta VALUES (?, ?)", (k, json.dumps(v)))
        if with_chunks:
            con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, tap TEXT)")
            for _i in range(rows):
                con.execute("INSERT INTO chunks (tap) VALUES ('t')")
        con.commit()
        return con

    @pytest.fixture()
    def wired(self, sandbox, tmp_path, monkeypatch):
        dbfile = tmp_path / "vec.sqlite"
        dbfile.write_bytes(b"")               # db_path().exists() -> True
        monkeypatch.setattr(dense, "have_backend", lambda: True)
        monkeypatch.setattr(dense, "db_path", lambda: dbfile)
        monkeypatch.setattr(embed, "available", lambda: True)
        monkeypatch.setattr(embed, "provider", lambda: "openai")
        monkeypatch.setattr(embed, "model", lambda: "toy-8")
        monkeypatch.setattr(embed, "dimension", lambda: 8)
        return monkeypatch

    def _use(self, monkeypatch, con):
        monkeypatch.setattr(dense, "_connect", lambda: con)

    _GOOD: ClassVar[dict] = {"version": dense.INDEX_VERSION,
                             "provider": "openai", "model": "toy-8", "dim": 8}

    def test_true_when_everything_matches(self, wired):
        self._use(wired, self._seed(self._GOOD, rows=1))
        assert dense.ready() is True

    def test_false_when_db_missing(self, wired, tmp_path):
        wired.setattr(dense, "db_path", lambda: tmp_path / "absent.sqlite")
        assert dense.ready() is False

    def test_false_when_connect_none(self, wired):
        self._use(wired, None)
        assert dense.ready() is False

    def test_false_on_version_mismatch(self, wired):
        self._use(wired, self._seed({**self._GOOD, "version": 999}))
        assert dense.ready() is False

    def test_false_on_provider_mismatch(self, wired):
        self._use(wired, self._seed({**self._GOOD, "provider": "voyage"}))
        assert dense.ready() is False

    def test_false_on_dim_mismatch(self, wired):
        self._use(wired, self._seed({**self._GOOD, "dim": 99}))
        assert dense.ready() is False

    def test_false_on_model_mismatch(self, wired):
        # provider and dim still match — only the model moved (voyage-3 ->
        # voyage-4 is this exact case, both 1024-d under provider "voyage")
        self._use(wired, self._seed({**self._GOOD, "model": "toy-4"}))
        assert dense.ready() is False

    def test_false_when_model_absent_from_meta(self, wired):
        meta = {k: v for k, v in self._GOOD.items() if k != "model"}
        self._use(wired, self._seed(meta))
        assert dense.ready() is False

    def test_false_when_chunks_table_missing(self, wired):
        self._use(wired, self._seed(self._GOOD, with_chunks=False))
        assert dense.ready() is False

    def test_false_on_empty_index(self, wired):
        self._use(wired, self._seed(self._GOOD, rows=0))
        assert dense.ready() is False

    def test_true_with_single_row(self, wired):
        # kills a `rows > 1` boundary mutant without the extension
        self._use(wired, self._seed(self._GOOD, rows=1))
        assert dense.ready() is True


# ------------------------------------------------------- SQL helper internals

class TestMetaRoundtrip:
    def _con(self):
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
        return con

    def test_write_then_read_roundtrips_json(self):
        con = self._con()
        payload = {"version": 1, "commits": {"a": "c1"}, "provider": "openai"}
        dense._write_meta(con, payload)
        assert dense._read_meta(con) == payload

    def test_read_meta_empty_when_no_table(self):
        assert dense._read_meta(sqlite3.connect(":memory:")) == {}

    def test_read_meta_falls_back_to_raw_on_bad_json(self):
        con = self._con()
        con.execute("INSERT INTO meta VALUES ('k', 'not-json')")
        assert dense._read_meta(con) == {"k": "not-json"}

    def test_write_meta_is_upsert(self):
        con = self._con()
        dense._write_meta(con, {"dim": 8})
        dense._write_meta(con, {"dim": 7})       # INSERT OR REPLACE
        assert dense._read_meta(con) == {"dim": 7}


class TestWipeAndDelete:
    def _schema(self):
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, tap TEXT)")
        con.execute("CREATE TABLE vec_chunks (rowid INTEGER PRIMARY KEY, e BLOB)")
        return con

    def _tables(self, con):
        return {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}

    def test_wipe_drops_both_stores(self):
        con = self._schema()
        con.execute("CREATE TABLE meta (k TEXT, v TEXT)")
        dense._wipe(con)
        tbls = self._tables(con)
        assert "chunks" not in tbls and "vec_chunks" not in tbls
        assert "meta" in tbls                    # _wipe leaves meta alone

    def test_delete_taps_removes_only_named_tap_from_both(self):
        con = self._schema()
        con.execute("INSERT INTO chunks (id, tap) VALUES (1, 'keep')")
        con.execute("INSERT INTO chunks (id, tap) VALUES (2, 'drop')")
        con.execute("INSERT INTO chunks (id, tap) VALUES (3, 'drop')")
        for i in (1, 2, 3):
            con.execute("INSERT INTO vec_chunks (rowid, e) VALUES (?, ?)",
                        (i, b"x"))
        dense._delete_taps(con, ["drop"])
        assert [r[0] for r in con.execute("SELECT id FROM chunks")] == [1]
        assert [r[0] for r in con.execute("SELECT rowid FROM vec_chunks")] == [1]

    def test_delete_taps_empty_list_is_a_noop(self):
        con = self._schema()
        con.execute("INSERT INTO chunks (id, tap) VALUES (1, 'keep')")
        dense._delete_taps(con, [])
        assert [r[0] for r in con.execute("SELECT id FROM chunks")] == [1]


class TestChunkTexts:
    def test_splits_a_long_body_into_multiple_chunks(self, monkeypatch):
        body = ("react " * 400) + "\n\n" + ("python " * 400)
        monkeypatch.setattr(dense, "read_body", lambda e, tp=None: body)
        out = dense._chunk_texts(_e("x", ""), None)
        assert len(out) >= 2
        assert out == rag.chunk(body)

    def test_empty_body_falls_back_to_single_body_chunk(self, monkeypatch):
        monkeypatch.setattr(dense, "read_body", lambda e, tp=None: "")
        assert dense._chunk_texts(_e("x", ""), None) == [""]


# --------------------------------------------------- retrieve() ranking logic

class TestRetrieveRanking:
    """The per-entry-max cosine reducer, driven by a fake connection.

    Distances come back canned; retrieve turns them into ``1 - dist`` scores,
    keeps the best chunk per (name, tap), drops rows absent from the live set,
    honours ``kind``, sorts by score then name, and caps at ``k``.
    """

    @pytest.fixture()
    def wired(self, monkeypatch):
        monkeypatch.setattr(dense, "ready", lambda: True)
        monkeypatch.setattr(dense, "_load", lambda: _FakeVec)
        monkeypatch.setattr(embed, "embed", _toy_embed)
        return monkeypatch

    def _con(self, wired, knn, chunks):
        con = _FakeCon(knn, chunks)
        wired.setattr(dense, "_connect", lambda: con)
        return con

    def test_ranks_by_similarity_and_drops_non_live_rows(self, wired):
        self._con(
            wired,
            knn=[(1, 0.0), (2, 0.5), (3, 0.9)],
            chunks=[(1, "acme/skills", "skills/jest/SKILL.md", "skill", "s1"),
                    (2, "acme/skills", "skills/pytest/SKILL.md", "skill", "s2"),
                    (3, "gone/tap", "skills/ghost/SKILL.md", "skill", "s3")])
        hits = dense.retrieve("q", entries=_ENTRIES)
        assert [h["entry"]["name"] for h in hits] == ["jest", "pytest"]
        assert hits[0]["score"] == pytest.approx(1.0)
        assert hits[1]["score"] == pytest.approx(0.5)
        assert set(hits[0].keys()) == {"entry", "score", "snippet"}
        assert hits[0]["snippet"] == "s1"

    def test_keeps_max_score_across_chunks_of_one_entry(self, wired):
        self._con(
            wired,
            knn=[(1, 0.9), (2, 0.1)],            # same entry, two chunks
            chunks=[(1, "acme/skills", "skills/jest/SKILL.md", "skill", "low"),
                    (2, "acme/skills", "skills/jest/SKILL.md", "skill", "high")])
        hits = dense.retrieve("q", entries=[_ENTRIES[0]])
        assert len(hits) == 1
        assert hits[0]["score"] == pytest.approx(0.9)   # 1 - 0.1, the max
        assert hits[0]["snippet"] == "high"

    def test_kind_filter_excludes_other_kinds(self, wired):
        self._con(
            wired,
            knn=[(1, 0.0), (2, 0.0)],
            chunks=[(1, "acme/skills", "skills/jest/SKILL.md", "skill", "s1"),
                    (2, "acme/skills", "skills/pyrule/SKILL.md", "rule", "s2")])
        entries = [_e("jest", ""), _e("pyrule", "", kind="rule")]
        hits = dense.retrieve("q", kind="skill", entries=entries)
        assert [h["entry"]["name"] for h in hits] == ["jest"]

    def test_k_caps_result_count(self, wired):
        self._con(
            wired,
            knn=[(1, 0.0), (2, 0.5)],
            chunks=[(1, "acme/skills", "skills/jest/SKILL.md", "skill", "s1"),
                    (2, "acme/skills", "skills/pytest/SKILL.md", "skill", "s2")])
        assert len(dense.retrieve("q", k=1, entries=_ENTRIES)) == 1

    def test_empty_knn_returns_empty_list(self, wired):
        self._con(wired, knn=[], chunks=[])
        assert dense.retrieve("q", entries=_ENTRIES) == []

    def test_knn_row_without_a_chunk_row_is_skipped(self, wired):
        # a vector rowid whose chunks row is gone -> meta is None -> skipped
        self._con(
            wired,
            knn=[(1, 0.0), (99, 0.5)],
            chunks=[(1, "acme/skills", "skills/jest/SKILL.md", "skill", "s1")])
        hits = dense.retrieve("q", entries=_ENTRIES)
        assert [h["entry"]["name"] for h in hits] == ["jest"]

    def test_none_when_not_ready(self, monkeypatch):
        monkeypatch.setattr(dense, "ready", lambda: False)
        assert dense.retrieve("q", entries=_ENTRIES) is None

    def test_none_when_query_embed_fails(self, wired):
        wired.setattr(embed, "embed", lambda *a, **k: None)
        assert dense.retrieve("q", entries=_ENTRIES) is None

    def test_none_when_connect_fails(self, wired):
        wired.setattr(dense, "_connect", lambda: None)
        assert dense.retrieve("q", entries=_ENTRIES) is None


# ------------------------------------------------- build() on a plain sqlite

class TestBuildWithoutExtension:
    """build()/_embed_and_store against plain tables (no vec0 virtual table).

    ``_ensure_schema`` is swapped for a plain-table version so the whole
    embed-and-store pipeline — reuse detection, per-tap delete, stats — runs
    and is mutation-checked without the sqlite-vec extension.
    """

    @pytest.fixture()
    def store(self, sandbox, tmp_path, monkeypatch):
        dbfile = tmp_path / "vec.sqlite"

        def _plain_schema(con, dim):
            # Stands in for `_ensure_schema` only to avoid the vec0 virtual
            # table, which needs the extension. The `chunks` shape must stay
            # identical to the real one — `TestTheStandInSchemaMatchesTheReal`
            # fails if it drifts, which is how this fixture silently claimed to
            # be the current version while building the previous one.
            con.execute(
                "CREATE TABLE IF NOT EXISTS chunks (id INTEGER PRIMARY KEY"
                " AUTOINCREMENT, name TEXT, tap TEXT, path TEXT, kind TEXT,"
                " cix INTEGER, snip TEXT, digest TEXT, vid INTEGER)")
            con.execute(
                "CREATE INDEX IF NOT EXISTS chunks_tap ON chunks(tap)")
            con.execute(
                "CREATE INDEX IF NOT EXISTS chunks_entry ON chunks(tap, path)")
            con.execute(
                "CREATE INDEX IF NOT EXISTS chunks_vid ON chunks(vid)")
            con.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY,"
                        " v TEXT)")
            con.execute("CREATE TABLE IF NOT EXISTS vectors (vid INTEGER"
                        " PRIMARY KEY AUTOINCREMENT, hash BLOB)")
            con.execute("CREATE UNIQUE INDEX IF NOT EXISTS vectors_hash ON"
                        " vectors(hash)")
            con.execute("CREATE TABLE IF NOT EXISTS vec_chunks (rowid INTEGER"
                        " PRIMARY KEY, embedding BLOB)")

        monkeypatch.setattr(dense, "_load", lambda: _FakeVec)
        monkeypatch.setattr(dense, "_connect",
                            lambda: sqlite3.connect(str(dbfile)))
        monkeypatch.setattr(dense, "_ensure_schema", _plain_schema)
        monkeypatch.setattr(dense, "db_path", lambda: dbfile)
        monkeypatch.setattr(dense, "have_backend", lambda: True)
        monkeypatch.setattr(dense, "read_body",
                            lambda e, tp=None: e["name"] + " " + e["_body"])
        monkeypatch.setattr(embed, "available", lambda: True)
        monkeypatch.setattr(embed, "provider", lambda: "openai")
        monkeypatch.setattr(embed, "model", lambda: "toy-8")
        monkeypatch.setattr(embed, "dimension", lambda: 8)
        monkeypatch.setattr(embed, "embed", _toy_embed)
        monkeypatch.setattr(rag, "_tap_paths", lambda: {"acme/skills": "/x"})
        monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c1"})
        return monkeypatch

    def test_build_stats_and_stored_rows(self, store):
        stats = dense.build(entries=_ENTRIES, force=True)
        assert stats["entries"] == 2
        assert stats["chunks"] == 2
        assert stats["added"] == 2
        assert stats["provider"] == "openai"
        assert stats["model"] == "toy-8"
        assert stats["reindexed"] == ["acme/skills"]
        assert stats["reused"] == []
        con = sqlite3.connect(str(dense.db_path()))
        # One vector row per DISTINCT embedding, not per chunk copy. This
        # module's toy embedder keys on `len(text) % 3`, and both entries land
        # on the same vector — so two chunks share one stored blob, which is
        # the saving. What must still hold is that both chunks resolve.
        assert con.execute("SELECT COUNT(*) FROM vec_chunks").fetchone()[0] == 1
        assert con.execute(
            "SELECT COUNT(*) FROM chunks c JOIN vec_chunks v ON v.rowid = c.vid"
        ).fetchone()[0] == 2

    def test_unchanged_tap_is_reused_not_reembedded(self, store):
        first = dense.build(entries=_ENTRIES, force=True)
        second = dense.build(entries=_ENTRIES)             # same commit c1
        assert second["reused"] == ["acme__skills"]
        assert second["reindexed"] == []
        assert second["added"] == 0
        assert second["chunks"] == first["chunks"]

    def test_commit_change_reindexes(self, store):
        dense.build(entries=_ENTRIES, force=True)
        store.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c2"})
        stats = dense.build(entries=_ENTRIES)
        assert stats["reused"] == []
        assert stats["reindexed"] == ["acme/skills"]
        assert stats["added"] == 2
        assert stats["chunks"] == 2                        # replaced, not dupe

    def test_an_untapped_tap_is_pruned_from_the_index(self, store):
        # THE GHOST-VECTOR BUG. `boost untap` removes a tap's entries, so it
        # can never appear in `fresh` — the incremental path only ever deleted
        # taps that CHANGED, and everything from a removed tap survived every
        # later build, crowding the KNN pool that retrieve() then filters back
        # out for not being live.
        both = [*_ENTRIES, _e("gone", "from the other tap", tap="old/skills")]
        store.setattr(rag, "_tap_commits",
                      lambda: {"acme__skills": "c1", "old__skills": "c1"})
        dense.build(entries=both, force=True)
        con = sqlite3.connect(str(dense.db_path()))
        assert con.execute("SELECT COUNT(*) FROM chunks WHERE tap = 'old/skills'"
                           ).fetchone()[0] == 1
        con.close()

        # …the tap is removed: gone from the entry set and from the commit map.
        store.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c1"})
        stats = dense.build(entries=_ENTRIES)

        assert stats["pruned"] == ["old/skills"]
        assert stats["reused"] == ["acme__skills"], "the surviving tap is untouched"
        con = sqlite3.connect(str(dense.db_path()))
        assert con.execute("SELECT COUNT(*) FROM chunks WHERE tap = 'old/skills'"
                           ).fetchone()[0] == 0
        # The surviving tap's two chunks share one vector (see
        # `test_build_stats_and_stored_rows`), and the removed tap's own vector
        # is gone — dropped by the refcounted sweep, not by having been the
        # only referent of a row that was deleted wholesale.
        assert con.execute("SELECT COUNT(*) FROM vec_chunks").fetchone()[0] == 1
        assert con.execute(
            "SELECT COUNT(*) FROM chunks c WHERE NOT EXISTS "
            "(SELECT 1 FROM vec_chunks v WHERE v.rowid = c.vid)"
        ).fetchone()[0] == 0
        con.close()

    def test_nothing_is_pruned_when_every_tap_is_still_present(self, store):
        dense.build(entries=_ENTRIES, force=True)
        assert dense.build(entries=_ENTRIES)["pruned"] == []

    def test_indexed_taps_is_empty_before_any_schema_exists(self, tmp_path):
        # _indexed_taps runs against whatever connection build() has; on a
        # database with no chunks table the answer is "nothing indexed", not a
        # crash that takes the whole build down.
        con = sqlite3.connect(str(tmp_path / "empty.sqlite"))
        assert dense._indexed_taps(con) == set()
        con.close()

    def test_provider_switch_wipes_and_rebuilds(self, store):
        dense.build(entries=_ENTRIES, force=True)
        store.setattr(embed, "provider", lambda: "voyage")
        stats = dense.build(entries=_ENTRIES)              # no force needed
        assert stats["reused"] == []
        assert stats["provider"] == "voyage"

    def test_model_switch_wipes_and_rebuilds(self, store):
        # provider and dim unchanged, only the model moved — the voyage-3 ->
        # voyage-4 case. Without the model term in `same_backend` the unchanged
        # tap commit would reuse vectors from the old embedding space.
        dense.build(entries=_ENTRIES, force=True)
        store.setattr(embed, "model", lambda: "toy-4")
        stats = dense.build(entries=_ENTRIES)              # no force needed
        assert stats["reused"] == []
        assert stats["model"] == "toy-4"
        assert stats["added"] == 2
        assert stats["chunks"] == 2                        # wiped, not appended

    def test_batch_count_mismatch_drops_that_batch(self, store):
        store.setattr(embed, "embed", lambda texts, **k: [[1.0, 2.0, 3.0]])
        stats = dense.build(entries=_ENTRIES, force=True)
        assert stats["added"] == 0
        assert stats["chunks"] == 0

    def test_failed_batch_is_reported_not_swallowed(self, store):
        store.setattr(embed, "embed", lambda texts, **k: None)   # provider 429s
        stats = dense.build(entries=_ENTRIES, force=True)
        assert stats["added"] == 0
        assert stats["failed"] == ["acme/skills"]

    def test_failed_tap_commit_is_not_recorded(self, store):
        # A rate-limited run must not mark the tap "built at c1" — otherwise the
        # next non-forced run reuses it and the store stays empty forever.
        store.setattr(embed, "embed", lambda texts, **k: None)
        dense.build(entries=_ENTRIES, force=True)
        con = sqlite3.connect(str(dense.db_path()))
        meta = dense._read_meta(con)
        con.close()
        assert meta["commits"] == {}

    def test_rerun_after_failure_retries_instead_of_reusing(self, store):
        store.setattr(embed, "embed", lambda texts, **k: None)
        dense.build(entries=_ENTRIES, force=True)         # fails, stores nothing
        store.setattr(embed, "embed", _toy_embed)         # provider recovers
        stats = dense.build(entries=_ENTRIES)             # no --force needed
        assert stats["reused"] == []
        assert stats["failed"] == []
        assert stats["added"] == 2
        assert stats["chunks"] == 2

    def test_successful_tap_commit_is_recorded(self, store):
        dense.build(entries=_ENTRIES, force=True)
        con = sqlite3.connect(str(dense.db_path()))
        meta = dense._read_meta(con)
        con.close()
        assert meta["commits"] == {"acme__skills": "c1"}

    def test_empty_entries_builds_nothing(self, store):
        stats = dense.build(entries=[], force=True)
        assert stats["chunks"] == 0
        assert stats["added"] == 0

    def test_build_none_when_dimension_unknown(self, store):
        # provider present but the model's dimension can't be resolved
        store.setattr(embed, "dimension", lambda: None)
        assert dense.build(entries=_ENTRIES, force=True) is None
