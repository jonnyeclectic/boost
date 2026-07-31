"""Per-registry vector shards: export one tap's vectors, import them elsewhere.

Measured on this machine: embedding 743 entries (3,740 chunks) with the shipped
ONNX `bge-small-en-v1.5` on CPU took **4,431 s — 74 minutes**, ~1.2 s/chunk.
Extrapolated to a full catalogue that is days, not the "hour-plus" the roadmap
estimated. So shipping prebuilt shards is a requirement for the keyless tier
rather than an optimisation: without them, a keyless user's semantic search is
theoretically available and practically unreachable.

A shard is one tap's rows plus the provenance needed to decide whether they are
still valid — the embedding backend that produced them and the registry commit
they were built from. Those checks are the whole safety story, so they are what
these tests are mostly about:

* vectors from a different provider/model/dimension must never be mixed into a
  store, because a cosine comparison across two embedding spaces is meaningless
  and would silently degrade every result rather than failing;
* a shard built from a different commit than the tap currently at HEAD is stale
  and must be refused, since `build()` would otherwise mark that tap "reused"
  and never re-embed it.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from boost_cli.core import dense, paths


def _store(provider="local", model="bge", dim=3, rows=(("a", "acme/skills"),),
           commits=None):
    """A hand-built store, so these tests never need the sqlite-vec extension."""
    paths.ensure_dirs()
    con = sqlite3.connect(str(dense.db_path()))
    try:
        con.execute("CREATE TABLE IF NOT EXISTS chunks ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, tap TEXT,"
                    " path TEXT, kind TEXT, cix INTEGER, snip TEXT)")
        con.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
        con.execute("CREATE TABLE IF NOT EXISTS vec_chunks ("
                    "rowid INTEGER PRIMARY KEY, embedding BLOB)")
        for name, tap in rows:
            cur = con.execute(
                "INSERT INTO chunks (name, tap, path, kind, cix, snip) "
                "VALUES (?, ?, ?, ?, 0, ?)",
                (name, tap, "%s/SKILL.md" % name, "skill", "snip of %s" % name))
            con.execute("INSERT INTO vec_chunks (rowid, embedding) VALUES (?, ?)",
                        (cur.lastrowid, b"\x00" * (4 * dim)))
        meta = {"version": dense.INDEX_VERSION, "provider": provider,
                "model": model, "dim": dim,
                "commits": commits if commits is not None else {"acme__skills": "c1"}}
        con.executemany("INSERT OR REPLACE INTO meta (k, v) VALUES (?, ?)",
                        [(k, json.dumps(v)) for k, v in meta.items()])
        con.commit()
    finally:
        con.close()


class TestExport:
    def test_a_shard_carries_only_the_named_tap(self, sandbox, with_backend):
        _store(rows=(("a", "acme/skills"), ("b", "other/repo")))
        shard = dense.export_shard("acme/skills")
        assert {r["tap"] for r in shard["chunks"]} == {"acme/skills"}

    def test_a_shard_records_the_backend_that_made_it(self, sandbox):
        _store(provider="voyage", model="voyage-4", dim=3)
        shard = dense.export_shard("acme/skills")
        assert shard["provider"] == "voyage"
        assert shard["model"] == "voyage-4"
        assert shard["dim"] == 3

    def test_a_shard_records_the_commit_it_was_built_from(self, sandbox):
        _store(commits={"acme__skills": "deadbeef"})
        assert dense.export_shard("acme/skills")["commit"] == "deadbeef"

    def test_vectors_survive_the_round_trip_as_bytes(self, sandbox):
        _store(dim=3)
        chunk = dense.export_shard("acme/skills")["chunks"][0]
        assert isinstance(chunk["embedding"], str)   # base64, JSON-safe
        assert chunk["snip"] == "snip of a"

    def test_an_untapped_name_exports_nothing(self, sandbox):
        _store()
        assert dense.export_shard("nobody/nothing")["chunks"] == []


@pytest.fixture()
def with_backend(monkeypatch):
    """Pretend the vec0 extension is loadable.

    Import writes vectors, so it needs the extension for real — but these tests
    are about the *validation* that happens before any write, and CI has no
    extension. Without this they fail with "no vector backend available"
    instead of exercising the check they are named for, which is how they
    passed locally and reddened three macOS legs plus the canary.
    """
    class _FakeVec:
        """Enough of sqlite_vec for the paths under test.

        `serialize_float32` is real: tests that WRITE vectors reach it, and a
        bare object() stub only survived while every test stopped at validation.
        """

        @staticmethod
        def serialize_float32(vec):
            import struct
            return struct.pack("%df" % len(vec), *vec)

    monkeypatch.setattr(dense, "_load", lambda: _FakeVec)
    monkeypatch.setattr(dense, "_connect",
                        lambda: sqlite3.connect(str(dense.db_path())))


class TestImportRefusesMismatchedVectors:
    """The failure that must never happen quietly."""

    def test_a_different_provider_is_refused(self, sandbox, with_backend):
        _store(provider="local", model="bge", dim=3)
        shard = {"tap": "x/y", "provider": "voyage", "model": "voyage-4",
                 "dim": 3, "commit": "c1", "chunks": []}
        ok, reason = dense.import_shard(shard, commit="c1")
        assert ok is False and "provider" in reason

    def test_a_different_model_is_refused(self, sandbox, with_backend):
        _store(provider="local", model="bge", dim=3)
        shard = {"tap": "x/y", "provider": "local", "model": "other-model",
                 "dim": 3, "commit": "c1", "chunks": []}
        ok, reason = dense.import_shard(shard, commit="c1")
        assert ok is False and "model" in reason

    def test_a_different_dimension_is_refused(self, sandbox, with_backend):
        # Would corrupt the vec0 table outright, not merely rank badly.
        _store(dim=3)
        shard = {"tap": "x/y", "provider": "local", "model": "bge",
                 "dim": 384, "commit": "c1", "chunks": []}
        ok, reason = dense.import_shard(shard, commit="c1")
        assert ok is False and "dim" in reason

    def test_a_stale_commit_is_refused(self, sandbox, with_backend):
        # Accepting it would mark the tap "reused" and it would never re-embed.
        _store()
        shard = {"tap": "x/y", "provider": "local", "model": "bge", "dim": 3,
                 "commit": "old", "chunks": []}
        ok, reason = dense.import_shard(shard, commit="new")
        assert ok is False and "commit" in reason

    def test_a_matching_shard_is_accepted(self, sandbox, with_backend):
        _store()
        shard = {"tap": "x/y", "provider": "local", "model": "bge", "dim": 3,
                 "commit": "c1", "chunks": []}
        ok, reason = dense.import_shard(shard, commit="c1")
        assert ok is True, reason


class TestImportIntoAnEmptyStore:
    """The case that matters most: a user who has never embedded anything."""

    def test_it_adopts_the_shard_backend_when_there_is_no_store(self, sandbox):
        # Not stubbed: with no store at all, import has to CREATE the vec0
        # virtual table, which only the real extension can do. Skipping where
        # it is absent is honest — faking it here would assert nothing about
        # the path that actually runs.
        con = dense._connect()
        if con is None:
            # NOT have_backend(): that only checks the import succeeds. On
            # macOS runners sqlite_vec imports and then fails to LOAD, so
            # have_backend() is True while _connect() is None — which is the
            # condition that actually decides whether this can run.
            pytest.skip("sqlite-vec extension not loadable here")
        con.close()
        shard = {"tap": "x/y", "provider": "local", "model": "bge", "dim": 3,
                 "commit": "c1", "chunks": []}
        ok, reason = dense.import_shard(shard, commit="c1")
        assert ok is True, reason

    def test_imported_rows_are_queryable_and_credited_to_their_tap(self, sandbox, with_backend):
        _store(rows=(("a", "acme/skills"),))
        shard = dense.export_shard("acme/skills")
        shard["tap"] = "mirror/repo"
        for c in shard["chunks"]:
            c["tap"] = "mirror/repo"
        ok, _ = dense.import_shard(shard, commit="c1")
        assert ok
        con = sqlite3.connect(str(dense.db_path()))
        try:
            n = con.execute("SELECT COUNT(*) FROM chunks WHERE tap = ?",
                            ("mirror/repo",)).fetchone()[0]
        finally:
            con.close()
        assert n == 1

    def test_reimporting_replaces_rather_than_duplicates(self, sandbox, with_backend):
        _store(rows=(("a", "acme/skills"),))
        shard = dense.export_shard("acme/skills")
        dense.import_shard(shard, commit="c1")
        dense.import_shard(shard, commit="c1")
        con = sqlite3.connect(str(dense.db_path()))
        try:
            n = con.execute("SELECT COUNT(*) FROM chunks WHERE tap = ?",
                            ("acme/skills",)).fetchone()[0]
        finally:
            con.close()
        assert n == 1, "a second import duplicated the tap's rows"


class TestRoundTrip:
    def test_export_then_import_preserves_the_vector_bytes(self, sandbox, with_backend):
        _store(dim=3)
        shard = dense.export_shard("acme/skills")
        before = shard["chunks"][0]["embedding"]
        dense.import_shard(shard, commit="c1")
        after = dense.export_shard("acme/skills")["chunks"][0]["embedding"]
        assert after == before

    def test_a_shard_is_json_serialisable(self, sandbox, with_backend):
        # It has to survive being published as a release artifact.
        _store()
        json.dumps(dense.export_shard("acme/skills"))


class TestWorksWithoutTheExtension:
    """Export must not require sqlite-vec — CI and most users don't have it.

    `export_shard` reads `chunks`, `meta` and the stored blobs, all ordinary
    tables, so routing it through `_connect` (which loads the extension and
    returns None without it) made every field vanish on a runner. That is how
    this shipped broken the first time: it passed locally, where the extra is
    installed, and failed six CI jobs. `_recorded_meta` documents the same trap.
    """

    def test_export_still_returns_rows_with_no_extension(self, sandbox,
                                                         monkeypatch):
        _store(rows=(("a", "acme/skills"),))
        monkeypatch.setattr(dense, "_load", lambda: None)
        assert dense._connect() is None          # precondition: no extension
        shard = dense.export_shard("acme/skills")
        assert len(shard["chunks"]) == 1
        assert shard["provider"] == "local"
        assert shard["commit"] == "c1"

    def test_export_of_a_missing_store_is_empty_not_an_error(self, sandbox):
        # No store on disk at all: a shard request must degrade, not raise.
        assert dense.export_shard("acme/skills")["chunks"] == []

    def test_import_still_needs_the_extension(self, sandbox, monkeypatch):
        # The asymmetry is deliberate: writing vectors needs the vec0 virtual
        # table, so import cannot degrade the way export can.
        monkeypatch.setattr(dense, "_load", lambda: None)
        shard = {"tap": "x/y", "provider": "local", "model": "bge", "dim": 3,
                 "commit": "c1", "chunks": []}
        ok, reason = dense.import_shard(shard, commit="c1")
        assert ok is False and "backend" in reason


class TestDeltaTopUp:
    """An imported shard must make `build` skip that tap and embed only the rest.

    This is step 3 of the keyless epic — "when a tap runs ahead of its published
    shard, or is a registry CI has never seen, embed just those files on the
    spot". It works because `import_shard` records the tap's commit in the same
    `meta.commits` map that `build` consults, so a shard is indistinguishable
    from locally-built vectors as far as reuse is concerned.

    That coupling is easy to break silently: an import that forgot to record the
    commit would still produce a working store, and the only symptom would be
    re-embedding the shard's chunks on the next build — minutes of wasted CPU
    that nothing reports. Hence a test.
    """

    def _tap_seen(self, monkeypatch, commits):
        from boost_cli.core import rag
        monkeypatch.setattr(rag, "_tap_commits", lambda: commits)
        monkeypatch.setattr(rag, "_tap_paths", lambda: {})

    def test_an_imported_shard_is_reused_not_re_embedded(self, sandbox,
                                                         with_backend,
                                                         monkeypatch):
        from boost_cli.core import embed
        _store(rows=(("a", "acme/skills"),))
        embedded = []
        monkeypatch.setattr(embed, "embed",
                            lambda texts, **kw: embedded.extend(texts) or
                            [[0.1, 0.2, 0.3] for _ in texts])
        monkeypatch.setattr(embed, "available", lambda: True)
        monkeypatch.setattr(embed, "dimension", lambda: 3)
        monkeypatch.setattr(embed, "provider", lambda: "local")
        monkeypatch.setattr(embed, "model", lambda: "bge")
        self._tap_seen(monkeypatch, {"acme__skills": "c1"})
        entries = [{"name": "a", "tap": "acme/skills", "kind": "skill",
                    "skill_md": "a/SKILL.md", "_body": "text", "description": ""}]
        stats = dense.build(entries=entries, force=False)
        assert stats is not None
        assert "acme__skills" in stats["reused"]
        assert embedded == [], "re-embedded a tap the shard already covered"

    def test_a_tap_the_shard_does_not_cover_is_still_embedded(self, sandbox,
                                                              with_backend,
                                                              monkeypatch):
        # The other half: shards cover the popular registries, the local model
        # makes the long tail self-serve. If this regressed, an uncatalogued
        # registry would be a dead end for a keyless user.
        from boost_cli.core import embed
        _store(rows=(("a", "acme/skills"),))
        monkeypatch.setattr(embed, "embed",
                            lambda texts, **kw: [[0.1, 0.2, 0.3] for _ in texts])
        monkeypatch.setattr(embed, "available", lambda: True)
        monkeypatch.setattr(embed, "dimension", lambda: 3)
        monkeypatch.setattr(embed, "provider", lambda: "local")
        monkeypatch.setattr(embed, "model", lambda: "bge")
        self._tap_seen(monkeypatch, {"acme__skills": "c1", "new__repo": "z9"})
        entries = [{"name": "b", "tap": "new/repo", "kind": "skill",
                    "skill_md": "b/SKILL.md", "_body": "text", "description": ""}]
        stats = dense.build(entries=entries, force=False)
        assert stats is not None
        assert "new/repo" in stats["reindexed"]
