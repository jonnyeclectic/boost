# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`search`, `doctor` and `reindex --dense` on a vector store boost cannot use.

Each used to end in exit 70 or in advice that could not work. They now give
the one answer `dense.fix_hint` gives, in-process, with a stub ``sqlite_vec``
and a key that is never called.
"""
import sqlite3

import pytest

from boost_cli.core import dense, embed

_GARBAGE = bytes(range(256)) * 12

#: The real probe, taken before the sandbox stubs it out on a Python whose
#: sqlite3 cannot load extensions at all (the macOS runners).
_extension_error = dense.extension_error

_loads = pytest.mark.skipif(
    not hasattr(sqlite3.Connection, "enable_load_extension"),
    reason="this Python's sqlite3 cannot load extensions")


def _flat(text: str) -> str:
    return " ".join(text.split())


class _NoopVec:
    @staticmethod
    def load(con):
        return None


class _DeniedVec:
    @staticmethod
    def load(con):
        raise sqlite3.OperationalError("not authorized")


@pytest.fixture()
def keyed(boost, tapped, monkeypatch):
    monkeypatch.setattr(dense, "_load", lambda: _NoopVec)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    # A real embed call would be a network request; none may happen here.
    monkeypatch.setattr(embed, "embed", lambda *a, **k: pytest.fail("embedded"))
    return boost


@pytest.fixture()
def corrupt(keyed):
    p = dense.db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(_GARBAGE)
    return p


_CORRUPT_FIX = ("rebuild it: `boost reindex --dense --force` replaces the "
                "unreadable store and re-embeds every entry")


class TestCorruptStore:
    def test_search_falls_back_to_bm25_with_one_hint(self, keyed, corrupt):
        r = keyed("search", "brainstorm")
        out = _flat(r.out)
        assert "brainstorming" in out
        assert out.count("semantic search is off — %s" % _CORRUPT_FIX) == 1

    def test_doctor_reports_it_and_fails(self, keyed, corrupt):
        r = keyed("doctor", expect=1)
        assert ("semantic search silently off — %s is not a readable SQLite "
                "database; searches are using BM25 — %s"
                % (corrupt.as_posix(), _CORRUPT_FIX)) in _flat(r.out)
        assert "not configured" not in r.out

    def test_plain_reindex_refuses_and_keeps_the_file(self, keyed, corrupt):
        r = keyed("reindex", "--dense")
        out = _flat(r.out)
        assert ("dense index not rebuilt — %s is not a readable SQLite "
                "database, and only `--force` replaces it"
                % corrupt.as_posix()) in out
        assert "hint: %s" % _CORRUPT_FIX in out
        assert corrupt.read_bytes() == _GARBAGE

    def test_json_carries_the_refusal(self, keyed, corrupt):
        import json
        r = keyed("reindex", "--dense", "--json")
        assert json.loads(r.out)["dense"] == {"refused": "corrupt"}


class TestOtherSpaceStore:
    @_loads
    def test_plain_reindex_keeps_paid_vectors(self, keyed, monkeypatch):
        p = dense.db_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(p))
        con.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
        con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, tap TEXT)")
        con.execute("INSERT INTO chunks (tap) VALUES ('acme/skills')")
        dense._write_meta(con, {"version": dense.INDEX_VERSION,
                                "provider": "voyage", "model": "voyage-4",
                                "dim": 1024, "chunks": 1000})
        con.commit()
        con.close()
        before = p.read_bytes()
        # The stub cannot create vec0 tables, which the offline dedupe pass
        # asks for before it finds nothing to do; the refusal comes earlier.
        monkeypatch.setattr(dense, "_ensure_schema", lambda con, dim: None)
        r = keyed("reindex", "--dense")
        out = _flat(r.out)
        assert ("dense index not rebuilt — the store holds 1,000 vectors "
                "built with voyage voyage-4 (1024-d) and this machine embeds "
                "with openai") in out
        assert "only `--force` replaces them" in out
        assert "through openai's paid API" in out
        assert "`export VOYAGE_API_KEY=...`" in out
        assert p.read_bytes() == before


class TestExtensionCannotLoad:
    def test_reindex_names_the_real_cause_and_leaves_no_file(
            self, keyed, monkeypatch):
        monkeypatch.setattr(dense, "_load", lambda: _DeniedVec)
        monkeypatch.setattr(dense, "extension_error", _extension_error)
        r = keyed("reindex", "--dense")
        out = _flat(r.out)
        assert ("dense index skipped — this Python's sqlite3 cannot load "
                "extensions, which sqlite-vec needs") in out
        assert "[rag]` extra" not in out
        assert not dense.db_path().exists()
        # And with no store left behind, doctor is not red.
        keyed("doctor")


class TestEmptyFile:
    def test_doctor_stays_green_on_a_zero_byte_file(self, boost, tapped,
                                                    monkeypatch):
        monkeypatch.setattr(dense, "_load", lambda: None)
        p = dense.db_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"")
        r = boost("doctor")
        assert "older build" not in r.out


def test_doctor_names_a_corrupt_store_without_the_extra(boost, tapped,
                                                        monkeypatch):
    monkeypatch.setattr(dense, "_load", lambda: None)
    p = dense.db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(_GARBAGE)
    r = boost("doctor", expect=1)
    assert ("%s is not a readable SQLite database; searches are using BM25"
            % p.as_posix()) in _flat(r.out)
