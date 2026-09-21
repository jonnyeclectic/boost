# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A ready store whose local model cannot be fetched or loaded.

See docs/roadmap/items/dense-ready-but-embedder-cannot-run.md. A store built
as ``local/BAAI/bge-small-en-v1.5`` on a machine that cannot fetch the weights
used to report ``ready``: `boost doctor` green-ticked it and exited 0, the
search hint stayed quiet, and every search made one failed 133 MB fetch —
measured at ~3.6 s a search against 0.1 s with dense switched off.

Nothing here needs onnxruntime, tokenizers or sqlite-vec: the runtime is a pair
of fakes, the network is a patched ``nethttp.urlopen`` that counts calls, and
the store is plain sqlite3 (``status()`` reads it without the extension).
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3

import pytest

from boost_cli.core import dense, embed, localembed, nethttp, paths, report

BODY = b"the pinned bytes"
DIGEST = hashlib.sha256(BODY).hexdigest()


@pytest.fixture(autouse=True)
def _clean(sandbox, monkeypatch):
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("BOOST_NO_EMBED", raising=False)
    embed.reset_local_cache()
    localembed.reset()
    yield
    embed.reset_local_cache()
    localembed.reset()


@pytest.fixture
def unreachable(monkeypatch):
    """The runtime imports, and every fetch fails. Returns the call log."""
    calls: list[str] = []

    def urlopen(url, timeout):
        calls.append(url)
        raise OSError("huggingface.co is unreachable")

    monkeypatch.setattr(localembed, "_deps", lambda: (object(), object()))
    monkeypatch.setattr(nethttp, "urlopen", urlopen)
    embed.reset_local_cache()
    return calls


def _fake_runtime(session_error: Exception | None = None):
    """(onnxruntime, tokenizers) fakes, and a list of sessions constructed."""
    made: list[str] = []

    class Tok:
        def enable_truncation(self, max_length):
            pass

        def enable_padding(self):
            pass

    class ORT:
        class SessionOptions:
            pass

        @staticmethod
        def InferenceSession(path, _opts, providers):
            made.append(path)
            if session_error is not None:
                raise session_error
            return object()

    class Toks:
        class Tokenizer:
            @staticmethod
            def from_file(_p):
                return Tok()

    return ORT, Toks, made


def _small_model_on_disk(monkeypatch):
    """Pin FILES to tiny bodies and put them in the model dir."""
    monkeypatch.setattr(localembed, "FILES", {
        "onnx/model.onnx": (len(BODY), DIGEST),
        "tokenizer.json": (len(BODY), DIGEST),
    })
    for rel in localembed.FILES:
        p = localembed.model_dir() / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(BODY)


def _marker():
    """Where the failure record lives — spelled out, not asked of the module.

    Literal on purpose: it is the contract between two processes, so a test
    that reached it through the helper would move with the helper.
    """
    return localembed.model_dir() / "unavailable.json"


def _record_on_disk(stage="fetch", error="URLError: timed out"):
    """A failure left by an earlier process: only the marker file exists."""
    p = _marker()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"stage": stage, "error": error}), encoding="utf-8")


def _age_marker(seconds: float) -> None:
    """Back-date the on-disk marker, and drop any in-process copy."""
    p = _marker()
    assert p.exists(), "no failure was recorded for the next process"
    then = p.stat().st_mtime - seconds
    os.utime(p, (then, then))
    localembed._failure = None


def _local_store(model=embed.LOCAL_MODEL, dim=embed.LOCAL_DIM,
                 provider="local", chunks=5):
    """A store as `dense.build` writes one, minus the vec0 tables."""
    paths.ensure_dirs()
    con = sqlite3.connect(str(dense.db_path()))
    try:
        con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, tap TEXT)")
        con.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
        meta = {"version": dense.INDEX_VERSION, "provider": provider,
                "model": model, "dim": dim,
                "commits": {"acme__skills": "c0ffee"}, "chunks": chunks}
        con.executemany("INSERT INTO meta (k, v) VALUES (?, ?)",
                        [(k, json.dumps(v)) for k, v in meta.items()])
        con.executemany("INSERT INTO chunks (tap) VALUES (?)",
                        [("acme/skills",)] * chunks)
        con.commit()
    finally:
        con.close()


@pytest.fixture
def local_ready(monkeypatch):
    """sqlite-vec present, the local model is the provider, a store is built."""
    monkeypatch.setattr(dense, "_load", lambda: object())
    monkeypatch.setattr(embed, "local_available", lambda: True)
    _local_store()


# ------------------------------------------------------ the per-search cost

class TestAFailedFetchIsPaidOnce:
    """The card's cost: one failed fetch per search, and per MCP query."""

    def test_one_process_fetches_once_however_many_queries(self, unreachable):
        for _ in range(3):
            assert embed.embed(["my app is slow"], input_type="query") is None
        assert len(unreachable) == 1

    def test_the_next_process_does_not_fetch_either(self, unreachable):
        assert embed.embed(["q"]) is None
        # A new `boost search`: nothing survives in memory, only the marker.
        localembed.reset()
        embed.reset_local_cache()
        assert embed.embed(["q"]) is None
        assert len(unreachable) == 1

    def test_an_expired_record_is_retried(self, unreachable):
        assert embed.embed(["q"]) is None
        _age_marker(3600 + 5)       # an hour: see localembed.RETRY_AFTER
        assert embed.embed(["q"]) is None
        assert len(unreachable) == 2

    def test_a_record_inside_the_hour_is_not(self, unreachable):
        assert embed.embed(["q"]) is None
        _age_marker(3600 - 60)
        assert embed.embed(["q"]) is None
        assert len(unreachable) == 1

    def test_the_failure_is_recorded_with_its_cause(self, unreachable):
        embed.embed(["q"])
        assert _marker().exists(), "a failed fetch left no record"
        rec = json.loads(_marker().read_text(encoding="utf-8"))
        assert rec["stage"] == "fetch"
        assert "unreachable" in rec["error"]
        assert rec["error"].startswith("OSError: ")

    def test_an_unwritable_cache_still_stops_the_retry(self, unreachable,
                                                        monkeypatch, tmp_path):
        """The MCP-server case: one process, and nowhere to write a marker."""
        blocker = tmp_path / "not-a-dir"
        blocker.write_text("x", encoding="utf-8")
        monkeypatch.setattr(localembed, "failure_path",
                            lambda: blocker / "unavailable.json")
        for _ in range(3):
            assert embed.embed(["q"]) is None
        assert len(unreachable) == 1


class TestBackOffRules:
    def test_the_window_is_half_open(self):
        localembed._note_failure("fetch", "x")
        at = localembed.last_failure()["at"]
        assert localembed.backing_off(now=at) is True
        assert localembed.backing_off(now=at + localembed.RETRY_AFTER - 1)
        assert localembed.backing_off(now=at + localembed.RETRY_AFTER) is False

    def test_a_record_from_the_future_does_not_hold_back(self):
        # A clock set back would otherwise hold the model off for as long as
        # the clock was ahead.
        localembed._note_failure("fetch", "x")
        at = localembed.last_failure()["at"]
        assert localembed.backing_off(now=at - 1) is False

    def test_no_record_means_no_back_off(self):
        assert localembed.last_failure() is None
        assert localembed.backing_off() is False

    def test_a_model_copied_in_ends_a_fetch_failure(self, monkeypatch):
        _small_model_on_disk(monkeypatch)
        localembed._note_failure("fetch", "x")
        assert localembed.backing_off() is False

    def test_a_partial_model_does_not(self, monkeypatch):
        _small_model_on_disk(monkeypatch)
        (localembed.model_dir() / "tokenizer.json").write_bytes(BODY[:-1])
        localembed._note_failure("fetch", "x")
        assert localembed.backing_off() is True

    def test_a_load_failure_holds_back_even_with_the_files_there(self,
                                                                 monkeypatch):
        _small_model_on_disk(monkeypatch)
        localembed._note_failure("load", "x")
        assert localembed.backing_off() is True

    def test_an_unreadable_marker_still_counts(self):
        p = localembed.failure_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{not json", encoding="utf-8")
        rec = localembed.last_failure()
        assert rec is not None
        assert rec["stage"] == "fetch" and rec["error"] == ""
        assert localembed.backing_off() is True

    def test_a_marker_holding_a_non_object_still_counts(self):
        p = localembed.failure_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("[1, 2]", encoding="utf-8")
        assert localembed.last_failure()["stage"] == "fetch"

    def test_the_marker_is_keyed_by_the_pinned_revision(self):
        # A new pin must not inherit the old revision's failure — and the
        # literal path the other tests write is the one the module reads.
        assert localembed.failure_path() == _marker()
        assert localembed.MODEL_REV in str(_marker())

    def test_forget_drops_both_copies(self):
        localembed._note_failure("fetch", "x")
        assert localembed.failure_path().exists()
        localembed.forget_failure()
        assert localembed.last_failure() is None
        assert not localembed.failure_path().exists()


class TestLoadRecordsAndClears:
    def test_a_load_failure_is_recorded_and_not_retried(self, monkeypatch):
        _small_model_on_disk(monkeypatch)
        ort, toks, made = _fake_runtime(RuntimeError("bad opset"))
        monkeypatch.setattr(localembed, "_deps", lambda: (ort, toks))
        assert localembed._load() is False
        assert localembed._load() is False
        assert len(made) == 1
        rec = localembed.last_failure()
        assert rec["stage"] == "load"
        assert rec["error"] == "RuntimeError: bad opset"

    def test_a_successful_load_clears_the_record(self, monkeypatch):
        _small_model_on_disk(monkeypatch)
        ort, toks, _made = _fake_runtime()
        monkeypatch.setattr(localembed, "_deps", lambda: (ort, toks))
        _record_on_disk("fetch", "earlier, on another network")
        assert localembed._load() is True
        assert not _marker().exists(), "a working model left its old failure"

    def test_a_missing_runtime_records_nothing(self, monkeypatch):
        # No runtime is `no-backend`/`no-key`, a rung of its own — not a model
        # failure, and recording it would name the wrong remedy.
        monkeypatch.setattr(localembed, "_deps", lambda: (None, None))
        assert localembed._load() is False
        assert not _marker().exists()

    def test_a_hash_mismatch_is_named(self, monkeypatch):
        class Resp:
            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False

            def read(self, *_a):
                return b""

        monkeypatch.setattr(localembed, "_deps", lambda: (object(), object()))
        monkeypatch.setattr(nethttp, "urlopen", lambda *_a, **_k: Resp())
        assert localembed._load() is False
        assert _marker().exists(), "a mismatched download left no record"
        error = json.loads(_marker().read_text(encoding="utf-8"))["error"]
        assert "sha256" in error
        assert "onnx/model.onnx" in error

    def test_a_long_error_fits_one_doctor_row(self):
        # A traceback-shaped message would otherwise put every line of it into
        # the marker and into doctor's issue row.
        text = localembed._describe(RuntimeError("first line\n" + "y" * 300))
        assert text == "RuntimeError: first line"
        text = localembed._describe(RuntimeError("x" * 300))
        assert text.startswith("RuntimeError: xxx")
        assert len(text) == 160

    def test_reset_forgets_the_in_process_record(self):
        localembed._note_failure("fetch", "x")
        localembed.failure_path().unlink()
        assert localembed.last_failure() is not None
        localembed.reset()
        assert localembed.last_failure() is None


# ------------------------------------------------------------- the ladder

class TestStatusNamesTheState:
    def test_a_recorded_failure_is_not_ready(self, local_ready):
        _record_on_disk("fetch", "URLError: timed out")
        st = dense.status()
        assert st["reason"] == "model-unavailable"
        assert st["ready"] is False
        # Vectors on disk that stopped serving are a fault, not a default.
        assert st["degraded"] is True
        assert st["model_failure"]["error"] == "URLError: timed out"

    def test_without_a_record_it_stays_ready(self, local_ready):
        st = dense.status()
        assert st["reason"] is None and st["ready"] is True
        assert st.get("model_failure") is None

    def test_an_old_record_is_still_reported(self, local_ready):
        """Retrying waits an hour; reporting does not expire.

        Nothing has succeeded since, so it is still the last thing known.
        """
        _record_on_disk()
        _age_marker(2 * 86400)
        assert dense.status()["reason"] == "model-unavailable"

    def test_status_never_tries_the_model(self, local_ready, monkeypatch):
        # The probe *is* the 133 MB fetch, and status() runs on every search.
        monkeypatch.setattr(localembed, "ensure_model", lambda: pytest.fail(
            "status() must read the record, not fetch"))
        monkeypatch.setattr(nethttp, "urlopen", lambda *_a, **_k: pytest.fail(
            "status() reached the network"))
        _record_on_disk()
        assert dense.status()["reason"] == "model-unavailable"
        _marker().unlink()
        assert dense.status()["reason"] is None

    def test_an_api_provider_ignores_a_local_record(self, monkeypatch):
        monkeypatch.setattr(dense, "_load", lambda: object())
        monkeypatch.setenv("VOYAGE_API_KEY", "vk-test")
        _local_store(provider="voyage", model=embed.VOYAGE_MODEL, dim=1024)
        _record_on_disk()
        st = dense.status()
        assert st["reason"] is None
        assert st.get("model_failure") is None

    def test_a_stale_store_is_named_first(self, monkeypatch):
        monkeypatch.setattr(dense, "_load", lambda: object())
        monkeypatch.setattr(embed, "local_available", lambda: True)
        _local_store(model="BAAI/some-other-model")
        _record_on_disk()
        assert dense.status()["reason"] == "model-changed"

    def test_an_empty_store_is_named_before_the_model(self, monkeypatch):
        # Nothing to search is the first thing to fix: a store with no
        # vectors needs building whether or not the model can load.
        monkeypatch.setattr(dense, "_load", lambda: object())
        monkeypatch.setattr(embed, "local_available", lambda: True)
        _local_store(chunks=0)
        _record_on_disk()
        assert dense.status()["reason"] == "empty"

    def test_a_load_failure_is_not_sent_to_download(self, monkeypatch):
        # The files are on disk; the load failed. Doctor must not promise a
        # 133 MB download the retry will not make.
        monkeypatch.setattr(dense, "_load", lambda: object())
        monkeypatch.setattr(embed, "local_available", lambda: True)
        _local_store()
        _record_on_disk(stage="load", error="RuntimeError: bad model")
        st = dense.status()
        assert st["reason"] == "model-unavailable"
        hint = dense.fix_hint(st["reason"], st)
        assert "`boost reindex --dense`" in hint
        assert "huggingface.co" not in hint and "download" not in hint

    def test_the_shard_surfaces_get_the_same_answer(self, monkeypatch):
        # `update --shards` and `reindex --fetch-shards` word a refused
        # manifest through `shards.remedy`, and had only the reason, so a
        # load failure was sent to download a model already on disk.
        from boost_cli.core import shards
        monkeypatch.setattr(dense, "_load", lambda: object())
        monkeypatch.setattr(embed, "local_available", lambda: True)
        _local_store()
        _record_on_disk(stage="load", error="RuntimeError: bad model")
        st = dense.status()
        manifest = {"provider": "local", "model": "BAAI/another-model",
                    "dim": embed.LOCAL_DIM}
        hint = shards.remedy(manifest)
        assert hint == dense.fix_hint(st["reason"], st)
        assert "download" not in hint

    def test_the_remedy_retries_rather_than_rebuilds(self):
        hint = dense.fix_hint("model-unavailable")
        assert "`boost reindex --dense`" in hint
        # Says what the command will do on this machine: fetch a large file
        # from one host. The generic fallback said neither.
        assert "huggingface.co" in hint
        # Every vector on disk is good; --force would re-embed them with the
        # very model that is missing.
        assert "--force" not in hint

    def test_ready_still_answers_for_the_store(self, local_ready, monkeypatch):
        """Shard re-import and near-duplicate collapse read stored vectors."""
        class Con:
            def execute(self, sql):
                class Cur:
                    def fetchone(self):
                        return (1,)
                return Cur()

            def close(self):
                pass

        monkeypatch.setattr(dense, "_connect", lambda: Con())
        monkeypatch.setattr(dense, "_read_meta", lambda _c: {
            "version": dense.INDEX_VERSION, "provider": "local",
            "model": embed.LOCAL_MODEL, "dim": embed.LOCAL_DIM, "chunks": 5})
        _record_on_disk()
        assert dense.ready() is True


# ------------------------------------------------------------- the surfaces

class TestSurfaces:
    def test_doctor_reports_an_issue_not_a_green_tick(self, local_ready):
        from boost_cli.commands import quality
        _record_on_disk("fetch", "URLError: timed out")
        rep = report.Report(as_json=True)
        quality._report_search_engine(rep)
        check = rep.payload()["checks"][0]
        assert check["status"] == "issue" and rep.issues == 1
        # One row: a store that is not serving has no quantization to advise.
        assert len(rep.payload()["checks"]) == 1
        msg = check["message"]
        assert "semantic search active" not in msg
        assert "the local model could not be downloaded" in msg
        assert "URLError: timed out" in msg
        assert "last tried" in msg
        assert "`boost reindex --dense`" in msg
        assert "huggingface.co" in msg

    def test_doctor_names_a_load_failure_as_one(self, local_ready):
        from boost_cli.commands import quality
        _record_on_disk("load", "RuntimeError: bad opset")
        rep = report.Report(as_json=True)
        quality._report_search_engine(rep)
        msg = rep.payload()["checks"][0]["message"]
        assert "the local model would not load" in msg

    def test_search_prints_the_hint(self, local_ready, capsys):
        from boost_cli.commands import discovery
        _record_on_disk()
        discovery._hint_semantic_search("BM25 full-content")
        printed = " ".join(capsys.readouterr().out.split())
        assert "semantic search is off" in printed
        assert "`boost reindex --dense`" in printed

    def test_mcp_does_not_call_a_built_store_unconfigured(self, local_ready):
        from boost_cli.core import mcp
        _record_on_disk()
        note = mcp.engine_note()
        assert "BM25 keyword matching only" in note
        assert "built but not in use" in note
        assert "not configured" not in note
        assert "`boost reindex --dense`" in note

    def test_an_unbuilt_machine_is_still_unconfigured(self, monkeypatch):
        from boost_cli.core import mcp
        monkeypatch.setattr(dense, "status",
                            lambda: {"ready": False, "reason": "no-store",
                                     "degraded": False})
        assert "not configured" in mcp.engine_note()

    @pytest.mark.parametrize("stage,phrase", [
        ("fetch", "could not be downloaded"), ("load", "would not load")])
    def test_one_wording_for_both_stages(self, stage, phrase):
        text = embed.local_failure_text({"stage": stage, "error": "E: x"})
        assert text == "the local model %s (E: x)" % phrase

    def test_the_wording_drops_an_empty_cause(self):
        assert (embed.local_failure_text({"stage": "fetch", "error": ""})
                == "the local model could not be downloaded")


# --------------------------------------------------------------- the remedy

class TestReindexRetries:
    def test_nothing_to_retry_loads_nothing(self, monkeypatch):
        monkeypatch.setattr(embed, "local_available", lambda: True)
        monkeypatch.setattr(embed, "_embed_local", lambda _t: pytest.fail(
            "no failure recorded: the next embedding loads on demand"))
        assert embed.retry_local() is None

    def test_an_api_provider_has_nothing_to_retry(self, monkeypatch):
        monkeypatch.setenv("VOYAGE_API_KEY", "vk-test")
        localembed._note_failure("fetch", "x")
        assert embed.retry_local() is None
        assert localembed.last_failure() is not None

    def test_a_recorded_failure_is_retried_at_once(self, unreachable):
        embed.embed(["q"])
        assert localembed.backing_off() is True
        assert embed.retry_local() is False
        # The back-off would have refused this attempt; the remedy must not.
        assert len(unreachable) == 2
        assert localembed.last_failure() is not None

    def test_reindex_is_the_remedy_the_hint_names(self, unreachable,
                                                  monkeypatch):
        """End to end through the command: a search fails, reindex retries.

        Its taps are all reused, so the build embeds nothing — the case where
        the model would otherwise never be touched and the hint would send the
        user round a loop.
        """
        from boost_cli.commands import discovery
        monkeypatch.setattr(dense, "have_backend", lambda: True)
        monkeypatch.setattr(dense, "quantize", lambda: None)
        monkeypatch.setattr(dense, "deduplicate", lambda: None)
        monkeypatch.setattr(dense, "build", lambda force=False, on_progress=None:
                            {"chunks": 5, "added": 0, "failed": []})
        assert embed.embed(["q"]) is None
        stats = discovery._reindex_dense(force=False)
        assert len(unreachable) == 2
        assert stats.get("model_error") is not None

    def test_a_retry_that_works_clears_the_record(self, monkeypatch):
        monkeypatch.setattr(embed, "local_available", lambda: True)
        localembed._note_failure("fetch", "x")
        monkeypatch.setattr(embed, "_embed_local",
                            lambda texts: [[0.0] * embed.LOCAL_DIM])
        assert embed.retry_local() is True
        assert localembed.last_failure() is None

    @pytest.fixture
    def wired(self, monkeypatch):
        from boost_cli.commands import discovery
        monkeypatch.setattr(dense, "have_backend", lambda: True)
        monkeypatch.setattr(embed, "available", lambda: True)
        monkeypatch.setattr(embed, "local_available", lambda: True)
        monkeypatch.setattr(dense, "quantize", lambda: None)
        monkeypatch.setattr(dense, "deduplicate", lambda: None)
        return discovery

    def test_reindex_retries_before_it_builds(self, wired, monkeypatch):
        seen: list[str] = []
        monkeypatch.setattr(embed, "retry_local",
                            lambda: seen.append("retry") or None)
        monkeypatch.setattr(dense, "build", lambda force=False, on_progress=None:
                            seen.append("build") or {"chunks": 5})
        wired._reindex_dense(force=False)
        assert seen == ["retry", "build"]

    def test_reindex_reports_a_failure_left_by_the_build(self, wired,
                                                         monkeypatch):
        # A first build that cannot fetch has nothing to retry beforehand; it
        # fails inside `build`, and that must reach the output too.
        monkeypatch.setattr(dense, "build", lambda force=False, on_progress=None:
                            _record_on_disk("fetch", "E: x") or {"chunks": 5})
        stats = wired._reindex_dense(force=False)
        assert stats.get("model_error"), "the build's failure was not reported"
        assert stats["model_error"]["error"] == "E: x"

    def test_a_healthy_reindex_reports_no_model_error(self, wired, monkeypatch):
        monkeypatch.setattr(dense, "build", lambda force=False, on_progress=None:
                            {"chunks": 5})
        assert "model_error" not in wired._reindex_dense(force=False)

    def test_reindex_output_names_the_model_not_a_rate_limit(
            self, wired, monkeypatch, capsys):
        monkeypatch.setattr(wired.registry, "list_taps", lambda: ["acme/x"])
        monkeypatch.setattr(wired.rag, "build", lambda force=False: {
            "docs": 5, "entries": 5, "taps": 1, "reused": [], "reindexed": [],
            "metadata_only": 0})
        monkeypatch.setattr(wired, "_reindex_dense", lambda force, spinner=None: {
            "chunks": 0, "added": 0, "failed": ["acme/x"], "reused": [],
            "provider": "local",
            "model_error": {"stage": "fetch", "error": "E: x", "at": 0.0}})
        assert wired.cmd_reindex(["--dense"]) == 0
        printed = " ".join(capsys.readouterr().out.split())
        assert "the local model could not be downloaded (E: x)" in printed
        assert "huggingface.co" in printed
        assert "rate limit" not in printed
