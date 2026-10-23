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
        # A real clone has `.git`; without it `update` re-clones the dir.
        (dest / ".git").mkdir(exist_ok=True)
        (dest / "SKILL.md").write_text("---\nname: x\n---\nb\n", encoding="utf-8")

    def checkout(repo, sha, verify=None):
        state["checkouts"].append((repo.name, sha))

    def pull(repo, verify=None):
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
        # Checked out in the staging clone, before it replaces the tap dir,
        # so an unhonourable pin never costs the tree already there.
        assert fake_clone["checkouts"][-1] == ("o__a.boost-reclone", SHA)

    def test_force_clones_at_head_and_drops_the_pin(self, sandbox, fake_clone):
        registry.add("o/a", at=SHA)
        util.rmtree(registry.list_taps()[0].path)

        results, failures = registry.update(force=True)

        assert failures == {}
        # The dropped pin is reported, not silent — CLAUDE.md calls a silent
        # state change here "the failure that looks like nothing at all".
        assert results["o/a"] == "cloned (pin cleared)"
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

    def test_a_first_tap_starts_the_clock(self, sandbox, fake_clone):
        # `update` was the marker's only writer, so a machine that tapped and
        # never updated had none — and the stale-tap hint, the only line that
        # reports drift, could never fire for it. A clone is a refresh.
        registry.add("o/a")
        assert registry.refresh_age_days() is not None
        assert registry.refresh_age_days() < 1

    def test_add_many_starts_the_clock_too(self, sandbox, fake_clone):
        # The path `tap --defaults` and `quickstart` take.
        registry.add_many(["o/a", "o/b"])
        assert registry.refresh_age_days() is not None

    def test_a_later_tap_does_not_restart_it(self, sandbox, fake_clone):
        # Adding one tap does not refresh the ones already here, so an
        # existing stamp is left where it is.
        import os
        registry.add("o/a")
        old = time.time() - 30 * 86400
        os.utime(paths.tap_refresh_marker(), (old, old))
        registry.add("o/b")
        assert 29.9 < registry.refresh_age_days() < 30.1

    def test_a_tap_that_never_cloned_starts_nothing(self, sandbox,
                                                    monkeypatch):
        def boom(url, dest, sparse=True):
            raise BoostError("clone failed")

        monkeypatch.setattr(gitutil, "clone_shallow", boom)
        with pytest.raises(BoostError):
            registry.add("o/a")
        assert registry.refresh_age_days() is None

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


class TestEnsureClonedHonoursThePin:
    """`store.source_dir_for` re-clones a missing tap through this, so a
    read-only `boost drift` must not move a pinned tap onto HEAD."""

    def test_a_missing_pinned_clone_lands_on_its_pin(self, sandbox,
                                                     fake_clone):
        registry.add("o/a", at=SHA)
        tap = registry.list_taps()[0]
        util.rmtree(tap.path)
        fake_clone["checkouts"].clear()

        assert registry.ensure_cloned(tap) is True

        assert tap.is_cloned
        assert fake_clone["checkouts"] == [("o__a.boost-reclone", SHA)]
        assert registry.list_taps()[0].pin == SHA

    def test_an_unpinned_missing_clone_checks_nothing_out(self, sandbox,
                                                          fake_clone):
        registry.add("o/a")
        tap = registry.list_taps()[0]
        util.rmtree(tap.path)

        assert registry.ensure_cloned(tap) is True

        assert tap.is_cloned
        assert fake_clone["checkouts"] == []

    def test_a_present_clone_is_left_alone(self, sandbox, fake_clone,
                                           monkeypatch):
        registry.add("o/a", at=SHA)
        tap = registry.list_taps()[0]
        calls = []
        monkeypatch.setattr(gitutil, "clone_shallow",
                            lambda *a, **k: calls.append(a))

        assert registry.ensure_cloned(tap) is False

        assert calls == []


class TestOffPin:
    def _tap(self, pin=SHA):
        registry.add("o/a", at=pin or None)
        return registry.list_taps()[0]

    def test_head_elsewhere_is_reported(self, sandbox, fake_clone,
                                        monkeypatch):
        tap = self._tap()
        monkeypatch.setattr(gitutil, "head_commit", lambda repo: "b" * 40)
        assert registry.off_pin(tap) == "b" * 40

    def test_head_on_the_pin_is_none(self, sandbox, fake_clone, monkeypatch):
        tap = self._tap()
        monkeypatch.setattr(gitutil, "head_commit", lambda repo: SHA)
        assert registry.off_pin(tap) is None

    def test_case_of_the_hash_does_not_matter(self, sandbox, fake_clone,
                                              monkeypatch):
        tap = self._tap()
        monkeypatch.setattr(gitutil, "head_commit", lambda repo: SHA.upper())
        assert registry.off_pin(tap) is None

    def test_an_unreadable_head_is_not_evidence(self, sandbox, fake_clone,
                                                monkeypatch):
        tap = self._tap()
        monkeypatch.setattr(gitutil, "head_commit", lambda repo: "")
        assert registry.off_pin(tap) is None

    def test_no_git_is_not_evidence(self, sandbox, fake_clone, monkeypatch):
        tap = self._tap()
        monkeypatch.setattr(gitutil, "has_git", lambda: False)
        monkeypatch.setattr(gitutil, "head_commit", lambda repo: "b" * 40)
        assert registry.off_pin(tap) is None

    def test_an_unpinned_tap_is_never_off_pin(self, sandbox, fake_clone,
                                              monkeypatch):
        tap = self._tap(pin="")
        monkeypatch.setattr(gitutil, "head_commit", lambda repo: "b" * 40)
        assert registry.off_pin(tap) is None

    def test_a_missing_clone_is_not_off_pin(self, sandbox, fake_clone,
                                            monkeypatch):
        tap = self._tap()
        util.rmtree(tap.path)
        monkeypatch.setattr(gitutil, "head_commit", lambda repo: "b" * 40)
        assert registry.off_pin(tap) is None


class TestUpdateReturnsAnOffPinClone:
    def test_checks_the_pin_back_out_and_reports_a_move(self, sandbox,
                                                        fake_clone,
                                                        monkeypatch):
        registry.add("o/a", at=SHA)
        fake_clone["checkouts"].clear()
        monkeypatch.setattr(gitutil, "head_commit", lambda repo: "b" * 40)

        results, failures = registry.update()

        assert failures == {}
        assert results["o/a"] == "bbbbbbb → aaaaaaa (back on its pin)"
        assert fake_clone["checkouts"] == [("o__a", SHA)]
        assert fake_clone["pulls"] == []
        assert registry.list_taps()[0].pin == SHA

    def test_a_clone_on_its_pin_is_still_skipped(self, sandbox, fake_clone,
                                                 monkeypatch):
        registry.add("o/a", at=SHA)
        fake_clone["checkouts"].clear()
        monkeypatch.setattr(gitutil, "head_commit", lambda repo: SHA)

        results, _ = registry.update()

        assert results["o/a"] == "pinned at aaaaaaa (skipped)"
        assert fake_clone["checkouts"] == []


class TestPinGoneUpstream:
    """git's "not our ref" becomes the pin, the remote and a remedy that works."""

    URL = "https://github.com/o/a"

    def _gone(self, monkeypatch, seen=None):
        def checkout(repo, sha, verify=None):
            if seen is not None:
                seen.append(sha)
            raise gitutil.CommitNotUpstream(sha, self.URL)
        monkeypatch.setattr(gitutil, "checkout_commit", checkout)

    def test_pin_missing_names_tap_pin_remote_and_force(self):
        tap = registry.Tap(name="o/a", url=self.URL)
        err = registry.pin_missing(tap, SHA)
        assert err.message == ("tap o/a is pinned at aaaaaaa, which is no "
                               "longer on https://github.com/o/a (history "
                               "rewritten upstream?)")
        assert err.hint == registry.pin_missing_remedy("o/a") == (
            "`boost update --force o/a` re-clones its default branch and "
            "drops the pin, or re-tap it with `--at <sha>` to pin a commit "
            "that exists there")
        assert registry.PIN_MISSING in err.message
        assert "untap" not in err.message + err.hint
        assert registry.pin_missing(tap, SHA, "/elsewhere").message.endswith(
            "no longer on /elsewhere (history rewritten upstream?)")

    def test_a_named_update_of_an_uncloned_tap_raises_it(
            self, sandbox, fake_clone, monkeypatch):
        registry.add("o/a", at=SHA)
        util.rmtree(registry.list_taps()[0].path)
        self._gone(monkeypatch)
        with pytest.raises(BoostError) as ei:
            registry.update("o/a")
        assert ei.value.message == registry.pin_missing(
            registry.get("o/a"), SHA).message
        assert ei.value.hint == registry.pin_missing_remedy("o/a")
        assert registry.list_taps()[0].pin == SHA

    def test_a_sweep_collects_it_with_the_marker(self, sandbox, fake_clone,
                                                 monkeypatch):
        registry.add("o/a", at=SHA)
        util.rmtree(registry.list_taps()[0].path)
        self._gone(monkeypatch)
        results, failures = registry.update()
        assert "o/a" not in results
        assert registry.PIN_MISSING in failures["o/a"]

    def test_an_off_pin_clone_whose_pin_is_gone_raises_it(
            self, sandbox, fake_clone, monkeypatch):
        registry.add("o/a", at=SHA)
        monkeypatch.setattr(gitutil, "head_commit", lambda p: "b" * 40)
        seen: list = []
        self._gone(monkeypatch, seen)
        with pytest.raises(BoostError) as ei:
            registry.update("o/a")
        assert seen == [SHA]
        assert ei.value.message.startswith(
            "tap o/a is pinned at aaaaaaa, which is no longer on ")
        assert ei.value.hint == registry.pin_missing_remedy("o/a")
