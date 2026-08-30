# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The CLI surface of tap pins and tap freshness.

Three commands have to agree about a pinned tap: `boost taps` shows it as a
commit rather than a date, `boost update` skips it, and `boost update --force`
is the one way past — which drops the pin, because choosing to move a tap is
choosing to stop holding it still.

The freshness hint is here too, because what it must NOT do is the testable
part: `boost search` never refreshes a tap. It reads one mtime and prints one
line, so a search stays a sub-second local operation and a machine that has
never refreshed says nothing at all.
"""
from __future__ import annotations

import os
import subprocess
import time

import pytest


@pytest.fixture()
def two_commit_tap(tmp_path):
    """A local fixture repo with a second commit to move to."""
    import sys
    from pathlib import Path

    src = tmp_path / "reg"
    subprocess.run([sys.executable,
                    str(Path(__file__).resolve().parents[1] / "make_fixture.py"),
                    str(src)], check=True, capture_output=True)

    def sha(rev="HEAD"):
        return subprocess.run(["git", "-C", str(src), "rev-parse", rev],
                              check=True, capture_output=True,
                              text=True).stdout.strip()

    first = sha()
    (src / "extra.md").write_text("more\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(src), "add", "-A"], check=True,
                   capture_output=True)
    subprocess.run(["git", "-C", str(src), "-c", "user.email=t@t",
                    "-c", "user.name=t", "commit", "-qm", "second"],
                   check=True, capture_output=True)
    return src, first, sha()


class TestPinnedTapSurvivesUpdate:
    def test_taps_shows_the_pin_instead_of_a_date(self, boost, two_commit_tap):
        src, first, _second = two_commit_tap
        boost("tap", str(src), "--at", first)
        res = boost("taps")
        assert "@%s" % first[:7] in res.out

    def test_update_skips_a_pinned_tap(self, boost, two_commit_tap):
        from boost_cli.core import gitutil, registry
        src, first, _second = two_commit_tap
        boost("tap", str(src), "--at", first)
        res = boost("update", "--taps-only")
        assert "pinned" in res.out
        # The clone is the thing that must not move: stale-but-present vectors
        # are the failure this prevents.
        assert gitutil.head_commit(registry.list_taps()[0].path) == first

    def test_force_moves_it_and_clears_the_pin(self, boost, two_commit_tap):
        from boost_cli.core import gitutil, registry
        src, first, second = two_commit_tap
        boost("tap", str(src), "--at", first)
        boost("update", "--taps-only", "--force")
        tap = registry.list_taps()[0]
        assert gitutil.head_commit(tap.path) == second
        assert tap.pin == ""

    def test_json_output_carries_the_pin(self, boost, two_commit_tap):
        import json
        src, first, _second = two_commit_tap
        boost("tap", str(src), "--at", first)
        assert json.loads(boost("taps", "--json").out)[0]["pin"] == first


class TestVectorsResyncWhenATapMoves:
    """A moved tap invalidates its vectors; boost has to notice out loud."""

    @pytest.fixture()
    def moved(self, boost, two_commit_tap):
        src, first, second = two_commit_tap
        boost("tap", str(src), "--at", first)
        return second

    def test_nothing_is_said_when_no_vectors_exist(self, boost, moved,
                                                   monkeypatch):
        from boost_cli.core import dense, shards

        def forbidden(*a, **k):
            raise AssertionError("must not reach the manifest with no store")

        monkeypatch.setattr(dense, "ready", lambda: False)
        monkeypatch.setattr(shards, "fetch_manifest", forbidden)
        res = boost("update", "--taps-only", "--force")
        assert "stale" not in res.out

    def test_a_newer_shard_is_imported_for_the_new_commit(self, boost, moved,
                                                          monkeypatch):
        from boost_cli.core import dense, shards
        seen = {}

        def sync(taps, commits, manifest=None, cache_dir=None, on_event=None):
            seen["taps"] = list(taps)
            seen["commits"] = dict(commits)
            return [{"tap": t, "status": "imported", "detail": "ok",
                     "chunks": 5} for t in taps]

        monkeypatch.setattr(dense, "ready", lambda: True)
        monkeypatch.setattr(shards, "fetch_manifest", lambda *a, **k: {
            "version": 1, "provider": "local", "model": "m", "dim": 384,
            "shards": [], "_url": "file:///x"})
        monkeypatch.setattr(shards, "sync", sync)
        res = boost("update", "--taps-only", "--force")
        assert "re-imported prebuilt vectors" in res.out
        # The commit handed to sync must be where the tap landed, not where it
        # was: a shard is only importable against the tree it describes.
        assert list(seen["commits"].values()) == [moved]

    def test_no_matching_shard_says_the_vectors_are_stale(self, boost, moved,
                                                          monkeypatch):
        from boost_cli.core import dense, shards
        monkeypatch.setattr(dense, "ready", lambda: True)
        monkeypatch.setattr(shards, "fetch_manifest", lambda *a, **k: {
            "version": 1, "provider": "local", "model": "m", "dim": 384,
            "shards": [], "_url": "file:///x"})
        monkeypatch.setattr(shards, "sync", lambda *a, **k: [
            {"tap": "x", "status": "refused", "detail": "commit moved"}])
        res = boost("update", "--taps-only", "--force")
        assert "no matching shard" in res.out
        assert "reindex --dense" in res.out

    def test_an_unreachable_manifest_still_reports_the_staleness(
            self, boost, moved, monkeypatch):
        from boost_cli.core import dense, shards
        from boost_cli.errors import BoostError

        def offline(*a, **k):
            raise BoostError("cannot reach the manifest")

        monkeypatch.setattr(dense, "ready", lambda: True)
        monkeypatch.setattr(shards, "fetch_manifest", offline)
        res = boost("update", "--taps-only", "--force")
        # Offline is not a reason to let stale vectors pass unmentioned.
        assert "stale" in res.out


class TestStaleTapHint:
    def _age_marker(self, days):
        from boost_cli.core import paths
        marker = paths.tap_refresh_marker()
        when = time.time() - days * 86400
        os.utime(marker, (when, when))

    def test_a_fresh_install_says_nothing(self, boost, fixture_tap_src):
        boost("tap", str(fixture_tap_src))
        res = boost("search", "alpha")
        assert "last refreshed" not in res.out

    def test_old_taps_are_mentioned_once(self, boost, fixture_tap_src):
        boost("tap", str(fixture_tap_src))
        boost("update", "--taps-only")
        self._age_marker(30)
        res = boost("search", "alpha")
        assert "taps last refreshed 30 days ago" in res.out
        assert res.out.count("last refreshed") == 1

    def test_it_is_mentioned_on_an_empty_result_too(self, boost,
                                                    fixture_tap_src):
        # "No matches" is exactly what an out-of-date tap set produces, and the
        # user has no other way to suspect it.
        boost("tap", str(fixture_tap_src))
        boost("update", "--taps-only")
        self._age_marker(30)
        res = boost("search", "zzzznothinghere")
        assert "taps last refreshed" in res.out

    def test_a_recent_refresh_is_not_mentioned(self, boost, fixture_tap_src):
        boost("tap", str(fixture_tap_src))
        boost("update", "--taps-only")
        self._age_marker(3)
        assert "last refreshed" not in boost("search", "alpha").out

    def test_search_never_fetches_a_tap(self, boost, fixture_tap_src,
                                        monkeypatch):
        from boost_cli.core import gitutil
        boost("tap", str(fixture_tap_src))
        boost("update", "--taps-only")
        self._age_marker(30)

        def forbidden(*a, **k):
            raise AssertionError("search must not touch the network")

        monkeypatch.setattr(gitutil, "pull", forbidden)
        monkeypatch.setattr(gitutil, "clone_shallow", forbidden)
        # The hint says it; it does not do it. Refreshing here would turn a
        # sub-second command into minutes and would strand imported shards.
        assert "taps last refreshed" in boost("search", "alpha").out
