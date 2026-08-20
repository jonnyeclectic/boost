"""`dense.status()` must not read the vector store to answer a search.

Every `boost search` that BM25 answers alone ends in `_hint_semantic_search`,
which calls `dense.status()` to decide whether to print one muted line. That
line cost a `SELECT COUNT(*) FROM chunks` over the whole store.

Measured on a real 445-tap install: the `chunks` table's covering index is
34.5 MB across 8,419 pages inside a 3.4 GB file, and counting it walked every
one of them — 1.94 s with the pages warm in the OS cache, and the dominant term
in a 33.9 s cold search (`boost.log`, versus 2.5 s warm for the same query).
Roughly 79% of a warm search, spent to decide the wording of a hint.

Nothing about that count is needed to answer the question the hot path asks.
`status()` needs to know whether the store has *any* rows (the `empty` reason);
only one `fix_hint` branch wants the number itself, and a store built after
this change records it in `meta`, which is 9 pages.

So these tests pin the cost, not just the answer: the default path may read
`meta` and probe for existence, and may not count. A future refactor that
reintroduces the scan keeps every value identical and fails here.
"""
import json
import sqlite3

import pytest

from boost_cli.core import dense, paths


def _write_store(provider="voyage", model="voyage-4", dim=1024,
                 version=dense.INDEX_VERSION, chunks=3, taps=("acme__skills",),
                 record_count=False):
    """A store carrying `meta` + `chunks`, no vec0 — so no extra required.

    `record_count` writes the `chunks` meta key that `dense.build()` now
    stamps. Off by default so the fixture keeps modelling a *legacy* store,
    which is the case that has to stay fast without it.
    """
    paths.ensure_dirs()
    con = sqlite3.connect(str(dense.db_path()))
    try:
        con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    " name TEXT, tap TEXT, kind TEXT, cix INTEGER, snip TEXT)")
        con.execute("CREATE INDEX chunks_tap ON chunks(tap)")
        con.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
        meta = {"version": version, "provider": provider, "model": model,
                "dim": dim, "commits": dict.fromkeys(taps, "c0ffee")}
        if record_count:
            meta["chunks"] = chunks
        con.executemany("INSERT INTO meta (k, v) VALUES (?, ?)",
                        [(k, json.dumps(v)) for k, v in meta.items()])
        for i in range(chunks):
            con.execute("INSERT INTO chunks (name, tap, kind, cix, snip)"
                        " VALUES (?, ?, ?, ?, ?)",
                        ("skill-%d" % i, taps[0].replace("__", "/"),
                         "skill", 0, "snip"))
        con.commit()
    finally:
        con.close()


@pytest.fixture(autouse=True)
def backend(monkeypatch):
    """Make the sqlite-vec backend *look* present, as test_dense_status does.

    `status()` reports the first missing link, so without this every reason
    collapses to "no-backend" and the store is never opened at all — which
    would make these tests pass for the wrong reason.
    """
    monkeypatch.setattr(dense, "_load", lambda: object())


@pytest.fixture
def keyed(monkeypatch):
    monkeypatch.setenv("VOYAGE_API_KEY", "vk-test")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("BOOST_NO_EMBED", raising=False)


@pytest.fixture
def sql_log(monkeypatch):
    """Every statement dense runs against the store, in order.

    Installed by wrapping `sqlite3.connect` *as dense imports it*, because
    `_recorded_meta` opens its own connection and there is no seam to pass a
    tracer through. `set_trace_callback` fires per executed statement, which is
    what makes "did it count?" answerable without timing anything.
    """
    seen: list[str] = []
    real = sqlite3.connect

    def traced(*a, **kw):
        con = real(*a, **kw)
        con.set_trace_callback(seen.append)
        return con

    monkeypatch.setattr(dense.sqlite3, "connect", traced)
    return seen


def _counted(sql_log) -> list[str]:
    """The statements that walk the whole `chunks` table."""
    return [s for s in sql_log
            if "count(*)" in s.lower() and "chunks" in s.lower()
            and "where" not in s.lower()]


# --------------------------------------------------------------- the hot path

def test_status_does_not_count_chunks(sandbox, keyed, sql_log):
    """The default `status()` must never issue an unfiltered COUNT over chunks.

    This is the regression that made a cold `boost search` take 34 s. The
    assertion is on the SQL rather than on elapsed time so it holds on a fast
    runner with a three-row fixture, where the scan is free and the bug is
    invisible to a stopwatch.
    """
    _write_store(chunks=3)
    dense.status()
    assert _counted(sql_log) == [], (
        "status() counted the chunks table on the search hot path: %r"
        % _counted(sql_log))


def test_status_still_sees_a_populated_store(sandbox, keyed, sql_log):
    """Cheap must not mean wrong: a store with rows is still `ready`."""
    _write_store(chunks=3)
    st = dense.status()
    assert st["reason"] is None
    assert st["ready"] is True
    assert st["store_exists"] is True
    assert _counted(sql_log) == []


def test_empty_store_still_reports_empty(sandbox, keyed, sql_log):
    """The one thing the count was load-bearing for, without the count.

    A store whose `meta` survived but whose rows did not is a real state — a
    build that failed after writing meta — and it must still be named `empty`
    rather than passed off as ready.
    """
    _write_store(chunks=0)
    st = dense.status()
    assert st["reason"] == "empty"
    assert st["ready"] is False
    assert st["degraded"] is True
    assert _counted(sql_log) == []


def test_recorded_count_is_used_when_present(sandbox, keyed, sql_log):
    """A store built after this change carries its own count in `meta`."""
    _write_store(chunks=7, record_count=True)
    st = dense.status()
    assert st["chunks"] == 7
    assert st["chunks_exact"] is True
    assert _counted(sql_log) == []


def test_legacy_store_reports_unknown_rather_than_scanning(sandbox, keyed,
                                                           sql_log):
    """A store built before `meta.chunks` existed must not be scanned for it.

    Reporting the number as unknown is the honest trade: it is one cosmetic
    figure in one hint, it self-heals on the next `boost reindex --dense`, and
    the alternative is 34.5 MB of page reads on every search forever.
    """
    _write_store(chunks=5)
    st = dense.status()
    assert st["chunks"] is None
    assert st["chunks_exact"] is False
    assert st["reason"] is None          # unknown count, but demonstrably non-empty
    assert _counted(sql_log) == []


# ------------------------------------------------------- the exact path

def test_exact_count_is_available_on_request(sandbox, keyed, sql_log):
    """`boost doctor` may pay for the scan — it is a health check, not a search."""
    _write_store(chunks=5)
    st = dense.status(count=True)
    assert st["chunks"] == 5
    assert st["chunks_exact"] is True
    assert _counted(sql_log), "count=True should have issued the COUNT"


def test_exact_count_prefers_recorded_value(sandbox, keyed, sql_log):
    """Even `count=True` need not scan when the store recorded its own total."""
    _write_store(chunks=7, record_count=True)
    st = dense.status(count=True)
    assert st["chunks"] == 7
    assert _counted(sql_log) == []


# ------------------------------------------------------------- fix_hint

def test_fix_hint_keeps_the_number_when_it_is_known():
    """The existing wording is unchanged for any caller that has a count."""
    st = {"built_provider": "voyage", "chunks": 750416, "chunks_exact": True}
    hint = dense.fix_hint("no-key", st)
    assert "750,416" in hint
    assert "VOYAGE_API_KEY" in hint


def test_fix_hint_drops_the_number_when_it_is_unknown():
    """Unknown must read as unknown — never as zero, and never as a guess.

    `chunks: None` used to be impossible, so the `status.get("chunks")` guard
    would now route a legacy store to "reinstall the extra" — the exact advice
    whose docstring says it forces a full re-embed of vectors the user paid
    for. The count being unknown is not evidence that there are no vectors.
    """
    st = {"built_provider": "voyage", "chunks": None, "chunks_exact": False}
    hint = dense.fix_hint("no-key", st)
    assert "VOYAGE_API_KEY" in hint, (
        "an unknown count must not be read as an unfinished install")
    assert "None" not in hint
    assert "0 vectors" not in hint


def test_fix_hint_still_routes_an_empty_store_to_build():
    """A genuinely empty store is a different case and keeps its old answer."""
    st = {"built_provider": "voyage", "chunks": 0, "chunks_exact": True}
    assert dense.fix_hint("no-key", st) == dense._FIX["no-key"]


# --------------------------------------------------------------- build

def test_build_records_the_chunk_count(sandbox, monkeypatch):
    """The count is free at build time — the build already computes it."""
    paths.ensure_dirs()
    con = sqlite3.connect(str(dense.db_path()))
    try:
        con.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
        dense._write_meta(con, {"version": dense.INDEX_VERSION, "chunks": 12})
        con.commit()
    finally:
        con.close()
    meta = dense._recorded_meta()
    assert meta.get("chunks") == 12


# --------------------------------------------------------------- ready()

def test_ready_does_not_count_chunks(sandbox, keyed, sql_log, monkeypatch):
    """`ready()` carries the same scan, on the branch `status()` never reaches.

    `rag.retrieve_any` asks `dense.ready()` on every search *before* the hint
    runs. On a BM25-only machine it short-circuits at `have_backend()` and the
    cost hides — but on exactly the machines that installed the `[rag]` extra
    and built a store, every search paid the same 34.5 MB scan and then ran a
    vector query on top. Fixing only `status()` would have left the slow path
    slow for the users who invested the most in it.
    """
    _write_store(chunks=3)
    monkeypatch.setattr(dense, "have_backend", lambda: True)
    monkeypatch.setattr(dense, "_connect",
                        lambda: sqlite3.connect(str(dense.db_path())))
    assert dense.ready() is True
    assert _counted(sql_log) == [], (
        "ready() counted the chunks table on every search: %r"
        % _counted(sql_log))


def test_ready_is_false_for_an_empty_store(sandbox, keyed, monkeypatch):
    """Cheap must not mean wrong here either: no rows is still not ready."""
    _write_store(chunks=0)
    monkeypatch.setattr(dense, "have_backend", lambda: True)
    monkeypatch.setattr(dense, "_connect",
                        lambda: sqlite3.connect(str(dense.db_path())))
    assert dense.ready() is False


# --------------------------------------------------------- the search seam

def test_search_hint_does_not_count(sandbox, keyed, sql_log, monkeypatch):
    """End to end at the seam that regressed: BM25 answered, hint printed."""
    from boost_cli.commands import discovery
    _write_store(chunks=3, provider="openai")     # provider-changed -> not ready
    discovery._hint_semantic_search("BM25 full-content")
    assert _counted(sql_log) == [], (
        "the search hint counted the vector store: %r" % _counted(sql_log))
