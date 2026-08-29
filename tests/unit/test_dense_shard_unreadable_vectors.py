# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: exporting a shard must not report "no vectors" when there are.

``vec_chunks`` is a **vec0 virtual table**. A plain :mod:`sqlite3` connection has
no such module, so any statement touching it raises
``OperationalError: no such module: vec0`` — and :func:`dense.export_shard` used
to catch ``sqlite3.Error`` and return ``{"chunks": []}``, which the command layer
turns into::

    no vectors for 'anthropics/skills'
    hint: build them first with `boost reindex --dense`

The hint names the step that had *just* run. Every scheduled ``shards`` run has
died there — 2026-08-02 and 2026-08-09, 20 of 20 registries, "tap and embed"
green and "export the shard" red — so the prebuilt-shard feature has never once
produced an artifact.

The existing suite could not see it. ``test_dense_shards._store`` builds
``vec_chunks`` with ``CREATE TABLE`` — an ordinary table a plain connection reads
happily — and its ``with_backend`` fixture patches ``_connect`` to a plain
connection. Both are reasonable shortcuts for tests about *validation*, and
together they mean no test in that file exercises the schema production actually
writes. This file covers the gap from the other side, without needing the
extension installed: from a plain connection's point of view a vec0 table is
precisely "a relation I cannot read", which is what is simulated here.

The distinction being pinned is between two states the old code collapsed:

* the tap genuinely has no rows — empty shard, and "run reindex" is right;
* the rows are there and cannot be read — a different problem with a different
  fix, and answering it with "run reindex" sends the reader back round a loop
  they have already completed.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from boost_cli.core import dense, paths
from boost_cli.errors import BoostError


def _store_with_unreadable_vectors(rows=(("a", "acme/skills"),), dim=3):
    """``chunks`` populated, ``vec_chunks`` absent.

    Stands in for the real store as a plain connection sees it: the ordinary
    tables read fine and the vector relation does not resolve. Whether that is
    ``no such module: vec0`` (production) or ``no such table`` (here) is the
    same ``sqlite3.OperationalError`` reaching the same handler.
    """
    paths.ensure_dirs()
    con = sqlite3.connect(str(dense.db_path()))
    try:
        con.execute("CREATE TABLE IF NOT EXISTS chunks ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, tap TEXT,"
                    " path TEXT, kind TEXT, cix INTEGER, snip TEXT)")
        con.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
        for name, tap in rows:
            con.execute(
                "INSERT INTO chunks (name, tap, path, kind, cix, snip) "
                "VALUES (?, ?, ?, ?, 0, ?)",
                (name, tap, "%s/SKILL.md" % name, "skill", "snip"))
        meta = {"version": dense.INDEX_VERSION, "provider": "local",
                "model": "bge", "dim": dim, "commits": {"acme__skills": "c1"}}
        con.executemany("INSERT OR REPLACE INTO meta (k, v) VALUES (?, ?)",
                        [(k, json.dumps(v)) for k, v in meta.items()])
        con.commit()
    finally:
        con.close()


class TestUnreadableVectorsAreReportedNotSwallowed:
    def test_export_raises_instead_of_returning_an_empty_shard(self, sandbox):
        _store_with_unreadable_vectors()
        with pytest.raises(BoostError):
            dense.export_shard("acme/skills")

    def test_the_message_does_not_tell_the_user_to_reindex(self, sandbox):
        # THE WHOLE POINT. `reindex --dense` is what produced these rows; being
        # sent back to it is what made the CI failure unreadable for two runs.
        _store_with_unreadable_vectors()
        with pytest.raises(BoostError) as caught:
            dense.export_shard("acme/skills")
        advice = "%s %s" % (caught.value, getattr(caught.value, "hint", "") or "")
        assert "reindex" not in advice.lower(), advice

    def test_the_message_names_the_vector_backend(self, sandbox):
        # The actual fix is the sqlite-vec extension, so the text has to point
        # there — a bare "cannot read" would leave the reader nowhere.
        _store_with_unreadable_vectors()
        with pytest.raises(BoostError) as caught:
            dense.export_shard("acme/skills")
        advice = ("%s %s" % (caught.value,
                             getattr(caught.value, "hint", "") or "")).lower()
        assert "sqlite-vec" in advice or "rag" in advice, advice


class TestTheGenuinelyEmptyCasesStillDegrade:
    """Only the unreadable case became an error. The rest must not regress."""

    def test_no_store_at_all_is_still_an_empty_shard(self, sandbox):
        assert dense.export_shard("acme/skills")["chunks"] == []

    def test_a_tap_with_no_rows_is_still_an_empty_shard(self, sandbox):
        # `chunks` is readable and simply has nothing for this tap. Here
        # "build them first" IS the right advice, so this must not raise.
        _store_with_unreadable_vectors(rows=(("a", "acme/skills"),))
        assert dense.export_shard("nobody/nothing")["chunks"] == []
