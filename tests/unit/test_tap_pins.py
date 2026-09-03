# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A tap pin has to survive `boost update`, or it is not a pin.

`boost tap --at <sha>` checked a commit out and recorded nothing, so the next
`boost update` reset the clone to the default branch — verified before this
change against a two-commit fixture: tapped at `fb61736`, updated, `6206d22`.
That is not a cosmetic bug. A tap's commit is load-bearing for dense search:
`dense.build` marks a tap "reused" per commit and `import_shard` refuses a shard
built for a different one, so a clone that quietly moves leaves the vectors
imported for it stale *but present* — wrong rankings, no error, and a re-fetch
of the shard refused because the manifest's commit no longer matches.

So the pin lives in config.json beside the tap, `update` skips a pinned tap, and
`--force` is the one way past it — which also drops the pin, because deciding to
move a tap is deciding to stop holding it still.
"""
import time

import pytest

from boost_cli.core import config, gitutil, paths, policy, registry, util
from boost_cli.errors import BoostError

SHA = "a" * 40


@pytest.fixture()
def fake_clone(monkeypatch):
    """Clone without a network; record what was checked out."""
    state = {"checkouts": [], "pulls": []}

    def clone(url, dest, sparse=True):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "SKILL.md").write_text("---\nname: x\n---\nb\n", encoding="utf-8")

    def checkout(repo, sha):
        state["checkouts"].append((repo.name, sha))

    def pull(repo):
        state["pulls"].append(repo.name)
        return "1111111 → 2222222"

    monkeypatch.setattr(gitutil, "clone_shallow", clone)
    monkeypatch.setattr(gitutil, "checkout_commit", checkout)
    monkeypatch.setattr(gitutil, "pull", pull)
    monkeypatch.setattr(policy, "check_tap_signing", lambda path: [])
    return state


class TestPinIsRecorded:
    def test_tap_at_writes_the_pin_into_config(self, sandbox, fake_clone):
        registry.add("o/a", at=SHA)
        assert registry.list_taps()[0].pin == SHA
        rows = config.load()["taps"]
        assert rows[0]["pin"] == SHA

    def test_add_many_records_each_taps_own_pin(self, sandbox, fake_clone):
        registry.add_many(["o/a", "o/b"], pins={"o/b": SHA}, jobs=2)
        pins = {t.name: t.pin for t in registry.list_taps()}
        assert pins == {"o/a": "", "o/b": SHA}

    def test_an_unpinned_tap_records_nothing(self, sandbox, fake_clone):
        registry.add("o/a")
        assert "pin" not in config.load()["taps"][0]

    def test_a_config_written_before_pins_reads_as_unpinned(self, sandbox,
                                                            fake_clone):
        # Every existing install is this case; it must not raise or nag.
        cfg = config.load()
        cfg["taps"] = [{"name": "o/a", "url": "https://github.com/o/a"}]
        config.save(cfg)
        assert registry.list_taps()[0].pin == ""


class TestUpdateRespectsPins:
    def test_a_pinned_tap_is_skipped_and_says_so(self, sandbox, fake_clone):
        registry.add("o/a", at=SHA)
        results, failures = registry.update()
        assert failures == {}
        assert "pinned" in results["o/a"]
        # The clone is what must not move.
        assert fake_clone["pulls"] == []

    def test_pinned_and_unpinned_taps_coexist_in_one_sweep(self, sandbox,
                                                           fake_clone):
        registry.add("o/a", at=SHA)
        registry.add("o/b")
        results, _ = registry.update()
        assert "pinned" in results["o/a"]
        assert fake_clone["pulls"] == ["o__b"]

    def test_force_moves_a_pinned_tap_and_drops_the_pin(self, sandbox,
                                                        fake_clone):
        registry.add("o/a", at=SHA)
        results, _ = registry.update(force=True)
        assert "→" in results["o/a"]
        assert fake_clone["pulls"] == ["o__a"]
        # Deciding to move it is deciding to stop holding it still: a pin that
        # silently re-applied next run would make --force a one-shot lie.
        assert registry.list_taps()[0].pin == ""

    def test_pin_and_unpin_are_reversible(self, sandbox, fake_clone):
        registry.add("o/a")
        registry.pin("o/a", SHA)
        assert registry.list_taps()[0].pin == SHA
        registry.unpin("o/a")
        assert registry.list_taps()[0].pin == ""


class TestUpdateReclonesAMissingPinnedTap:
    """A pinned tap has nothing to hold still once its clone is gone, so
    skipping it — the old behaviour — reported "pinned … (skipped)" while
    leaving nothing on disk at all: `boost taps` kept naming a commit no
    clone described.
    """

    def test_recloned_at_its_pin_not_skipped(self, sandbox, fake_clone):
        registry.add("o/a", at=SHA)
        util.rmtree(registry.list_taps()[0].path)

        results, failures = registry.update()

        assert failures == {}
        assert results["o/a"] == "cloned at %s" % SHA[:7]
        assert registry.list_taps()[0].is_cloned
        # The pin survives — this is a reclone onto it, not a move off it.
        assert registry.list_taps()[0].pin == SHA
        assert fake_clone["checkouts"][-1] == ("o__a", SHA)

    def test_force_clones_at_head_and_drops_the_pin(self, sandbox, fake_clone):
        registry.add("o/a", at=SHA)
        util.rmtree(registry.list_taps()[0].path)

        results, failures = registry.update(force=True)

        assert failures == {}
        assert results["o/a"] == "cloned"
        assert registry.list_taps()[0].pin == ""
        # Only the checkout `add(at=SHA)` itself performed — force must not
        # land the fresh clone back on the pin it just dropped.
        assert fake_clone["checkouts"] == [("o__a", SHA)]

    def test_an_unhonourable_pin_leaves_no_half_clone(self, sandbox,
                                                      fake_clone, monkeypatch):
        registry.add("o/a", at=SHA)
        clone_path = registry.list_taps()[0].path
        util.rmtree(clone_path)

        def bad_checkout(repo, sha):
            raise BoostError("not our ref")

        monkeypatch.setattr(gitutil, "checkout_commit", bad_checkout)
        with pytest.raises(BoostError):
            registry.update("o/a")
        # A clone left on HEAD with the old pin still recorded would read as
        # cloned-and-current on the next sweep and never be retried.
        assert not clone_path.exists()
        assert registry.list_taps()[0].pin == SHA


class TestRefreshMarker:
    """One `stat`, so the search path can afford to ask."""

    def test_a_machine_that_never_refreshed_has_no_age(self, sandbox):
        # Not zero and not infinity: a fresh install must not nag on its first
        # search about a refresh it has had no chance to run.
        assert registry.refresh_age_days() is None

    def test_a_successful_sweep_stamps_the_marker(self, sandbox, fake_clone):
        registry.add("o/a")
        registry.update()
        assert registry.refresh_age_days() is not None
        assert registry.refresh_age_days() < 1

    def test_an_all_pinned_sweep_still_counts_as_refreshed(self, sandbox,
                                                           fake_clone):
        # "Refreshed" is about having asked. A user whose taps are all pinned
        # is not out of date, and should not be told they are.
        registry.add("o/a", at=SHA)
        registry.update()
        assert registry.refresh_age_days() is not None

    def test_a_sweep_with_no_taps_stamps_nothing(self, sandbox):
        registry.update()
        assert registry.refresh_age_days() is None

    def test_the_age_is_read_from_the_markers_mtime(self, sandbox, fake_clone):
        import os
        registry.add("o/a")
        registry.update()
        marker = paths.tap_refresh_marker()
        old = time.time() - 30 * 86400
        os.utime(marker, (old, old))
        assert 29.9 < registry.refresh_age_days() < 30.1

    def test_an_unreadable_marker_reads_as_unknown(self, sandbox, monkeypatch):
        def boom(self):
            raise OSError("nope")

        monkeypatch.setattr("pathlib.Path.stat", boom)
        assert registry.refresh_age_days() is None


class TestLastRefreshAt:
    """The ISO-string sibling of refresh_age_days, for `boost health`.

    A tap clone's own git log is the upstream's clock and never moves on a
    local sync — that mismatch is what made `boost health` claim a sync from
    minutes ago was weeks old. This is the same marker, in the shape
    ``util.rel_time`` expects, so a caller reporting "last tap sync" reads the
    local action rather than the tap's newest commit.
    """

    def test_a_machine_that_never_refreshed_has_no_timestamp(self, sandbox):
        assert registry.last_refresh_at() is None

    def test_a_successful_sweep_stamps_a_recent_timestamp(self, sandbox,
                                                           fake_clone):
        import time as time_mod
        from datetime import UTC, datetime

        registry.add("o/a")
        registry.update()
        stamped = registry.last_refresh_at()
        assert stamped is not None
        then = datetime.strptime(stamped, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        assert abs(time_mod.time() - then.timestamp()) < 5

    def test_the_timestamp_tracks_the_markers_mtime(self, sandbox, fake_clone):
        import os

        registry.add("o/a")
        registry.update()
        marker = paths.tap_refresh_marker()
        old = time.time() - 30 * 86400
        os.utime(marker, (old, old))
        stamped = registry.last_refresh_at()
        assert stamped == time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(old))

    def test_an_unreadable_marker_reads_as_unknown(self, sandbox, monkeypatch):
        def boom(self):
            raise OSError("nope")

        monkeypatch.setattr("pathlib.Path.stat", boom)
        assert registry.last_refresh_at() is None


class TestPinFailureStillCleansUp:
    def test_a_pin_that_cannot_be_honoured_leaves_no_tap(self, sandbox,
                                                         fake_clone,
                                                         monkeypatch):
        def checkout(repo, sha):
            raise BoostError("not our ref")

        monkeypatch.setattr(gitutil, "checkout_commit", checkout)
        with pytest.raises(BoostError):
            registry.add("o/a", at=SHA)
        # No tap, no clone, no config row: a tap silently left on HEAD would
        # have every shard for it refused later, three steps from the cause.
        assert registry.list_taps() == []
        assert not (paths.repos_dir() / "o__a").exists()
