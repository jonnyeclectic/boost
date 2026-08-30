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


class TestQuickstartCatalog:
    """`--catalog` is the "search everything" entry point."""

    def test_it_plans_every_catalogued_registry(self, boost):
        from boost_cli.core import config
        catalogued = [e for e in config.load_registry_catalog()
                      if not e.get("list_only")]
        res = boost("quickstart", "--catalog", "--dry-run")
        # Past a handful the dry run reports the shape: 463 lines of "would
        # tap" is a wall of text, not a preview.
        assert "would tap %d registries" % len(catalogued) in res.out

    def test_the_default_scope_is_still_the_seven_starters(self, boost):
        from boost_cli.core import config
        res = boost("quickstart", "--dry-run")
        for default in config.DEFAULT_TAPS:
            assert str(default["name"]) in res.out

    def test_catalog_scope_excludes_index_repos(self, boost):
        from boost_cli.core import config
        lists = [e for e in config.load_registry_catalog()
                 if e.get("list_only")]
        if not lists:
            pytest.skip("no list-only repos in the bundled catalogue")
        res = boost("quickstart", "--catalog", "--dry-run")
        total = len([e for e in config.load_registry_catalog()
                     if not e.get("list_only")])
        # An awesome-list repo indexes other repos and ships nothing of its
        # own, so tapping it for vectors buys nothing.
        assert "would tap %d registries" % total in res.out


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

    def test_zero_shards_says_why_it_is_zero(self, boost, monkeypatch):
        """"import 0 shard(s)" reads as "none are published".

        The cause here is local — no `rag` extra — and `--dry-run` is exactly
        what a cautious new user runs first, so the preview was the one surface
        that reported the symptom and withheld the reason. The live path
        already explains both cases.
        """
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "have_backend", lambda: False)
        out = _flat(boost("quickstart", "--dry-run").out)
        assert "import 0 shard(s)" in out
        assert "boost-skill-cli[rag]" in out
        # Named as the working default, not as a downgrade — BM25 is what
        # ships and what the required eval gate floors.
        assert "keyword search works without it" in out

    def test_no_vectors_is_reported_as_a_choice_not_a_gap(self, boost,
                                                          monkeypatch):
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "have_backend", lambda: True)
        out = _flat(boost("quickstart", "--dry-run", "--no-vectors").out)
        assert "import 0 shard(s)" in out
        assert "--no-vectors was asked for" in out
        # It must not blame the missing extra for a flag the user passed.
        assert "boost-skill-cli[rag]" not in out


def _flat(text: str) -> str:
    """Output with its wrapping collapsed.

    These lines go through ``out.info(..., wrap=True)``, which folds prose to
    the pane — so "keyword search is unaffected" arrives split across two lines
    and a naive substring assertion fails on formatting rather than on
    behaviour. Collapsing whitespace asserts the sentence, not the column it
    happened to break at.
    """
    return " ".join(text.split())


class TestEveryZeroShardReasonNamesItself:
    """All four branches, because a preview that reports a symptom without its
    reason is the defect — and three-quarters covered is three-quarters of the
    defect still shipped."""

    def test_an_unreadable_manifest_says_keyword_search_is_unaffected(
            self, boost, monkeypatch):
        from boost_cli.core import dense, shards
        from boost_cli.errors import BoostError

        def boom(*_a, **_k):
            raise BoostError("manifest unreachable")

        monkeypatch.setattr(dense, "have_backend", lambda: True)
        monkeypatch.setattr(shards, "fetch_manifest", boom)
        out = _flat(boost("quickstart", "--dry-run").out)
        assert "import 0 shard(s)" in out
        assert "the shard manifest could not be read" in out
        # The reassurance is the point: the tapping half still worked.
        assert "keyword search is unaffected" in out

    def test_a_manifest_with_no_matching_shard_says_so(self, boost,
                                                       monkeypatch):
        # The one branch where zero really does mean "none published for
        # these" — and it must not be worded like a local misconfiguration.
        from boost_cli.core import dense, shards
        monkeypatch.setattr(dense, "have_backend", lambda: True)
        monkeypatch.setattr(shards, "fetch_manifest", lambda *a, **k: {})
        monkeypatch.setattr(shards, "rows", lambda _m: {})
        out = _flat(boost("quickstart", "--dry-run").out)
        assert "import 0 shard(s)" in out
        assert "none of these registries have a published shard yet" in out
        assert "boost-skill-cli[rag]" not in out


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
