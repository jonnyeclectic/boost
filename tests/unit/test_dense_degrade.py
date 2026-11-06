# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A vector store boost cannot use degrades to BM25 with one accurate hint.

Four shapes reached exit 70, wrong advice, or a destroyed store:

* a ``rag_vectors.sqlite`` SQLite rejects ("file is not a database") crashed
  `boost search` and the `reindex --dense --force` meant to repair it, while
  doctor called it "not configured";
* a plain `reindex --dense` silently wiped a store built in another
  embedding space, the re-embed `fix_hint` reserves for ``--force``;
* a Python whose sqlite3 cannot load extensions was told to install the
  extra it already had, and left a 0-byte store doctor called "an older
  build";
* a failed shard fetch always said `boost reindex --dense` "embeds locally",
  which is a dead end without the extra and a paid API call with a key.

No real extension, model or network: ``sqlite_vec`` is a stub class.
"""
import sqlite3

import pytest

from boost_cli.core import dense, embed, shards

# Captured at import, before `sandbox` can stand in for it on a Python whose
# sqlite3 cannot load extensions.
_extension_error = dense.extension_error
_loads = pytest.mark.skipif(
    not hasattr(sqlite3.Connection, "enable_load_extension"),
    reason="this Python's sqlite3 cannot load extensions")

_GARBAGE = bytes(range(256)) * 12          # 3,072 bytes no SQLite will open


class _NoopVec:
    """A ``sqlite_vec`` whose ``load`` succeeds and adds nothing."""

    @staticmethod
    def load(con):
        return None


class _DeniedVec:
    """A ``sqlite_vec`` whose ``load`` is refused, as by a locked-down sqlite3."""

    @staticmethod
    def load(con):
        raise sqlite3.OperationalError("not authorized")


@pytest.fixture()
def keyed(sandbox, monkeypatch):
    """The extra imports, and an OpenAI key is in force (never called)."""
    monkeypatch.setattr(dense, "_load", lambda: _NoopVec)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    return sandbox


def _corrupt_store():
    p = dense.db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(_GARBAGE)
    return p


def _built_store(**meta):
    """A plain-sqlite store holding one chunk, with ``meta`` recorded."""
    p = dense.db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p))
    con.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
    con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, tap TEXT)")
    con.execute("INSERT INTO chunks (tap) VALUES ('acme/skills')")
    dense._write_meta(con, meta)
    con.commit()
    con.close()
    return p


class TestCorruptStore:
    def test_unreadable_is_true_only_for_a_rejected_file(self, sandbox):
        assert dense.unreadable() is False                 # no file
        p = dense.db_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"")
        assert dense.unreadable() is False                 # empty is not corrupt
        p.write_bytes(_GARBAGE)
        assert dense.unreadable() is True
        p.unlink()
        _built_store(version=dense.INDEX_VERSION)
        assert dense.unreadable() is False

    def test_a_locked_store_is_busy_not_corrupt(self, sandbox, monkeypatch):
        # Another boost mid-VACUUM holds an exclusive lock for minutes. That
        # raises "database is locked" — an OperationalError, which is also a
        # DatabaseError — and reading it as corrupt would point the user at
        # the `--force` that deletes a healthy store.
        p = _built_store(version=dense.INDEX_VERSION)
        real = sqlite3.connect
        holder = real(str(p), isolation_level=None)
        try:
            holder.execute("BEGIN EXCLUSIVE")
            monkeypatch.setattr(sqlite3, "connect",
                                lambda db, *a, **k: real(db, timeout=0))
            assert dense.unreadable() is False
            assert dense._recorded_meta().get("_corrupt") is None
        finally:
            holder.execute("ROLLBACK")
            holder.close()
        assert p.exists()

    def test_status_names_it_and_it_is_a_fault(self, keyed):
        _corrupt_store()
        st = dense.status(count=True)
        assert st["reason"] == "corrupt"
        assert st["corrupt"] is True
        assert st["store_exists"] is True
        assert st["degraded"] is True
        assert st["ready"] is False
        assert st["chunks"] is None

    @pytest.mark.parametrize("vec", [None, _DeniedVec])
    def test_it_outranks_a_missing_backend(self, sandbox, monkeypatch, vec):
        # Below those rungs, a corrupt file read as a degraded store with no
        # chunk count, which doctor's "%d-chunk" line could not format.
        monkeypatch.setattr(dense, "_load", lambda: vec)
        _corrupt_store()
        st = dense.status(count=True)
        assert (st["reason"], st["degraded"]) == ("corrupt", True)

    def test_kill_switch_still_outranks_it(self, keyed, monkeypatch):
        monkeypatch.setenv("BOOST_NO_EMBED", "1")
        _corrupt_store()
        st = dense.status()
        assert (st["reason"], st["degraded"]) == ("disabled", False)

    def test_fix_hint_offers_the_force_rebuild(self, keyed):
        _corrupt_store()
        st = dense.status()
        assert dense.fix_hint(st["reason"], st) == (
            "rebuild it: `boost reindex --dense --force` replaces the "
            "unreadable store and re-embeds every entry")

    def test_ready_is_false_not_a_crash(self, keyed):
        _corrupt_store()
        assert dense.ready() is False

    def test_ready_survives_a_database_error_past_the_meta_read(
            self, keyed, monkeypatch):
        _corrupt_store()

        def boom(con):
            raise sqlite3.DatabaseError("file is not a database")
        monkeypatch.setattr(dense, "_ready_on", boom)
        assert dense.ready() is False

    def test_read_meta_returns_empty_for_a_rejected_file(self, keyed):
        p = _corrupt_store()
        con = sqlite3.connect(str(p))
        try:
            assert dense._read_meta(con) == {}
            assert dense._indexed_taps(con) == set()
        finally:
            con.close()

    def test_offline_migrations_skip_it(self, keyed):
        p = _corrupt_store()
        assert dense.quantize() is None
        assert dense.deduplicate() is None
        assert p.read_bytes() == _GARBAGE

    def test_plain_build_refuses_and_keeps_the_file(self, keyed):
        p = _corrupt_store()
        assert dense.build(entries=[]) == {"refused": "corrupt"}
        assert p.read_bytes() == _GARBAGE

    def test_forced_build_replaces_the_file(self, keyed, monkeypatch):
        p = _corrupt_store()
        journal = p.with_name(p.name + "-journal")
        journal.write_bytes(b"x")
        seen = {}

        def connect():
            # The build is past the guard: record what it would open.
            seen["exists"] = p.exists()
            seen["journal"] = journal.exists()
        monkeypatch.setattr(dense, "_connect", connect)
        assert dense.build(entries=[], force=True) is None
        assert seen == {"exists": False, "journal": False}

    def test_refusal_text_names_the_file_and_the_flag(self, keyed):
        p = _corrupt_store()
        msg, hint = dense.refusal_text({"refused": "corrupt"})
        assert msg == ("dense index not rebuilt — %s is not a readable SQLite "
                       "database, and only `--force` replaces it"
                       % p.as_posix())
        assert hint == dense.fix_hint("corrupt")


class TestOtherSpaceStoreIsKept:
    """A plain build refuses a store in another space; ``--force`` replaces it."""

    def test_refusal_names_the_restore_and_the_force_cost(self, sandbox,
                                                          monkeypatch):
        monkeypatch.setattr(dense, "_load", lambda: _NoopVec)
        monkeypatch.setattr(embed, "provider", lambda: "local")
        _built_store(version=dense.INDEX_VERSION, provider="voyage",
                     model="voyage-4", dim=1024, chunks=1000)
        refused = {"refused": "provider-changed", "chunks": 1000,
                   "built_provider": "voyage", "built_model": "voyage-4",
                   "built_dim": 1024, "provider": "local",
                   "model": embed.LOCAL_MODEL, "dim": 384}
        msg, hint = dense.refusal_text(refused)
        assert msg == (
            "dense index not rebuilt — the store holds 1,000 vectors built "
            "with voyage voyage-4 (1024-d) and this machine embeds with local "
            "%s (384-d); only `--force` replaces them, re-embedding every "
            "entry locally" % embed.LOCAL_MODEL)
        assert hint == ("set the key it was built with: `export "
                        "VOYAGE_API_KEY=...` — or `boost reindex --dense "
                        "--force` re-embeds all 1,000 vectors in local's space")

    def test_refusal_text_prices_a_paid_rebuild(self, keyed):
        _built_store(version=dense.INDEX_VERSION, provider="openai",
                     model="old", dim=1536, chunks=1)
        msg, _ = dense.refusal_text(
            {"refused": "model-changed", "chunks": 1,
             "built_provider": "openai", "built_model": "old",
             "built_dim": 1536, "provider": "openai",
             "model": "new", "dim": 1536})
        assert "holds 1 vector built with openai old" in msg
        assert msg.endswith("re-embedding every entry through openai's paid API")

    def test_refusal_text_without_a_count(self, keyed):
        msg, _ = dense.refusal_text({"refused": "dim-changed", "chunks": None,
                                     "provider": "voyage"})
        assert "the store holds vectors built with" in msg
        assert msg.endswith("through voyage's paid API")

    def test_dim_change_alone_is_named(self, sandbox, monkeypatch):
        monkeypatch.setattr(dense, "_load", lambda: _NoopVec)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        _built_store(version=dense.INDEX_VERSION, provider="openai",
                     model=embed.model(), dim=7, chunks=1)
        monkeypatch.setattr(dense, "_connect",
                            lambda: sqlite3.connect(str(dense.db_path())))
        monkeypatch.setattr(dense.catalog, "all_entries", lambda: [])
        got = dense.build()
        assert got["refused"] == "dim-changed"
        assert got["built_dim"] == 7
        assert got["dim"] == embed.dimension()

    def test_an_empty_other_space_store_is_rebuilt(self, sandbox, monkeypatch):
        # Nothing to lose: no chunks, so the wipe is allowed without --force.
        monkeypatch.setattr(dense, "_load", lambda: _NoopVec)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        p = dense.db_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(p))
        con.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
        con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, tap TEXT)")
        dense._write_meta(con, {"version": dense.INDEX_VERSION,
                                "provider": "voyage", "model": "voyage-4",
                                "dim": 1024})
        con.commit()
        con.close()
        wiped = []
        monkeypatch.setattr(dense, "_connect",
                            lambda: sqlite3.connect(str(p)))
        monkeypatch.setattr(dense, "_wipe", lambda c: wiped.append(True))

        def stop(con, dim):
            raise RuntimeError("past the wipe")
        monkeypatch.setattr(dense, "_ensure_schema", stop)
        monkeypatch.setattr(dense.catalog, "all_entries", lambda: [])
        with pytest.raises(RuntimeError, match="past the wipe"):
            dense.build()
        assert wiped == [True]


class TestExtensionCannotLoad:
    @_loads
    def test_extension_error_reports_the_refusal(self, sandbox, monkeypatch):
        monkeypatch.setattr(dense, "_load", lambda: _DeniedVec)
        assert _extension_error() == "not authorized"

    @_loads
    def test_extension_error_is_none_when_it_loads(self, sandbox, monkeypatch):
        monkeypatch.setattr(dense, "_load", lambda: _NoopVec)
        assert _extension_error() is None

    def test_extension_error_is_none_without_a_backend(self, sandbox,
                                                       monkeypatch):
        monkeypatch.setattr(dense, "_load", lambda: None)
        assert _extension_error() is None

    def test_extension_error_ignores_a_module_without_load(self, sandbox,
                                                          monkeypatch):
        monkeypatch.setattr(dense, "_load", lambda: object())
        assert _extension_error() is None

    def test_a_sqlite3_without_extension_loading_is_named(self, sandbox,
                                                         monkeypatch):
        class _NoExt:
            def close(self):
                pass
        monkeypatch.setattr(dense, "_load", lambda: _NoopVec)
        monkeypatch.setattr(dense.sqlite3, "connect", lambda *a, **k: _NoExt())
        assert _extension_error() == (
            "this Python's sqlite3 was built without extension loading")

    @_loads
    def test_status_reason_and_hint(self, keyed, monkeypatch):
        monkeypatch.setattr(dense, "_load", lambda: _DeniedVec)
        monkeypatch.setattr(dense, "extension_error", _extension_error)
        st = dense.status()
        assert st["reason"] == "no-extension-load"
        assert st["extension_error"] == "not authorized"
        assert st["degraded"] is False                    # nothing built yet
        assert dense.fix_hint(st["reason"], st) == (
            "this Python's sqlite3 cannot load extensions, which sqlite-vec "
            "needs — reinstall boost under a Python built with loadable "
            "SQLite extensions, then `boost reindex --dense`")

    @_loads
    def test_it_outranks_a_missing_key(self, sandbox, monkeypatch):
        monkeypatch.setattr(dense, "_load", lambda: _DeniedVec)
        monkeypatch.setattr(dense, "extension_error", _extension_error)
        monkeypatch.setattr(embed, "provider", lambda: None)
        assert dense.status()["reason"] == "no-extension-load"

    def test_connect_leaves_no_empty_store(self, keyed, monkeypatch):
        monkeypatch.setattr(dense, "_load", lambda: _DeniedVec)
        assert dense._connect() is None
        assert not dense.db_path().exists()

    def test_connect_removes_an_empty_store_it_finds(self, keyed, monkeypatch):
        monkeypatch.setattr(dense, "_load", lambda: _DeniedVec)
        p = dense.db_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"")
        assert dense._connect() is None
        assert not p.exists()

    def test_connect_keeps_a_real_store(self, keyed, monkeypatch):
        monkeypatch.setattr(dense, "_load", lambda: _DeniedVec)
        p = _built_store(version=dense.INDEX_VERSION)
        before = p.read_bytes()
        assert dense._connect() is None
        assert p.read_bytes() == before


class TestEmptyFileIsNoStore:
    def test_a_zero_byte_file_is_not_a_degraded_build(self, keyed):
        p = dense.db_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"")
        st = dense.status(count=True)
        assert st["store_exists"] is False
        assert st["degraded"] is False
        assert st["reason"] == "no-store"

    def test_without_the_extra_too(self, sandbox, monkeypatch):
        monkeypatch.setattr(dense, "_load", lambda: None)
        p = dense.db_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"")
        st = dense.status(count=True)
        assert (st["reason"], st["store_exists"], st["degraded"]) == (
            "no-backend", False, False)

    def test_chunks_without_meta_still_count_as_a_store(self, keyed):
        p = dense.db_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(p))
        con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, tap TEXT)")
        con.execute("INSERT INTO chunks (tap) VALUES ('a')")
        con.commit()
        con.close()
        st = dense.status()
        assert st["store_exists"] is True
        assert st["reason"] == "version-changed"


class TestTransportHint:
    """The shard-fetch failure hint reads the same status doctor reads."""

    def test_without_the_extra_it_names_the_install(self, sandbox,
                                                    monkeypatch):
        monkeypatch.setattr(dense, "_load", lambda: None)
        assert shards.transport_hint() == (
            "shards are optional — to embed on this machine instead, "
            "install the extra: `%s`" % dense.install_extra())

    def test_kill_switch(self, sandbox, monkeypatch):
        monkeypatch.setenv("BOOST_NO_EMBED", "1")
        assert shards.transport_hint() == (
            "shards are optional — to embed on this machine instead, "
            "unset the kill switch: `unset BOOST_NO_EMBED`")

    def test_extension_cannot_load(self, keyed, monkeypatch):
        monkeypatch.setattr(dense, "_load", lambda: _DeniedVec)
        monkeypatch.setattr(dense, "extension_error", _extension_error)
        assert shards.transport_hint().startswith(
            "shards are optional — to embed on this machine instead, "
            "this Python's sqlite3 cannot load extensions")

    def test_a_key_is_named_with_its_cost(self, sandbox, monkeypatch):
        monkeypatch.setattr(dense, "_load", lambda: _NoopVec)
        monkeypatch.setenv("VOYAGE_API_KEY", "pa-test")
        assert shards.transport_hint() == (
            "shards are optional — `boost reindex --dense` embeds them "
            "through voyage's paid API instead")

    def test_local(self, sandbox, monkeypatch):
        monkeypatch.setattr(dense, "_load", lambda: _NoopVec)
        monkeypatch.setattr(embed, "provider", lambda: "local")
        assert shards.transport_hint() == (
            "shards are optional — `boost reindex --dense` embeds them "
            "locally instead")

    def test_a_corrupt_store_names_force_not_the_plain_build(self, keyed):
        _corrupt_store()
        assert shards.transport_hint() == (
            "shards are optional — rebuild it: `boost reindex --dense "
            "--force` replaces the unreadable store and re-embeds every entry")

    def test_an_other_space_store_names_its_restore(self, sandbox,
                                                     monkeypatch):
        monkeypatch.setattr(dense, "_load", lambda: _NoopVec)
        monkeypatch.setattr(embed, "provider", lambda: "local")
        _built_store(version=dense.INDEX_VERSION, provider="voyage",
                     model="voyage-4", dim=1024, chunks=5)
        assert shards.transport_hint() == (
            "shards are optional — set the key it was built with: `export "
            "VOYAGE_API_KEY=...` — or `boost reindex --dense --force` "
            "re-embeds all 5 vectors in local's space")

    def test_a_failed_fetch_carries_it(self, sandbox, monkeypatch, tmp_path):
        monkeypatch.setattr(dense, "_load", lambda: None)
        missing = (tmp_path / "nope" / "manifest.json").as_uri()
        with pytest.raises(shards.BoostError) as err:
            shards.fetch_manifest(missing)
        assert err.value.hint == shards.transport_hint()
        assert err.value.hint.startswith(shards.TRANSPORT_LEAD)
