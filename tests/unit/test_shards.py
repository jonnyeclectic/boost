# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Published shards: the manifest contract, and refusing rather than degrading.

A shard moves vectors between machines, so every check in `core.shards` exists
because the alternative failure is silent. Mixing two embedding spaces does not
raise — it returns wrong rankings. Importing a shard for a commit the tap has
moved past does not raise either — it makes `dense.build` mark that tap
"reused" and pins the user to stale vectors. A corrupt download imports as
noise. So the tests here are mostly about what is *refused*, and where: the
space and commit checks have to happen before the download, or a user pays 129
MB to be told no.

The fixtures are plain dicts and `file:` URLs. `download` is exercised for
real — it is the function with a digest, a size ceiling and an origin check in
it, and mocking urlopen would test none of them.
"""
import contextlib
import json
import sqlite3

import pytest

from boost_cli.core import shards
from boost_cli.errors import BoostError

SPACE = {"provider": "local", "model": "BAAI/bge-small-en-v1.5", "dim": 384}


def _shard_file(tmp_path, tap, commit):
    """A shard on disk, and the manifest row that describes it."""
    body = json.dumps({"tap": tap, "commit": commit, **SPACE,
                       "chunks": [{"name": "x", "tap": tap, "path": "p",
                                   "kind": "skill", "cix": 0, "snip": "s",
                                   "embedding": "AAAA"}]})
    path = tmp_path / (tap.replace("/", "__") + ".shard.json")
    path.write_text(body, encoding="utf-8")
    import hashlib
    return path, {"tap": tap, "commit": commit, "chunks": 1,
                  "bytes": len(body.encode()),
                  "sha256": hashlib.sha256(body.encode()).hexdigest(),
                  "url": path.as_uri()}


def _manifest(tmp_path, rows, **over):
    data = {"version": 1, "generated": "2026-01-01T00:00:00Z", **SPACE,
            "shards": rows}
    data.update(over)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class TestFetchManifest:
    """Every field validated here is load-bearing at import time."""

    def test_reads_a_well_formed_manifest(self, tmp_path):
        _, row = _shard_file(tmp_path, "a/b", "1" * 40)
        path = _manifest(tmp_path, [row])
        got = shards.fetch_manifest(path.as_uri())
        assert got["provider"] == "local"
        assert got["dim"] == 384
        assert got["_url"] == path.as_uri()

    def test_a_future_schema_is_refused_by_version(self, tmp_path):
        path = _manifest(tmp_path, [], version=99)
        with pytest.raises(BoostError, match="version"):
            shards.fetch_manifest(path.as_uri())

    @pytest.mark.parametrize("field", ["provider", "model", "dim"])
    def test_a_manifest_without_its_space_is_refused(self, tmp_path, field):
        # Without these three nothing downstream can tell whether the vectors
        # are comparable with this machine's, and `incompatible` would compare
        # against None and wave everything through.
        path = _manifest(tmp_path, [], **{field: None})
        with pytest.raises(BoostError, match=field):
            shards.fetch_manifest(path.as_uri())

    def test_missing_shards_list_is_refused(self, tmp_path):
        path = _manifest(tmp_path, [])
        path.write_text(json.dumps({"version": 1, **SPACE}), encoding="utf-8")
        with pytest.raises(BoostError, match="shards"):
            shards.fetch_manifest(path.as_uri())

    def test_non_json_is_a_boost_error_not_a_traceback(self, tmp_path):
        path = tmp_path / "manifest.json"
        path.write_text("<html>404</html>", encoding="utf-8")
        with pytest.raises(BoostError, match="valid JSON"):
            shards.fetch_manifest(path.as_uri())

    def test_a_non_https_url_is_refused_before_urllib_sees_it(self):
        with pytest.raises(BoostError, match="refusing to fetch"):
            shards.fetch_manifest("ftp://example.com/manifest.json")

    def test_the_env_override_wins(self, monkeypatch):
        monkeypatch.setenv(shards.MANIFEST_ENV, "https://example.test/m.json")
        assert shards.manifest_url() == "https://example.test/m.json"

    def test_the_default_url_is_https_and_anonymous(self, monkeypatch):
        monkeypatch.delenv(shards.MANIFEST_ENV, raising=False)
        # A workflow artifact URL needs a token; a release asset does not. If
        # this ever points at /actions/artifacts the quickstart is broken for
        # everyone who is not logged in.
        assert shards.manifest_url().startswith("https://")
        assert "/releases/download/" in shards.manifest_url()


class TestIncompatible:
    """The pre-download gate. Answered from the manifest, never from bytes."""

    def test_matching_space_is_compatible(self, monkeypatch):
        monkeypatch.setattr(shards.embed, "provider", lambda: "local")
        monkeypatch.setattr(shards.embed, "model", lambda: SPACE["model"])
        monkeypatch.setattr(shards.embed, "dimension", lambda: 384)
        assert shards.incompatible({**SPACE}) is None

    def test_no_backend_names_the_backend_not_the_model(self, monkeypatch):
        monkeypatch.setattr(shards.embed, "provider", lambda: None)
        assert "backend" in shards.incompatible({**SPACE})

    def test_a_paid_provider_cannot_use_keyless_shards(self, monkeypatch):
        # The case that decides what is worth publishing: a machine holding a
        # Voyage key embeds queries at 1024-d, so 384-d keyless vectors are
        # unusable there — and it must be told before a download, not after.
        monkeypatch.setattr(shards.embed, "provider", lambda: "voyage")
        monkeypatch.setattr(shards.embed, "model", lambda: "voyage-4")
        monkeypatch.setattr(shards.embed, "dimension", lambda: 1024)
        why = shards.incompatible({**SPACE})
        assert "voyage" in why

    def test_same_provider_different_model_is_refused(self, monkeypatch):
        monkeypatch.setattr(shards.embed, "provider", lambda: "local")
        monkeypatch.setattr(shards.embed, "model", lambda: "other/model")
        monkeypatch.setattr(shards.embed, "dimension", lambda: 384)
        assert "other/model" in shards.incompatible({**SPACE})

    def test_same_model_different_dim_is_refused(self, monkeypatch):
        monkeypatch.setattr(shards.embed, "provider", lambda: "local")
        monkeypatch.setattr(shards.embed, "model", lambda: SPACE["model"])
        monkeypatch.setattr(shards.embed, "dimension", lambda: 768)
        assert "768" in shards.incompatible({**SPACE})

    def test_the_kill_switch_is_named_not_mistaken_for_a_missing_backend(
            self, monkeypatch):
        # With BOOST_NO_EMBED set, `provider()` is None whether or not the
        # extra is installed, and "no embedding backend" sent a user who has
        # one to reinstall it. The switch is what to name.
        monkeypatch.setenv("BOOST_NO_EMBED", "1")
        why = shards.incompatible({**SPACE})
        assert "BOOST_NO_EMBED" in why
        assert "backend" not in why


def _machine(monkeypatch, prov, model, dim, local=True):
    """Stub the embedding space this machine resolves, and its local model."""
    monkeypatch.setattr(shards.embed, "provider", lambda: prov)
    monkeypatch.setattr(shards.embed, "model", lambda: model)
    monkeypatch.setattr(shards.embed, "dimension", lambda: dim)
    monkeypatch.setattr(shards.embed, "local_available", lambda: local)
    monkeypatch.setattr(shards.embed, "local_installed", lambda: local)
    for env in shards.embed.KEY_ENV.values():
        monkeypatch.delenv(env, raising=False)


@pytest.mark.usefixtures("sandbox")
class TestRemedy:
    """The one next action for a refused manifest, read by every surface.

    The defect it closes: a machine with VOYAGE_API_KEY exported refuses the
    keyless shards, and the only advice anywhere was `boost reindex --dense` —
    which, with that key set, embeds through the paid API. The free path
    (drop the key, take the download) was never mentioned.

    Sandboxed because the answer reads the store on disk: unsandboxed, these
    tests would judge whatever store the developer's own machine holds.
    """

    def test_a_key_that_outranks_the_local_model_is_named_with_its_cost(
            self, monkeypatch):
        _machine(monkeypatch, "voyage", "voyage-4", 1024)
        fix = shards.remedy({**SPACE})
        assert "`unset VOYAGE_API_KEY`" in fix
        # The free path must say how to take it, not just what to drop.
        assert "`boost update --shards`" in fix
        # Keeping the key is a real choice, and it is not free: say so.
        assert "keep the key, and `boost reindex --dense`" in fix
        assert "voyage" in fix.split("`boost reindex --dense`")[1]
        assert "paid" in fix

    def test_every_key_that_outranks_local_is_named(self, monkeypatch):
        # Unsetting VOYAGE alone falls through to OPENAI, which is still not
        # the published space — the remedy would be a measured no-op.
        _machine(monkeypatch, "voyage", "voyage-4", 1024)
        monkeypatch.setenv("VOYAGE_API_KEY", "v")
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        fix = shards.remedy({**SPACE})
        assert "`unset VOYAGE_API_KEY OPENAI_API_KEY`" in fix
        assert "keep the keys," in fix

    def test_only_the_key_in_force_is_named(self, monkeypatch):
        _machine(monkeypatch, "openai", "text-embedding-3-small", 1536)
        fix = shards.remedy({**SPACE})
        assert "`unset OPENAI_API_KEY`" in fix
        assert "VOYAGE" not in fix
        assert "openai" in fix

    def test_no_local_model_means_unsetting_the_key_would_not_help(
            self, monkeypatch):
        # Drop the key without the local model and `provider()` is None:
        # the published vectors still cannot load. Don't send them there.
        _machine(monkeypatch, "voyage", "voyage-4", 1024, local=False)
        fix = shards.remedy({**SPACE})
        assert "unset" not in fix
        assert "`boost reindex --dense`" in fix and "paid" in fix

    def test_a_local_model_mismatch_embeds_locally_and_costs_nothing(
            self, monkeypatch):
        _machine(monkeypatch, "local", "other/model", 384)
        fix = shards.remedy({**SPACE})
        assert "`boost reindex --dense`" in fix
        assert "locally" in fix
        assert "unset" not in fix and "paid" not in fix

    def test_a_keyed_manifest_is_not_answered_by_dropping_a_key(
            self, monkeypatch):
        # Only a keyless manifest is served by unsetting keys.
        _machine(monkeypatch, "voyage", "voyage-4", 1024)
        fix = shards.remedy({"provider": "openai",
                             "model": "text-embedding-3-small", "dim": 1536})
        assert "unset" not in fix
        assert "`boost reindex --dense`" in fix

    def test_the_kill_switch_defers_to_the_dense_table(self, monkeypatch):
        monkeypatch.setenv("BOOST_NO_EMBED", "1")
        fix = shards.remedy({**SPACE})
        from boost_cli.core import dense
        assert fix == dense.fix_hint("disabled")

    def test_no_backend_defers_to_the_dense_table(self, monkeypatch):
        # One table for one question: `boost doctor` and `boost search`
        # already answer "no provider" from dense.fix_hint, so this must not
        # grow a second, possibly contradictory, answer.
        from boost_cli.core import dense
        _machine(monkeypatch, None, None, None)
        st = {"reason": "no-backend"}
        monkeypatch.setattr(dense, "status", lambda **k: st)
        assert shards.remedy({**SPACE}) == dense.fix_hint("no-backend")

    # The free path needs somewhere to land. `dense.import_shard` merges a
    # shard only into a store in its own space, so for a user whose vectors
    # were built with the key, "unset it" bought a refused import ("provider
    # mismatch: store 'voyage', shard 'local'") and knocked their paid store
    # offline — `provider-changed`, whose hint is the `--force` rebuild that
    # throws those vectors away. Measured on a real voyage-4 store.

    def test_a_store_built_with_the_key_is_not_told_to_drop_it(
            self, monkeypatch, vector_store):
        _machine(monkeypatch, "voyage", "voyage-4", 1024)
        assert vector_store()["ready"]       # a working store, not a stub
        fix = shards.remedy({**SPACE})
        assert "unset" not in fix
        assert "cannot merge" in fix
        # Keeping it current is the ordinary command, not the rebuild.
        assert "`boost reindex --dense`" in fix and "--force" not in fix
        assert "voyage" in fix and "paid" in fix

    def test_no_store_on_disk_keeps_the_free_path(self, monkeypatch):
        from boost_cli.core import dense
        _machine(monkeypatch, "voyage", "voyage-4", 1024)
        monkeypatch.setattr(dense, "have_backend", lambda: True)
        assert not dense.status()["store_exists"]
        assert "`unset VOYAGE_API_KEY`" in shards.remedy({**SPACE})

    def test_a_store_with_no_recorded_space_keeps_the_free_path(
            self, monkeypatch, vector_store):
        # `import_shard` lets such a store adopt the shard's space, so it is
        # no obstacle to the download.
        _machine(monkeypatch, "voyage", "voyage-4", 1024)
        assert vector_store(provider=None)["store_exists"]
        assert "`unset VOYAGE_API_KEY`" in shards.remedy({**SPACE})

    def test_a_store_already_in_the_published_space_keeps_the_free_path(
            self, monkeypatch, vector_store):
        # Built keyless, key exported since: dropping the key is exactly
        # what puts this store back in service, and the shards merge into it.
        _machine(monkeypatch, "voyage", "voyage-4", 1024)
        st = vector_store(**SPACE)
        assert st["reason"] == "provider-changed"
        assert "`unset VOYAGE_API_KEY`" in shards.remedy({**SPACE})

    def test_a_keyless_store_of_another_model_is_another_space(
            self, monkeypatch, vector_store):
        # Provider alone is not the space: dropping the key would leave this
        # store `model-changed`, and the import would refuse on the model.
        _machine(monkeypatch, "voyage", "voyage-4", 1024)
        vector_store(provider="local", model="other/model", dim=384)
        assert "unset" not in shards.remedy({**SPACE})

    def test_a_store_in_another_space_that_cannot_serve_defers_to_its_table(
            self, monkeypatch, vector_store):
        # Its own trouble comes first, in the words `boost doctor` uses for
        # it; "keeps them current" would be false of a store that is not
        # serving at all.
        from boost_cli.core import dense
        _machine(monkeypatch, "voyage", "voyage-4", 1024)
        st = vector_store(model="voyage-3")
        assert st["reason"] == "model-changed"
        fix = shards.remedy({**SPACE})
        assert fix == dense.fix_hint("model-changed", st)
        assert "unset" not in fix


class TestRows:
    """One malformed row must not deny a user the other forty."""

    def test_keys_by_tap(self, tmp_path):
        _, a = _shard_file(tmp_path, "a/b", "1" * 40)
        _, c = _shard_file(tmp_path, "c/d", "2" * 40)
        assert sorted(shards.rows({"shards": [a, c]})) == ["a/b", "c/d"]

    @pytest.mark.parametrize("drop", ["commit", "url", "sha256", "tap"])
    def test_a_row_missing_a_required_field_is_skipped(self, tmp_path, drop):
        _, a = _shard_file(tmp_path, "a/b", "1" * 40)
        _, c = _shard_file(tmp_path, "c/d", "2" * 40)
        del a[drop]
        assert list(shards.rows({"shards": [a, c]})) == ["c/d"]

    def test_a_non_dict_row_is_skipped(self):
        assert shards.rows({"shards": ["nonsense", None]}) == {}

    def test_no_shards_key_is_empty_not_an_error(self):
        assert shards.rows({}) == {}


class TestDownload:
    """Verification, origin pinning, and leaving nothing behind on refusal."""

    def test_a_verified_shard_lands_at_dest(self, tmp_path):
        _, row = _shard_file(tmp_path, "a/b", "1" * 40)
        mpath = _manifest(tmp_path, [row])
        manifest = shards.fetch_manifest(mpath.as_uri())
        dest = tmp_path / "out" / "a__b.shard.json"
        shards.download(row, dest, manifest)
        assert json.loads(dest.read_text())["tap"] == "a/b"

    def test_a_bad_digest_is_refused_and_deleted(self, tmp_path):
        _, row = _shard_file(tmp_path, "a/b", "1" * 40)
        manifest = shards.fetch_manifest(_manifest(tmp_path, [row]).as_uri())
        row = {**row, "sha256": "0" * 64}
        dest = tmp_path / "out" / "a__b.shard.json"
        with pytest.raises(BoostError, match="verification"):
            shards.download(row, dest, manifest)
        # Nothing partial survives: a later run must not mistake it for good.
        assert not dest.exists()
        assert not dest.with_suffix(dest.suffix + ".part").exists()

    def test_a_url_off_the_manifests_host_is_refused(self, tmp_path):
        _, row = _shard_file(tmp_path, "a/b", "1" * 40)
        mpath = _manifest(tmp_path, [row])
        manifest = shards.fetch_manifest(mpath.as_uri())
        # A manifest names the URLs boost fetches, so a tampered one must not
        # be able to widen where the fetch goes.
        row = {**row, "url": "https://evil.example/a.json"}
        with pytest.raises(BoostError, match="not on the manifest"):
            shards.download(row, tmp_path / "x.json", manifest)

    def test_size_label_reads_bytes_and_tolerates_its_absence(self):
        assert shards._size_label({"bytes": 2 * 1024 * 1024}).endswith("MB")
        assert shards._size_label({}) == ""
        assert shards._size_label({"bytes": "big"}) == ""


@pytest.mark.usefixtures("sandbox")
class TestSync:
    """Per-tap outcomes: one failure never costs another tap its vectors.

    ``sandbox`` because a successful import stamps the shard-sync marker under
    ``$HOME`` — the mtime `boost search` reads — and a test suite must not write
    into the developer's real ``~/.boost/state`` to find that out.
    """

    def _manifest_for(self, tmp_path, taps):
        rows = [_shard_file(tmp_path, tap, commit)[1] for tap, commit in taps]
        path = _manifest(tmp_path, rows)
        return shards.fetch_manifest(path.as_uri())

    @pytest.fixture(autouse=True)
    def _keyless(self, monkeypatch):
        monkeypatch.setattr(shards.embed, "provider", lambda: "local")
        monkeypatch.setattr(shards.embed, "model", lambda: SPACE["model"])
        monkeypatch.setattr(shards.embed, "dimension", lambda: 384)

    def test_imports_and_reports_chunks(self, tmp_path, monkeypatch):
        manifest = self._manifest_for(tmp_path, [("a/b", "1" * 40)])
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "import_shard",
                            lambda shard, commit: (True, "1 chunk"))
        res = shards.sync(["a/b"], {"a/b": "1" * 40}, manifest=manifest,
                          cache_dir=tmp_path / "cache")
        assert res == [{"tap": "a/b", "status": "imported",
                        "detail": "1 chunk", "chunks": 1}]

    def test_a_moved_tap_is_refused_without_downloading(self, tmp_path,
                                                        monkeypatch):
        manifest = self._manifest_for(tmp_path, [("a/b", "1" * 40)])
        called = []
        monkeypatch.setattr(shards, "download",
                            lambda *a, **k: called.append(1))
        res = shards.sync(["a/b"], {"a/b": "9" * 40}, manifest=manifest,
                          cache_dir=tmp_path / "cache")
        assert res[0]["status"] == "refused"
        # The point of checking the commit here as well as in `import_shard`.
        assert called == []

    def test_a_tap_with_no_published_shard_says_so(self, tmp_path):
        manifest = self._manifest_for(tmp_path, [("a/b", "1" * 40)])
        res = shards.sync(["z/z"], {"z/z": "1" * 40}, manifest=manifest,
                          cache_dir=tmp_path / "cache")
        assert res[0]["status"] == "unpublished"

    def test_one_failure_does_not_stop_the_others(self, tmp_path, monkeypatch):
        manifest = self._manifest_for(tmp_path, [("a/b", "1" * 40),
                                                 ("c/d", "2" * 40)])
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "import_shard",
                            lambda shard, commit: (True, "ok"))
        real = shards.download

        def flaky(row, dest, manifest, timeout=300.0):
            if row["tap"] == "a/b":
                raise BoostError("network went away")
            return real(row, dest, manifest, timeout)

        monkeypatch.setattr(shards, "download", flaky)
        res = shards.sync(["a/b", "c/d"], {"a/b": "1" * 40, "c/d": "2" * 40},
                          manifest=manifest, cache_dir=tmp_path / "cache")
        assert [r["status"] for r in res] == ["failed", "imported"]

    def test_an_incompatible_manifest_short_circuits_every_tap(self, tmp_path,
                                                               monkeypatch):
        manifest = self._manifest_for(tmp_path, [("a/b", "1" * 40)])
        monkeypatch.setattr(shards.embed, "dimension", lambda: 1024)
        res = shards.sync(["a/b"], {"a/b": "1" * 40}, manifest=manifest,
                          cache_dir=tmp_path / "cache")
        assert [r["status"] for r in res] == ["incompatible"]

    def test_the_downloaded_json_is_deleted_after_import(self, tmp_path,
                                                         monkeypatch):
        manifest = self._manifest_for(tmp_path, [("a/b", "1" * 40)])
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "import_shard",
                            lambda shard, commit: (True, "ok"))
        cache = tmp_path / "cache"
        shards.sync(["a/b"], {"a/b": "1" * 40}, manifest=manifest,
                    cache_dir=cache)
        # A shard is a transfer format; these run to hundreds of megabytes and
        # are dead weight once their rows are in the store.
        assert list(cache.glob("*.shard.json")) == []

    def test_events_are_emitted_per_tap(self, tmp_path, monkeypatch):
        manifest = self._manifest_for(tmp_path, [("a/b", "1" * 40)])
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "import_shard",
                            lambda shard, commit: (True, "ok"))
        seen = []
        shards.sync(["a/b"], {"a/b": "1" * 40}, manifest=manifest,
                    cache_dir=tmp_path / "cache",
                    on_event=lambda t, s, d: seen.append((t, s)))
        assert ("a/b", "downloading") in seen
        assert ("a/b", "imported") in seen

    def test_a_tap_already_built_at_the_published_commit_skips_download(
            self, tmp_path, monkeypatch):
        manifest = self._manifest_for(tmp_path, [("a/b", "1" * 40)])
        called = []
        monkeypatch.setattr(shards, "download",
                            lambda *a, **k: called.append(1))
        res = shards.sync(["a/b"], {"a/b": "1" * 40}, manifest=manifest,
                          cache_dir=tmp_path / "cache",
                          built={"a/b": "1" * 40})
        assert res == [{"tap": "a/b", "status": "current"}]
        assert called == []

    def test_built_map_defaults_to_empty_and_still_downloads(
            self, tmp_path, monkeypatch):
        # Omitting `built` must reproduce the pre-existing always-download
        # behaviour exactly — callers like `pkg._resync_vectors` rely on it.
        manifest = self._manifest_for(tmp_path, [("a/b", "1" * 40)])
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "import_shard",
                            lambda shard, commit: (True, "ok"))
        res = shards.sync(["a/b"], {"a/b": "1" * 40}, manifest=manifest,
                          cache_dir=tmp_path / "cache")
        assert res[0]["status"] == "imported"

    def test_a_built_commit_that_does_not_match_still_downloads(
            self, tmp_path, monkeypatch):
        # `built` names an older commit (a prior import, or a stale record) —
        # the triple-equality must fail closed and pay for a fresh shard.
        manifest = self._manifest_for(tmp_path, [("a/b", "1" * 40)])
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "import_shard",
                            lambda shard, commit: (True, "ok"))
        res = shards.sync(["a/b"], {"a/b": "1" * 40}, manifest=manifest,
                          cache_dir=tmp_path / "cache",
                          built={"a/b": "9" * 40})
        assert res[0]["status"] == "imported"

    def test_current_status_is_emitted_and_marks_sync_fresh(
            self, tmp_path, monkeypatch):
        manifest = self._manifest_for(tmp_path, [("a/b", "1" * 40)])
        seen = []
        res = shards.sync(["a/b"], {"a/b": "1" * 40}, manifest=manifest,
                          cache_dir=tmp_path / "cache",
                          built={"a/b": "1" * 40},
                          on_event=lambda t, s, d: seen.append((t, s)))
        assert ("a/b", "current") in seen
        # "current" is not "imported" — a rerun that changes nothing must not
        # falsely stamp the shard-sync marker via the `any(... == "imported")`
        # check, and must not have tried to download anything either.
        assert res[0]["status"] == "current"


_ROW = {"tap": "a/b", "commit": "1" * 40, "url": "file:///a", "sha256": "0",
        "bytes": 100}


@pytest.mark.usefixtures("sandbox")
class TestPlan:
    """What `sync` will do, decided before a byte moves — and `sync` does it.

    `boost quickstart --dry-run` counts and sizes its preview from this, so
    a step it classifies wrongly is a promise the live run breaks.
    """

    def _plan(self, commits, built=None, taps=("a/b",)):
        return shards.plan(list(taps), commits, {"shards": [_ROW]}, built)

    def test_a_tap_without_a_row_is_unpublished(self):
        assert self._plan({}, taps=["z/z"]) == [
            {"tap": "z/z", "status": "unpublished"}]

    def test_a_tap_at_the_row_with_vectors_built_there_is_current(self):
        steps = self._plan({"a/b": "1" * 40}, built={"a/b": "1" * 40})
        assert steps == [{"tap": "a/b", "status": "current", "row": _ROW}]

    def test_vectors_built_at_another_commit_are_downloaded_again(self):
        steps = self._plan({"a/b": "1" * 40}, built={"a/b": "9" * 40})
        assert [s["status"] for s in steps] == ["download"]

    def test_a_tap_that_moved_past_its_row_is_refused_before_download(self):
        steps = self._plan({"a/b": "2" * 40})
        assert steps == [{"tap": "a/b", "status": "refused",
                          "commit_moved": True,
                          "detail": "tap is at 2222222, shard is for 1111111",
                          "row": _ROW}]

    def test_a_tap_with_no_known_commit_is_downloaded(self):
        # `sync` has always fetched here and left the verdict to
        # `import_shard`; the plan must not quietly start refusing.
        assert self._plan({})[0]["status"] == "download"
        assert self._plan({})[0]["row"] is _ROW

    def test_sync_does_what_the_plan_says_and_reports_it_without_the_row(
            self, tmp_path, monkeypatch):
        rows = {tap: _shard_file(tmp_path, tap, "1" * 40)[1]
                for tap in ("a/b", "c/d", "e/f")}
        manifest = shards.fetch_manifest(
            _manifest(tmp_path, list(rows.values())).as_uri())
        monkeypatch.setattr(shards, "incompatible", lambda _m: None)
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "import_shard",
                            lambda shard, commit: (True, "ok"))
        fetched, events = [], []
        real = shards.download

        def download(row, dest, manifest, timeout=300.0):
            fetched.append(row["tap"])
            return real(row, dest, manifest, timeout)

        monkeypatch.setattr(shards, "download", download)
        taps = ["a/b", "c/d", "e/f", "z/z"]
        commits = {"a/b": "1" * 40, "c/d": "2" * 40, "e/f": "1" * 40}
        built = {"a/b": "1" * 40}
        steps = shards.plan(taps, commits, manifest, built)
        res = shards.sync(taps, commits, manifest=manifest, built=built,
                          cache_dir=tmp_path / "cache",
                          on_event=lambda t, s, d: events.append((t, s, d)))
        assert fetched == [s["tap"] for s in steps
                           if s["status"] == "download"] == ["e/f"]
        assert [r["status"] for r in res] == ["current", "refused",
                                              "imported", "unpublished"]
        assert all("row" not in r for r in res)
        assert ("c/d", "refused", "commit moved") in events
        assert ("a/b", "current", "") in events
        assert ("z/z", "unpublished", "") in events


class TestDownloadBytes:
    def test_only_download_steps_are_summed(self):
        steps = [{"tap": "a", "status": "download", "row": {"bytes": 10}},
                 {"tap": "b", "status": "current", "row": {"bytes": 1000}},
                 {"tap": "c", "status": "refused", "row": {"bytes": 1000}},
                 {"tap": "d", "status": "unpublished"},
                 {"tap": "e", "status": "download", "row": {"bytes": 5}}]
        assert shards.download_bytes(steps) == (15, 0)

    @pytest.mark.parametrize("size", [None, 0, -3, "big", 1.5])
    def test_a_row_without_a_usable_size_is_counted_not_summed(self, size):
        row = {} if size is None else {"bytes": size}
        steps = [{"tap": "a", "status": "download", "row": {"bytes": 7}},
                 {"tap": "b", "status": "download", "row": row}]
        assert shards.download_bytes(steps) == (7, 1)

    def test_nothing_to_download_weighs_nothing(self):
        assert shards.download_bytes([]) == (0, 0)


class _StreamedResponse:
    """A response whose ``read(amt)`` behaves like a socket, not like a file.

    Every other fixture in this file is a ``file:`` URL, where one ``read``
    returns the whole document — which is exactly why the suite could not see
    either failure this class reproduces. ``chunk`` caps how much any single
    read returns (a resumable short read); ``cut`` stops the body early and
    then reports EOF, the way a dropped connection does.
    """

    def __init__(self, body: bytes, chunk: int | None = None,
                 cut: int | None = None, headers: dict | None = None):
        self._body = body
        self._pos = 0
        self._chunk = chunk or len(body)
        self._cut = len(body) if cut is None else cut
        self.headers = ({"Content-Length": str(len(body))}
                        if headers is None else headers)

    def read(self, amt: int | None = None) -> bytes:
        if self._pos >= self._cut:
            return b""
        n = min(amt or len(self._body), self._chunk, self._cut - self._pos)
        out = self._body[self._pos:self._pos + n]
        self._pos += n
        return out

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _served(monkeypatch, **kw):
    """Serve a well-formed manifest through a streamed response."""
    body = json.dumps({"version": 1, **SPACE,
                       "shards": [{"tap": "a/b", "commit": "1" * 40,
                                   "url": "https://example.test/a.json",
                                   "sha256": "0" * 64}]}).encode()
    resp = _StreamedResponse(body, **kw)
    monkeypatch.setattr(shards, "_open", lambda url, timeout: resp)
    return body


class TestTruncatedManifest:
    """A body that arrives short must never be parsed as if it were whole.

    ``read(amt)`` returns *up to* amt bytes and performs no length check — that
    belongs to ``read()`` with no argument — so a single read left the JSON
    decoder to report a network artefact as "not valid JSON", pointing the user
    at a corrupt publish that does not exist.
    """

    def test_a_short_reading_stream_still_yields_the_whole_manifest(
            self, monkeypatch):
        """The loop: 32 bytes at a time must still assemble the document."""
        _served(monkeypatch, chunk=32)
        got = shards.fetch_manifest("https://example.test/m.json")
        assert got["provider"] == "local"
        assert len(got["shards"]) == 1

    def test_a_cut_stream_says_truncated_rather_than_invalid_json(
            self, monkeypatch):
        """The honest error names the network, not the publisher."""
        body = _served(monkeypatch, chunk=32, cut=40)
        with pytest.raises(BoostError) as err:
            shards.fetch_manifest("https://example.test/m.json")
        assert "truncated" in err.value.message
        # The real numbers, so the message can be acted on.
        assert "40 of %d" % len(body) in err.value.message

    def test_a_compressed_response_is_not_judged_by_content_length(
            self, monkeypatch):
        """Content-Length is the wire size; `raw` is the decoded body.

        Comparing the two behind a gzipping proxy would invent a truncation —
        the same class of bug the check exists to remove.
        """
        _served(monkeypatch, headers={"Content-Length": "999999",
                                      "Content-Encoding": "gzip"})
        got = shards.fetch_manifest("https://example.test/m.json")
        assert got["dim"] == 384

    def test_identity_encoding_is_still_checked(self, monkeypatch):
        """`identity` means unencoded, so the length still has to add up."""
        _served(monkeypatch, cut=40, headers={"Content-Length": "999999",
                                              "Content-Encoding": "identity"})
        with pytest.raises(BoostError, match="truncated"):
            shards.fetch_manifest("https://example.test/m.json")

    def test_no_content_length_is_not_a_truncation(self, monkeypatch):
        """An unanswerable question is left alone, not guessed at."""
        _served(monkeypatch, chunk=32, headers={})
        got = shards.fetch_manifest("https://example.test/m.json")
        assert got["version"] == 1

    def test_an_oversized_manifest_is_named_oversized_not_truncated(
            self, monkeypatch):
        """Order matters: too big is also 'shorter than declared'."""
        monkeypatch.setattr(shards, "MAX_MANIFEST_BYTES", 64)
        _served(monkeypatch, chunk=16)
        with pytest.raises(BoostError, match="implausibly large"):
            shards.fetch_manifest("https://example.test/m.json")


class TestStaleVersionStore:
    """A store from an older boost must be replaced, not INSERTed into.

    ``_ensure_schema`` is CREATE TABLE IF NOT EXISTS, so it cannot add a column
    to a table an older boost built. ``build`` has wiped on a version change
    since that bit it once; ``import_shard`` did not, so importing into a v2
    store failed per row with "table chunks has no column named digest" — a
    sqlite message about a column, where the honest answer is that the store
    predates this format. On a real machine that is one confusing failure per
    published shard.
    """

    def _v2_store(self, sandbox):
        """A store stamped with the previous index version."""
        from boost_cli.core import dense
        dense.db_path().parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(dense.db_path()))
        con.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
        # v2's `chunks` has no `digest` column — that is the whole point.
        con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    " name TEXT, tap TEXT, path TEXT, kind TEXT, cix INTEGER,"
                    " snip TEXT)")
        for k, v in (("version", "2"), ("provider", '"local"'),
                     ("model", '"BAAI/bge-small-en-v1.5"'), ("dim", "384")):
            con.execute("INSERT INTO meta (k, v) VALUES (?, ?)", (k, v))
        con.commit()
        con.close()

    def _plain_connect(self, monkeypatch):
        """Open the store without sqlite-vec.

        `_connect` loads the extension and returns None without it, so
        `import_shard` would exit at "no vector backend available" before
        reaching the decision under test. The decision itself is pure sqlite.
        Ubuntu and Windows runners carry the [rag] extra and macOS ones do not,
        so leaving this unpatched passes on two thirds of the matrix.
        """
        from boost_cli.core import dense
        monkeypatch.setattr(
            dense, "_connect",
            lambda: sqlite3.connect(str(dense.db_path())))

    def test_a_stale_version_store_is_replaced_rather_than_appended_to(
            self, sandbox, monkeypatch):
        from boost_cli.core import dense
        self._v2_store(sandbox)
        self._plain_connect(monkeypatch)
        wiped = []
        monkeypatch.setattr(dense, "_wipe", lambda con: wiped.append(1))
        # Stop after the wipe decision; the INSERT path needs sqlite-vec.
        monkeypatch.setattr(dense, "_ensure_schema",
                            lambda con, dim: (_ for _ in ()).throw(
                                _Stop()))
        with contextlib.suppress(_Stop):
            dense.import_shard({"tap": "a/b", "commit": "1" * 40,
                                "provider": "local",
                                "model": "BAAI/bge-small-en-v1.5",
                                "dim": 384, "chunks": []}, commit="1" * 40)
        assert wiped == [1]

    def test_a_matching_version_is_left_alone(self, sandbox, monkeypatch):
        """The wipe is for a format change, not for every import."""
        from boost_cli.core import dense
        self._v2_store(sandbox)
        con = sqlite3.connect(str(dense.db_path()))
        con.execute("UPDATE meta SET v = ? WHERE k = 'version'",
                    (str(dense.INDEX_VERSION),))
        con.commit()
        con.close()
        self._plain_connect(monkeypatch)
        wiped = []
        monkeypatch.setattr(dense, "_wipe", lambda con: wiped.append(1))
        monkeypatch.setattr(dense, "_ensure_schema",
                            lambda con, dim: (_ for _ in ()).throw(_Stop()))
        with contextlib.suppress(_Stop):
            dense.import_shard({"tap": "a/b", "commit": "1" * 40,
                                "provider": "local",
                                "model": "BAAI/bge-small-en-v1.5",
                                "dim": 384, "chunks": []}, commit="1" * 40)
        assert wiped == []


class _Stop(Exception):
    """Ends an import once the assertion's decision point has been reached."""


class TestReusableCommits:
    """What `dense.tap_commits` reports decides which taps `ingest` SKIPS.

    That makes a stale-version store's recorded commits actively dangerous:
    the store is about to be discarded — `build` wipes it and so does
    `import_shard` — so its rows are not vectors anyone can reuse. Reported as
    reusable, they let `ingest` skip 417 taps as "already current" and then
    wipe them on the first import, leaving a store silently missing them while
    the run reported success. Observed on a real 466-tap machine.
    """

    def _store(self, version):
        from boost_cli.core import dense
        dense.db_path().parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(dense.db_path()))
        con.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
        con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, tap TEXT)")
        con.execute("INSERT INTO meta (k, v) VALUES ('version', ?)",
                    (str(version),))
        con.execute("INSERT INTO meta (k, v) VALUES ('commits', ?)",
                    ('{"a__b": "%s"}' % ("1" * 40),))
        con.commit()
        con.close()

    def test_a_current_store_reports_what_it_holds(self, sandbox):
        from boost_cli.core import dense
        self._store(dense.INDEX_VERSION)
        assert dense.tap_commits() == {"a__b": "1" * 40}

    def test_a_stale_version_store_reports_nothing_reusable(self, sandbox):
        """Not the commits it recorded: those vectors are about to be wiped."""
        from boost_cli.core import dense
        self._store(dense.INDEX_VERSION - 1)
        assert dense.tap_commits() == {}
