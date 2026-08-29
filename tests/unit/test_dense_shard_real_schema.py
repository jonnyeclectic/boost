# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests: export a shard from the schema production actually writes.

Every other shard test builds its fixture by hand, and every one of them makes
``vec_chunks`` an **ordinary** table. That is a fair shortcut for tests about
validation, and it is also why the shard feature could ship broken twice: the
real :func:`dense._ensure_schema` writes

    CREATE VIRTUAL TABLE vec_chunks USING vec0(embedding float[N] ...)

and a virtual table is exactly the thing a hand-rolled ``CREATE TABLE`` fixture
cannot stand in for. Against the fixture a plain connection reads the join
happily; against the real store it raises ``no such module: vec0``.

So this file refuses to hand-build anything. It creates the store through
``dense._connect`` and ``dense._ensure_schema`` — the production path — and then
asks for a shard. It is the only test here that would have failed before the
fix, and the only one that will fail if the storage layer moves again.

It **skips without ``sqlite-vec``**, which is the honest cost of testing the real
schema and the reason it is not the whole defence:
``test_dense_shard_unreadable_vectors.py`` pins the same contract with no extra
installed, so a runner that skips this file is still not blind. Do not "fix" the
skip by faking the extension — a fake vec0 is the fixture that hid the bug.
"""
from __future__ import annotations

import json

import pytest

from boost_cli.core import dense, paths

sqlite_vec = pytest.importorskip(
    "sqlite_vec",
    reason="the real vec0 schema needs the [rag] extra; the contract is also "
           "pinned extension-free in test_dense_shard_unreadable_vectors.py")


def _extension_loadable() -> bool:
    """True when this interpreter can actually create a vec0 table.

    Importing ``sqlite_vec`` is NOT enough, and assuming it was reddened all
    three macOS legs of PR #503 with ``sqlite-vec imported but _connect returned
    None``. Loading an extension needs
    ``sqlite3.Connection.enable_load_extension``, which CPython only exposes
    when its bundled SQLite was built with extension support — macOS builds
    routinely are not. So the package imports, ``dense._load()`` returns it, and
    ``dense._connect()`` still returns ``None``.

    Probe the capability rather than a proxy for it: build the thing these tests
    need and see whether it works. Exactly the mistake this file exists to
    correct, one level up — a fixture that stood in for the real schema is what
    hid the bug, and an import that stood in for the real capability is what
    broke the fix.
    """
    import sqlite3
    con = sqlite3.connect(":memory:")
    try:
        con.enable_load_extension(True)
        sqlite_vec.load(con)
        con.execute("CREATE VIRTUAL TABLE t USING vec0(embedding float[2])")
        return True
    except (AttributeError, sqlite3.Error):
        return False
    finally:
        con.close()


pytestmark = pytest.mark.skipif(
    not _extension_loadable(),
    reason="this interpreter cannot load sqlite extensions (macOS CPython is "
           "commonly built without support), so the real vec0 schema is "
           "unreachable — the extension-free half of the contract still runs "
           "in test_dense_shard_unreadable_vectors.py")

DIM = 4


def _production_store(tap: str = "acme/skills", rows: int = 2):
    """A store built the way `dense.build` builds one — vec0 and all."""
    paths.ensure_dirs()
    con = dense._connect()
    # The module-level skipif already proved the extension loads here, so a
    # None now is a real regression in _connect rather than a missing extra.
    assert con is not None, \
        "_connect returned None although vec0 loads on this interpreter"
    try:
        dense._ensure_schema(con, DIM)
        for i in range(rows):
            cur = con.execute(
                "INSERT INTO chunks (name, tap, path, kind, cix, snip) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("skill-%d" % i, tap, "skill-%d/SKILL.md" % i, "skill", 0,
                 "snippet %d" % i))
            con.execute(
                "INSERT INTO vec_chunks (rowid, embedding) VALUES (?, ?)",
                (cur.lastrowid,
                 sqlite_vec.serialize_float32([0.1 * (i + 1)] * DIM)))
        meta = {"version": dense.INDEX_VERSION, "provider": "local",
                "model": "bge-small-en-v1.5", "dim": DIM,
                "commits": {tap.replace("/", "__"): "c0ffee"}}
        con.executemany("INSERT OR REPLACE INTO meta (k, v) VALUES (?, ?)",
                        [(k, json.dumps(v)) for k, v in meta.items()])
        con.commit()
    finally:
        con.close()


class TestExportAgainstTheRealSchema:
    """The regression. Before the fix every assertion here failed."""

    def test_a_shard_carries_the_rows(self, sandbox):
        _production_store(rows=2)
        assert len(dense.export_shard("acme/skills")["chunks"]) == 2

    def test_a_shard_carries_its_provenance(self, sandbox):
        # shards.yml asserts on exactly these four before it uploads, so an
        # export that returns rows without them still fails the workflow.
        _production_store()
        shard = dense.export_shard("acme/skills")
        for field in ("provider", "model", "dim", "commit"):
            assert shard.get(field), "%s missing from %r" % (field, shard)

    def test_the_embeddings_survive_the_round_trip(self, sandbox):
        import base64
        _production_store(rows=1)
        blob = dense.export_shard("acme/skills")["chunks"][0]["embedding"]
        assert len(base64.b64decode(blob)) == 4 * DIM

    def test_the_shard_is_json_serialisable(self, sandbox):
        # It is written to a file by `reindex --export-shard` and uploaded.
        _production_store()
        json.dumps(dense.export_shard("acme/skills"))

    def test_a_tap_with_no_rows_is_empty_not_an_error(self, sandbox):
        # Same degradation as everywhere else, now confirmed on the real
        # schema rather than inferred from the stand-in.
        _production_store()
        assert dense.export_shard("nobody/nothing")["chunks"] == []


class TestExportedShardImportsBack:
    """End-to-end on the real schema: what CI publishes, a user can consume."""

    def test_a_real_shard_is_accepted_by_import(self, sandbox):
        _production_store(rows=2)
        shard = dense.export_shard("acme/skills")
        ok, reason = dense.import_shard(shard, commit="c0ffee")
        assert ok, reason

    def test_the_imported_rows_come_back_out_again(self, sandbox):
        _production_store(rows=2)
        shard = dense.export_shard("acme/skills")
        dense.import_shard(shard, commit="c0ffee")
        assert len(dense.export_shard("acme/skills")["chunks"]) == 2
