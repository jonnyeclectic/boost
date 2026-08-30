# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost quickstart` and `reindex --fetch-shards` end to end.

The behaviour worth pinning here is what these commands DON'T do, because both
failure modes are expensive rather than loud:

* quickstart must never start a multi-hour local embed on a user's behalf. It
  reports the taps with no published shard and leaves them alone.
* neither command may reach the network as a side effect of being asked what it
  would do. `--dry-run` taps nothing, and a machine with no embedding backend
  never fetches a manifest it could not use.

Every test here runs against the sandbox HOME and a manifest served from a
`file:` URL, so nothing in the suite depends on a release existing.
"""
from __future__ import annotations

import hashlib
import json

import pytest

SPACE = {"provider": "local", "model": "BAAI/bge-small-en-v1.5", "dim": 384}


@pytest.fixture()
def manifest(tmp_path, monkeypatch):
    """A published manifest with one shard, served from disk."""
    body = json.dumps({"tap": "a/b", "commit": "1" * 40, **SPACE,
                       "chunks": [{"name": "x", "embedding": "AAAA"}]})
    shard = tmp_path / "a__b.shard.json"
    shard.write_text(body, encoding="utf-8")
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({
        "version": 1, "generated": "2026-01-01T00:00:00Z", **SPACE,
        "shards": [{"tap": "a/b", "commit": "1" * 40, "chunks": 1,
                    "bytes": len(body.encode()),
                    "sha256": hashlib.sha256(body.encode()).hexdigest(),
                    "url": shard.as_uri()}]}), encoding="utf-8")
    monkeypatch.setenv("BOOST_SHARD_MANIFEST", path.as_uri())
    return path


class TestQuickstartDryRun:
    def test_dry_run_taps_nothing(self, boost, sandbox):
        res = boost("quickstart", "--dry-run")
        assert "would tap" in res.out
        # The proof it changed nothing: no clone, no config, no index.
        assert not (sandbox / ".boost" / "repos").exists()

    def test_dry_run_names_every_default_tap(self, boost):
        from boost_cli.core import config
        res = boost("quickstart", "--dry-run")
        for default in config.DEFAULT_TAPS:
            assert str(default["name"]) in res.out


class TestQuickstartWithoutTheExtra:
    """The default install: no `rag` extra, so no vectors and no fetch."""

    def test_it_does_not_fetch_a_manifest_it_could_not_use(self, boost,
                                                           monkeypatch):
        # Pointed at a URL that would fail loudly if it were opened.
        monkeypatch.setenv("BOOST_SHARD_MANIFEST",
                           "https://127.0.0.1:1/manifest.json")
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "have_backend", lambda: False)
        res = boost("quickstart", "--dry-run")
        assert "would tap" in res.out


class TestQuickstartTapping:
    """The real tap path, with the network replaced rather than the command."""

    @pytest.fixture()
    def fake_taps(self, monkeypatch):
        """`add_many` answers with one of each outcome, in order."""
        from boost_cli.core import catalog, config, registry

        class FakeTap:
            def __init__(self, name):
                self.name = name
                self.safe_name = name.replace("/", "__")

        names = [str(d["name"]) for d in config.DEFAULT_TAPS]
        calls = {}

        def add_many(urls, curated=False, pins=None, jobs=None, on_done=None):
            calls["pins"] = pins
            calls["urls"] = list(urls)
            out = []
            for i, name in enumerate(names):
                if i == 0:
                    out.append({"spec": name, "name": name, "ok": False,
                                "skipped": True, "error": "already tapped"})
                elif i == 1:
                    out.append({"spec": name, "name": name, "ok": False,
                                "error": "repository not found"})
                else:
                    out.append({"spec": name, "name": name, "ok": True,
                                "tap": FakeTap(name)})
            return out

        monkeypatch.setattr(registry, "add_many", add_many)
        monkeypatch.setattr(catalog, "rebuild_tap", lambda tap: [{"name": "x"}])
        monkeypatch.setattr("boost_cli.core.rag.build",
                            lambda *a, **k: {"entries": 3})
        return calls

    def test_it_reports_each_outcome_and_survives_a_bad_registry(
            self, boost, fake_taps):
        res = boost("quickstart", "--no-vectors")
        both = res.out + res.err
        assert "already tapped" in both
        # One registry failing must not stop the other six.
        assert "repository not found" in both
        assert both.count("tapped ") >= 2
        assert "ready" in both

    def test_shard_commits_are_passed_as_pins(self, boost, fake_taps,
                                              manifest, monkeypatch):
        from boost_cli.core import dense, embed, shards
        monkeypatch.setattr(dense, "have_backend", lambda: True)
        monkeypatch.setattr(embed, "provider", lambda: "local")
        monkeypatch.setattr(embed, "model", lambda: SPACE["model"])
        monkeypatch.setattr(embed, "dimension", lambda: 384)
        monkeypatch.setattr(shards, "sync",
                            lambda *a, **k: [])
        boost("quickstart")
        # The manifest names a/b, which is not a default tap, so no pin applies
        # — but the pins dict must still have been threaded through rather than
        # dropped, or a pinned registry would be tapped at HEAD.
        assert fake_taps["pins"] == {}

    def test_the_urls_tapped_are_the_default_registries(self, boost,
                                                        fake_taps):
        from boost_cli.core import config
        boost("quickstart", "--no-vectors")
        assert fake_taps["urls"] == [str(d["url"]) for d in config.DEFAULT_TAPS]


class TestFetchShards:
    def test_no_taps_is_a_clear_error_not_a_fetch(self, boost, manifest):
        res = boost("reindex", "--fetch-shards", expect=1)
        assert "no taps configured" in (res.out + res.err)

    def test_a_space_mismatch_is_refused_with_the_one_next_action(
            self, boost, fixture_tap_src, manifest, monkeypatch):
        boost("tap", str(fixture_tap_src))
        from boost_cli.core import embed
        monkeypatch.setattr(embed, "provider", lambda: "voyage")
        monkeypatch.setattr(embed, "model", lambda: "voyage-4")
        monkeypatch.setattr(embed, "dimension", lambda: 1024)
        res = boost("reindex", "--fetch-shards", expect=1)
        both = res.out + res.err
        # Named before any download: the 129 MB it did not spend is the point.
        assert "cannot serve this machine" in both
        assert "1024" in both or "voyage" in both

    def test_a_tap_with_no_published_shard_is_reported_not_embedded(
            self, boost, fixture_tap_src, manifest, monkeypatch):
        from boost_cli.core import embed
        monkeypatch.setattr(embed, "provider", lambda: "local")
        monkeypatch.setattr(embed, "model", lambda: SPACE["model"])
        monkeypatch.setattr(embed, "dimension", lambda: 384)
        boost("tap", str(fixture_tap_src))
        res = boost("reindex", "--fetch-shards")
        # Not a tick: nothing landed, and this user's vectors are still missing.
        assert "no published vectors" in (res.out + res.err)
        # The remedy is offered, never taken on the user's behalf.
        assert "reindex --dense" in res.out

    def test_json_output_lists_every_tap_and_its_status(
            self, boost, fixture_tap_src, manifest, monkeypatch):
        from boost_cli.core import embed
        monkeypatch.setattr(embed, "provider", lambda: "local")
        monkeypatch.setattr(embed, "model", lambda: SPACE["model"])
        monkeypatch.setattr(embed, "dimension", lambda: 384)
        boost("tap", str(fixture_tap_src))
        res = boost("reindex", "--fetch-shards", "--json")
        data = json.loads(res.out)
        assert [r["status"] for r in data["shards"]] == ["unpublished"]


class TestTapAt:
    """`--at` is what makes a shard importable; a bad pin must not tap HEAD."""

    def test_an_abbreviated_sha_is_refused(self, boost, fixture_tap_src):
        res = boost("tap", str(fixture_tap_src), "--at", "abc1234", expect=1)
        assert "full commit SHA" in (res.out + res.err)

    def test_at_without_a_spec_is_a_usage_error(self, boost):
        res = boost("tap", "--defaults", "--at", "a" * 40, expect=2)
        assert "SPEC" in (res.out + res.err)

    def test_a_real_pin_lands_the_tap_at_that_commit(self, boost,
                                                     fixture_tap_src):
        from boost_cli.core import gitutil, registry
        head = gitutil.head_commit(fixture_tap_src)
        boost("tap", str(fixture_tap_src), "--at", head)
        tap = registry.list_taps()[0]
        assert gitutil.head_commit(tap.path) == head

    def test_a_pin_that_cannot_be_honoured_leaves_no_tap_behind(
            self, boost, fixture_tap_src):
        from boost_cli.core import registry
        # A well-formed SHA that does not exist in the repo: the clone succeeds
        # and the checkout cannot, and a tap silently left on HEAD would have
        # every shard refused later for a reason three steps away.
        boost("tap", str(fixture_tap_src), "--at", "b" * 40, expect=1)
        assert registry.list_taps() == []
