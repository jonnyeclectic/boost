"""Unit tests: boost_cli/core/dense.py — the opt-in sqlite-vec backend.

The embeddings API is replaced with a deterministic 3-D toy embedder, so these
tests exercise the real sqlite-vec store (build, cosine KNN, per-entry max
aggregation, commit-keyed reuse, provider-switch invalidation) with no network.
Skipped entirely when the `[rag]` extra (sqlite-vec) isn't installed.
"""
from __future__ import annotations

import math
import sqlite3

import pytest

from boost_cli.core import dense, embed, rag


def _vec_loadable() -> bool:
    """True only if sqlite-vec both imports *and* loads on this interpreter,
    AND can actually run the bound-LIMIT KNN query dense.py issues.

    macOS' bundled Python is often built without ``enable_load_extension``, so
    the package imports but the extension can't load. Some sqlite3/sqlite-vec
    combinations (seen on Windows CI) load fine but reject a KNN query whose
    LIMIT is a bound parameter with "a LIMIT or 'k = ?' constraint is
    required" — a real query, not just vec_version(), is the only way to
    catch that. Either way dense retrieval is genuinely unavailable here and
    the product degrades to BM25, so we skip here.
    """
    try:
        import sqlite_vec  # type: ignore
    except ImportError:
        return False
    con = sqlite3.connect(":memory:")
    try:
        con.enable_load_extension(True)
        sqlite_vec.load(con)
        con.execute("select vec_version()").fetchone()
        con.execute("create virtual table t using vec0(embedding float[3])")
        con.execute("insert into t(rowid, embedding) values (1, ?)",
                    (sqlite_vec.serialize_float32([1.0, 0.0, 0.0]),))
        con.execute(
            "select rowid, distance from t where embedding match ? "
            "order by distance limit ?",
            (sqlite_vec.serialize_float32([1.0, 0.0, 0.0]), 5)).fetchall()
        return True
    except Exception:
        return False
    finally:
        con.close()


pytestmark = pytest.mark.skipif(
    not _vec_loadable(), reason="sqlite-vec extension not loadable here")

_VOCAB = {"react": (1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0), "python": (0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
          "testing": (0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0)}


def _toy_embed(texts, input_type=None, timeout=60):
    out = []
    for t in texts:
        v = [0.0] * 8
        for word, base in _VOCAB.items():
            if word in t.lower():
                for i in range(8):
                    v[i] += base[i]
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append([x / norm for x in v])
    return out


def _e(name, body, tap="acme/skills", kind="skill"):
    # Each entry gets its own `skill_md`. The shared "s" this used to hard-code
    # is not data a real catalog can produce — two skills cannot live at one
    # path — and once entries are identified by (tap, skill_md) it collapsed
    # every fixture entry onto a single key.
    return {"name": name, "tap": tap, "kind": kind,
            "skill_md": "skills/%s/SKILL.md" % name, "_body": body}


@pytest.fixture()
def dense_env(sandbox, monkeypatch):
    """sqlite-vec backend wired to the toy embedder + patched tap plumbing."""
    monkeypatch.setattr(embed, "embed", _toy_embed)
    monkeypatch.setattr(embed, "provider", lambda: "openai")
    monkeypatch.setattr(embed, "model", lambda: "toy-8")
    monkeypatch.setattr(embed, "dimension", lambda: 8)
    monkeypatch.setattr(embed, "available", lambda: True)
    monkeypatch.setattr(rag, "_tap_paths", lambda: {"acme/skills": "/x"})
    monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c1"})
    monkeypatch.setattr(dense, "read_body",
                        lambda e, tp=None: e["name"] + "\n" + e.get("_body", ""))
    return monkeypatch


_ENTRIES = [
    _e("jest", "react testing components"),
    _e("pytest", "python testing fixtures"),
]


class TestBackendPresence:
    def test_have_backend(self):
        assert dense.have_backend() is True

    def test_db_path_under_cache(self, sandbox):
        assert dense.db_path().name == "rag_vectors.sqlite"


class TestDegradation:
    def test_build_none_without_embeddings(self, sandbox, monkeypatch):
        monkeypatch.setattr(embed, "available", lambda: False)
        assert dense.build(entries=_ENTRIES) is None
        assert dense.ready() is False
        assert dense.retrieve("react", entries=_ENTRIES) is None

    def test_build_none_without_backend(self, dense_env, monkeypatch):
        monkeypatch.setattr(dense, "_load", lambda: None)
        assert dense.have_backend() is False
        assert dense.build(entries=_ENTRIES) is None
        assert dense.ready() is False

    def test_retrieve_none_when_query_embed_fails(self, dense_env, monkeypatch):
        dense.build(entries=_ENTRIES, force=True)
        assert dense.ready() is True
        monkeypatch.setattr(embed, "embed", lambda *a, **k: None)
        assert dense.retrieve("react", entries=_ENTRIES) is None


class TestBuildAndRetrieve:
    def test_ready_false_before_build(self, dense_env):
        assert dense.ready() is False
        assert dense.retrieve("react", entries=_ENTRIES) is None

    def test_build_stats(self, dense_env):
        stats = dense.build(entries=_ENTRIES, force=True)
        assert stats["entries"] == 2
        assert stats["chunks"] == 2
        assert stats["added"] == 2
        assert stats["provider"] == "openai"
        assert stats["model"] == "toy-8"
        assert dense.ready() is True

    def test_ranks_by_cosine(self, dense_env):
        dense.build(entries=_ENTRIES, force=True)
        hits = dense.retrieve("react", entries=_ENTRIES)
        assert hits[0]["entry"]["name"] == "jest"
        assert hits[0]["score"] > hits[-1]["score"]
        assert set(hits[0].keys()) == {"entry", "score", "snippet"}

        hits = dense.retrieve("python fixtures", entries=_ENTRIES)
        assert hits[0]["entry"]["name"] == "pytest"

    def test_kind_filter(self, dense_env):
        entries = [_e("jest", "react testing"),
                   _e("pyrule", "python testing", kind="rule")]
        dense.build(entries=entries, force=True)
        names = {h["entry"]["name"]
                 for h in dense.retrieve("testing", kind="skill",
                                         entries=entries)}
        assert names == {"jest"}

    def test_live_set_filter(self, dense_env):
        dense.build(entries=_ENTRIES, force=True)
        only = [_ENTRIES[0]]
        hits = dense.retrieve("testing", entries=only)
        assert {h["entry"]["name"] for h in hits} == {"jest"}

    def test_k_caps_results(self, dense_env):
        dense.build(entries=_ENTRIES, force=True)
        assert len(dense.retrieve("testing", k=1, entries=_ENTRIES)) == 1

    def test_max_score_per_entry_across_chunks(self, dense_env):
        # a body long enough to split into 2 chunks; "react" only in the first
        body = ("react " * 200) + "\n\n" + ("python " * 200)
        entries = [_e("multi", body)]
        dense.build(entries=entries, force=True)
        stats_chunks = dense.build(entries=entries, force=True)["chunks"]
        assert stats_chunks >= 2
        hits = dense.retrieve("react", entries=entries)
        assert hits[0]["entry"]["name"] == "multi"
        assert hits[0]["score"] > 0.5     # the react-heavy chunk wins (max)


class TestIncremental:
    def test_reuses_unchanged_tap(self, dense_env):
        first = dense.build(entries=_ENTRIES, force=True)
        second = dense.build(entries=_ENTRIES)
        assert second["reused"] == ["acme__skills"]
        assert second["reindexed"] == []
        assert second["chunks"] == first["chunks"]
        assert dense.retrieve("react", entries=_ENTRIES)

    def test_commit_change_reindexes(self, dense_env, monkeypatch):
        dense.build(entries=_ENTRIES, force=True)
        monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c2"})
        stats = dense.build(entries=_ENTRIES)
        assert stats["reused"] == []
        assert stats["reindexed"] == ["acme/skills"]

    def test_provider_switch_invalidates(self, dense_env, monkeypatch):
        dense.build(entries=_ENTRIES, force=True)
        assert dense.ready() is True
        # a different provider/dim must not be served stale vectors
        monkeypatch.setattr(embed, "provider", lambda: "voyage")
        monkeypatch.setattr(embed, "dimension", lambda: 4)
        assert dense.ready() is False

    def test_model_switch_invalidates(self, dense_env, monkeypatch):
        # Same provider, same dimension, different model — voyage-3 -> voyage-4
        # is exactly this shape. provider+dim alone cannot catch it.
        dense.build(entries=_ENTRIES, force=True)
        assert dense.ready() is True
        monkeypatch.setattr(embed, "model", lambda: "toy-4")
        assert dense.ready() is False

    def test_model_switch_reembeds_instead_of_reusing(self, dense_env,
                                                      monkeypatch):
        # The tap commit is unchanged, so only the model check can stop the
        # reuse path from serving vectors from the previous embedding space.
        dense.build(entries=_ENTRIES, force=True)
        monkeypatch.setattr(embed, "model", lambda: "toy-4")
        stats = dense.build(entries=_ENTRIES)
        assert stats["reused"] == []
        assert stats["model"] == "toy-4"
        assert stats["added"] == len(_ENTRIES)
        assert stats["chunks"] == len(_ENTRIES)   # wiped, not appended
        assert dense.ready() is True

    def test_added_and_chunks_on_reindex(self, dense_env, monkeypatch):
        dense.build(entries=_ENTRIES, force=True)
        monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c2"})
        stats = dense.build(entries=_ENTRIES)
        assert stats["added"] == 2         # both re-embedded on commit change
        assert stats["chunks"] == 2        # replaced, not duplicated


class TestDenseHardening:
    def test_ready_false_on_version_mismatch(self, dense_env):
        dense.build(entries=_ENTRIES, force=True)
        con = dense._connect()
        con.execute("INSERT OR REPLACE INTO meta (k, v) VALUES ('version','999')")
        con.commit()
        con.close()
        assert dense.ready() is False

    def test_ready_false_on_dim_mismatch(self, dense_env, monkeypatch):
        dense.build(entries=_ENTRIES, force=True)
        monkeypatch.setattr(embed, "dimension", lambda: 99)   # provider same
        assert dense.ready() is False

    def test_ready_false_on_empty_index(self, dense_env):
        stats = dense.build(entries=[], force=True)
        assert stats["chunks"] == 0
        assert dense.ready() is False         # the rows > 0 guard

    def test_ready_true_with_single_chunk(self, dense_env):
        dense.build(entries=[_e("solo", "react")], force=True)
        assert dense.ready() is True          # kills a `rows > 1` mutant

    def test_retrieve_none_when_knn_query_unsupported(self, dense_env, monkeypatch):
        # Some sqlite3/sqlite-vec combinations (observed on Windows) reject
        # the MATCH+LIMIT query shape outright — retrieve() must degrade to
        # "fall back to BM25" (None), not crash the search command.
        dense.build(entries=_ENTRIES, force=True)
        real_connect = dense._connect

        class _FlakyConnection:
            def __init__(self, real):
                self._real = real

            def execute(self, sql, *args, **kwargs):
                if "MATCH" in sql:
                    raise sqlite3.OperationalError(
                        "a LIMIT or 'k = ?' constraint is required on vec0 knn queries")
                return self._real.execute(sql, *args, **kwargs)

            def close(self):
                self._real.close()

        monkeypatch.setattr(dense, "_connect", lambda: _FlakyConnection(real_connect()))
        assert dense.retrieve("react", entries=_ENTRIES) is None

    def test_scores_are_cosine_similarities(self, dense_env):
        dense.build(entries=_ENTRIES, force=True)
        hits = dense.retrieve("react testing", entries=_ENTRIES)
        for h in hits:
            assert -1.0 <= h["score"] <= 1.0          # 1.0 - cosine distance
        # jest's chunk direction == the query direction -> similarity ~ 1.0
        assert hits[0]["entry"]["name"] == "jest"
        assert hits[0]["score"] == pytest.approx(1.0, abs=0.02)

    def test_snippet_is_stored_chunk_text(self, dense_env):
        entries = [_e("solo", "react testing components")]
        dense.build(entries=entries, force=True)
        hits = dense.retrieve("react", entries=entries)
        assert hits[0]["snippet"].startswith("solo")  # read_body prepends name
        assert "react testing" in hits[0]["snippet"]

    def test_kind_defaults_to_skill_when_absent(self, dense_env):
        e = {"name": "n", "tap": "acme/skills", "skill_md": "s",
             "_body": "react"}                          # no kind key
        dense.build(entries=[e], force=True)
        hits = dense.retrieve("react", kind="skill", entries=[e])
        assert hits and hits[0]["entry"]["name"] == "n"

    def test_batch_count_mismatch_is_skipped(self, dense_env, monkeypatch):
        # provider returns fewer vectors than texts -> that batch is dropped
        monkeypatch.setattr(embed, "embed",
                            lambda texts, **k: [[1.0, 2.0, 3.0]])
        stats = dense.build(entries=_ENTRIES, force=True)
        assert stats["added"] == 0
        assert dense.ready() is False

    def test_empty_query_knn_returns_empty(self, dense_env):
        dense.build(entries=_ENTRIES, force=True)
        # a query whose entries are all filtered out -> no live matches
        hits = dense.retrieve("react", entries=[])
        assert hits == []
