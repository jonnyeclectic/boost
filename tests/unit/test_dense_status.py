"""`dense.status()` — why semantic search is (or isn't) running.

Every one of the three things dense retrieval needs (the `[rag]` extra, an
embeddings key, a built store) fails *silently* today: `rag.retrieve_any`
floors to BM25 and returns, so a user who set a key but never reindexed — or
who reindexed and then upgraded into a new embedding model — has no way to
learn that the vector search they paid for has never once run. `status()` is
the inspection primitive that makes each case nameable; `boost doctor` formats
it.

The store fixtures here are hand-built with plain `sqlite3` rather than
`dense.build()` on purpose: `status()` must be able to report what an existing
store was built with even when the sqlite-vec extension can no longer load, so
these tests must not need the extra either.
"""
import json
import sqlite3

import pytest

from boost_cli.core import dense, embed, logs, paths


def _write_store(provider="voyage", model="voyage-4", dim=1024,
                 version=dense.INDEX_VERSION, chunks=3, taps=("acme__skills",)):
    """A store carrying `meta` + `chunks` — no vec0, so no extra required."""
    paths.ensure_dirs()
    con = sqlite3.connect(str(dense.db_path()))
    try:
        con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    " name TEXT, tap TEXT, kind TEXT, cix INTEGER, snip TEXT)")
        con.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
        meta = {"version": version, "provider": provider, "model": model,
                "dim": dim, "commits": dict.fromkeys(taps, "c0ffee")}
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
    """Force the sqlite-vec backend to *look* present for every test here.

    `status()` reports the FIRST missing link, so on a runner without the
    `[rag]` extra every reason collapses to "no-backend" and no other branch is
    reachable. The extra is optional by design — it has no 3.14t wheel, so the
    free-threaded canary has none — which makes "is sqlite-vec installed?" the
    wrong thing for these assertions to depend on. Pin it instead; the genuine
    no-backend path gets its own test that patches `_load` back to None.

    Only `have_backend()` consults `_load`, and `status()` never opens the store
    through `_connect`, so a truthy sentinel is enough — no real extension load.
    """
    monkeypatch.setattr(dense, "_load", lambda: object())


@pytest.fixture
def keyed(monkeypatch):
    """A live Voyage key, so `embed.provider()` resolves."""
    monkeypatch.setenv("VOYAGE_API_KEY", "vk-test")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("BOOST_NO_EMBED", raising=False)


# ------------------------------------------------------- nothing configured

def test_nothing_available_at_all_reports_no_key(sandbox, monkeypatch):
    """No key AND no local backend — in practice a partial install or BOOST_NO_EMBED.

    `local_available()` is forced off rather than left to the ambient
    interpreter on purpose. This test used to assert "no-key" unconditionally,
    which made its result depend on whether the [rag] extra happened to be
    installed: green on CI (extra absent) and red on any machine that had run
    `pip install 'boost-skill-cli[rag]'`. An assertion that flips with the
    environment is not testing the code.
    """
    monkeypatch.setattr(embed, "local_available", lambda: False)
    st = dense.status()
    assert st["reason"] == "no-key"
    assert st["ready"] is False
    assert st["provider"] is None
    assert st["model"] is None
    # Opt-in means opt-in: never dress a deliberate default up as a problem.
    assert st["degraded"] is False


def test_local_backend_alone_gets_past_no_key(sandbox, monkeypatch):
    """The keyless path: the extra's bundled model counts as a provider.

    This is the behaviour change that made the old assertion wrong. With a local
    backend present and no key set, the missing link is the *store*, not a key —
    so `boost doctor` must send the user to `reindex --dense` rather than to a
    billing page.
    """
    monkeypatch.setattr(embed, "local_available", lambda: True)
    st = dense.status()
    assert st["reason"] == "no-store"
    assert st["provider"] == "local"
    assert st["model"] == embed.LOCAL_MODEL
    assert st["ready"] is False
    # Still not degraded: never having reindexed is an unfinished setup, not a fault.
    assert st["degraded"] is False
    assert "reindex --dense" in dense.fix_hint(st["reason"])


def test_no_store_is_named_separately_from_no_key(sandbox, keyed):
    """Key set, extra maybe present, but `reindex --dense` never run."""
    st = dense.status()
    assert st["reason"] == "no-store"
    assert st["ready"] is False
    assert st["provider"] == "voyage"
    assert st["model"] == "voyage-4"
    assert st["store_exists"] is False
    # Two of three steps done is an unfinished setup, not a broken one.
    assert st["degraded"] is False


# ------------------------------------------------------------ the silent trap

def test_model_change_is_reported_as_degraded(sandbox, keyed):
    """voyage-3 -> voyage-4 shares 1024 dims, so only the model name catches it.

    This is the case worth an exit code: the user has done all three steps and
    is still silently on BM25, which no other surface tells them.
    """
    _write_store(model="voyage-3")
    st = dense.status()
    assert st["reason"] == "model-changed"
    assert st["ready"] is False
    assert st["degraded"] is True
    assert st["built_model"] == "voyage-3"
    assert st["model"] == "voyage-4"
    # The dim is identical, which is exactly why dim alone cannot detect this.
    assert st["built_dim"] == st["dim"] == 1024


def test_provider_change_is_reported_as_degraded(sandbox, monkeypatch):
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    _write_store(provider="voyage", model="voyage-4", dim=1024)
    st = dense.status()
    assert st["reason"] == "provider-changed"
    assert st["degraded"] is True
    assert st["built_provider"] == "voyage"
    assert st["provider"] == "openai"


def test_index_version_change_is_reported_as_degraded(sandbox, keyed):
    """`build()` only wipes on provider/model/dim, so a version bump must be seen."""
    _write_store(version=dense.INDEX_VERSION + 1)
    st = dense.status()
    assert st["reason"] == "version-changed"
    assert st["degraded"] is True
    assert st["built_version"] == dense.INDEX_VERSION + 1


def test_dim_change_is_reported_as_degraded(sandbox, keyed):
    """Provider and model both match, but the recorded width does not.

    Reachable whenever a release re-points `embed._DIMS` (or a provider changes
    a model's default output size) — the vectors on disk are then a different
    shape than the query vector, which is unrecoverable without a rebuild.
    """
    _write_store(provider="voyage", model="voyage-4", dim=512)
    st = dense.status()
    assert st["reason"] == "dim-changed"
    assert st["degraded"] is True
    assert st["built_dim"] == 512
    assert st["dim"] == 1024


def test_meta_without_a_chunks_table_reads_as_empty(sandbox, keyed):
    """A store abandoned between `_write_meta` and `_ensure_schema`.

    Meta parses, so the store is real, but COUNT(*) has no table to read —
    that must degrade to "empty", not escape as a DatabaseError.
    """
    paths.ensure_dirs()
    con = sqlite3.connect(str(dense.db_path()))
    try:
        con.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
        con.executemany(
            "INSERT INTO meta (k, v) VALUES (?, ?)",
            [(k, json.dumps(v)) for k, v in
             {"version": dense.INDEX_VERSION, "provider": "voyage",
              "model": "voyage-4", "dim": 1024, "commits": {}}.items()])
        con.commit()
    finally:
        con.close()
    st = dense.status()
    assert st["chunks"] == 0
    assert st["reason"] == "empty"
    assert st["built_model"] == "voyage-4"


def test_unopenable_store_path_degrades(sandbox, keyed, monkeypatch):
    """`sqlite3.connect` itself failing must not raise out of a health check."""
    paths.ensure_dirs()
    boom = dense.db_path()
    boom.mkdir(parents=True, exist_ok=True)   # a directory, not a file
    st = dense.status()
    assert st["ready"] is False
    assert st["built_model"] is None


def test_empty_store_is_reported_as_degraded(sandbox, keyed):
    """A store whose every tap failed to embed reads as 'built' but serves nothing."""
    _write_store(chunks=0)
    st = dense.status()
    assert st["reason"] == "empty"
    assert st["degraded"] is True
    assert st["chunks"] == 0


# ------------------------------------------------------------- healthy path

def test_matching_store_reports_the_active_model(sandbox, keyed):
    _write_store(model="voyage-4", chunks=7,
                 taps=("acme__skills", "beta__rules"))
    st = dense.status()
    assert st["reason"] is None
    assert st["degraded"] is False
    assert st["chunks"] == 7
    assert st["taps"] == 2
    assert st["built_model"] == "voyage-4"
    assert st["model"] == "voyage-4"


def test_status_reports_the_recorded_model_without_the_extra(sandbox, keyed,
                                                            monkeypatch):
    """Dropping the [rag] extra must not blind the report.

    `_connect()` loads sqlite-vec and returns None without it, so reading meta
    through it would make the most useful line ("built with voyage-4") vanish
    exactly when the user needs to know why dense went quiet.
    """
    _write_store(model="voyage-4")
    monkeypatch.setattr(dense, "_load", lambda: None)
    st = dense.status()
    assert st["backend"] is False
    assert st["reason"] == "no-backend"
    assert st["built_model"] == "voyage-4"      # still legible
    assert st["chunks"] == 3


def test_kill_switch_reads_as_no_key(sandbox, keyed, monkeypatch):
    """BOOST_NO_EMBED short-circuits `provider()`, so dense cannot run."""
    monkeypatch.setenv("BOOST_NO_EMBED", "1")
    st = dense.status()
    assert st["ready"] is False
    assert st["reason"] == "no-key"


def test_corrupt_store_degrades_instead_of_raising(sandbox, keyed):
    paths.ensure_dirs()
    dense.db_path().write_bytes(b"this is not a database")
    st = dense.status()          # must not raise
    assert st["ready"] is False
    assert st["built_model"] is None


# ------------------------------------------------------------ doctor surfacing

def test_doctor_reports_bm25_only_when_no_key(boost, sandbox):
    res = boost("doctor", expect=None)
    assert "semantic search" in res.out.lower()
    assert "BM25" in res.out


def test_doctor_names_the_model_when_dense_is_active(boost, sandbox, keyed):
    _write_store(model="voyage-4", chunks=5)
    res = boost("doctor", expect=None)
    assert "voyage-4" in res.out


def test_doctor_flags_a_stale_store_as_an_issue(boost, sandbox, keyed):
    """The silent-BM25 case must move doctor's exit code, not just print."""
    _write_store(model="voyage-3")
    res = boost("doctor", expect=None)
    assert res.rc == 1
    assert "voyage-3" in res.out
    assert "reindex --dense" in res.out


def test_doctor_names_the_live_provider_on_a_provider_change(boost, sandbox,
                                                             monkeypatch):
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    _write_store(provider="voyage", model="voyage-4", dim=1024)
    res = boost("doctor", expect=None)
    assert res.rc == 1
    assert "live key is openai" in res.out


def test_doctor_says_an_empty_store_holds_no_vectors(boost, sandbox, keyed):
    _write_store(chunks=0)
    res = boost("doctor", expect=None)
    assert res.rc == 1
    assert "holds no vectors" in res.out


def test_doctor_stays_healthy_when_dense_is_simply_unconfigured(boost, sandbox):
    """A user who never wanted vector search must still get a clean bill."""
    res = boost("doctor", expect=None)
    assert "reindex --dense" not in res.out or res.rc == 0


# --------------------------------------------------- the log is only ✓ if usable

def test_doctor_flags_a_log_it_cannot_write(boost, sandbox):
    """Existence is not health.

    Observed for real: every `boost` invocation raised PermissionError on
    boost.log while doctor printed a ✓ for it in the same breath, because the
    check only tested `Path.exists()`. A health check that confirms presence
    rather than function is the exact failure this command exists to catch.
    """
    boost("count")                      # create the log
    lp = logs.log_path()
    assert lp.exists()
    lp.chmod(0o444)
    try:
        res = boost("doctor", expect=None)
        assert res.rc == 1
        assert "not writable" in res.out
        assert str(lp.name) in res.out
    finally:
        lp.chmod(0o644)


def test_doctor_still_oks_a_writable_log(boost, sandbox):
    boost("count")
    res = boost("doctor", expect=None)
    assert "diagnostic log at" in res.out
    assert "log is not writable" not in res.out
