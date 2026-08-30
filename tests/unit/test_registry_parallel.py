# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`registry.add_many`: clone wide, write config once.

Tapping the catalog was 463 sequential clones. A clone is network latency —
measured at ~1.6 s whether one runs or twelve — so the wall time was 13 minutes
of waiting, and the fix is concurrency. What makes that unsafe is `add`'s tail:
`config.load()` -> append -> `config.save()` is read-modify-write on one JSON
file, so N threads doing it lose taps at random. `add_many` clones in a pool and
writes once, and these tests pin both halves.

The clone itself is faked here. What is being tested is the bookkeeping around
it — ordering, deduplication, failure isolation, and that exactly one config
write happens — none of which needs a real repository, and all of which would
be untestable at speed if it did.
"""
import threading

import pytest

from boost_cli.core import config, gitutil, policy, registry
from boost_cli.errors import BoostError


@pytest.fixture()
def fake_clone(monkeypatch):
    """Replace the network with a directory, and record concurrency."""
    state = {"live": 0, "peak": 0, "cloned": []}
    lock = threading.Lock()

    def clone(url, dest, sparse=True):
        with lock:
            state["live"] += 1
            state["peak"] = max(state["peak"], state["live"])
            state["cloned"].append(str(url))
        try:
            if "boom" in str(url):
                raise BoostError("clone failed: no such repo")
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "SKILL.md").write_text("---\nname: x\n---\nbody\n",
                                           encoding="utf-8")
        finally:
            with lock:
                state["live"] -= 1

    monkeypatch.setattr(gitutil, "clone_shallow", clone)
    monkeypatch.setattr(policy, "check_tap_signing", lambda path: [])
    return state


class TestAddMany:
    def test_every_tap_lands_in_one_config_write(self, sandbox, fake_clone,
                                                 monkeypatch):
        writes = []
        real_save = config.save
        monkeypatch.setattr(config, "save",
                            lambda cfg: (writes.append(1), real_save(cfg))[1])
        specs = ["o/a", "o/b", "o/c", "o/d"]
        res = registry.add_many(specs, jobs=4)
        assert [r["ok"] for r in res] == [True] * 4
        assert sorted(t.name for t in registry.list_taps()) == sorted(specs)
        # The point of the whole function: 4 clones, 1 write. Per-tap writes
        # would race and lose taps.
        assert writes == [1]

    def test_results_keep_the_order_they_were_asked_for(self, sandbox,
                                                        fake_clone):
        specs = ["o/z", "o/y", "o/x", "o/w"]
        res = registry.add_many(specs, jobs=4)
        # Completion order is whatever the network decides; output order is
        # not allowed to be.
        assert [r["name"] for r in res] == specs

    def test_one_failure_does_not_cost_the_others_their_clone(self, sandbox,
                                                              fake_clone):
        res = registry.add_many(["o/a", "o/boom", "o/c"], jobs=3)
        by_name = {r["name"]: r for r in res}
        assert by_name["o/boom"]["ok"] is False
        assert "no such repo" in by_name["o/boom"]["error"]
        assert by_name["o/a"]["ok"] and by_name["o/c"]["ok"]
        assert sorted(t.name for t in registry.list_taps()) == ["o/a", "o/c"]

    def test_a_failed_clone_leaves_no_directory_behind(self, sandbox,
                                                       fake_clone,
                                                       monkeypatch):
        # A half-clone that survives is worse than no clone: the next scan
        # indexes it as if it were a tap.
        def clone(url, dest, sparse=True):
            dest.mkdir(parents=True, exist_ok=True)
            raise BoostError("clone failed midway")

        monkeypatch.setattr(gitutil, "clone_shallow", clone)
        res = registry.add_many(["o/a"], jobs=1)
        assert res[0]["ok"] is False
        assert not (registry.Tap(name="o/a", url="u").path).exists()

    def test_an_already_tapped_registry_is_skipped_not_recloned(
            self, sandbox, fake_clone):
        registry.add_many(["o/a"], jobs=1)
        before = len(fake_clone["cloned"])
        res = registry.add_many(["o/a", "o/b"], jobs=2)
        assert res[0]["skipped"] is True
        assert len(fake_clone["cloned"]) == before + 1   # only o/b

    def test_a_repeated_spec_does_not_reorder_the_rest(self, sandbox,
                                                       fake_clone):
        # A dict comprehension over the specs keeps the LAST index for a
        # repeat, which moved that tap — and everything after it — out of the
        # order the caller asked for.
        res = registry.add_many(["o/z", "o/y", "o/x", "o/z"], jobs=4)
        assert [r["name"] for r in res] == ["o/z", "o/z", "o/y", "o/x"]
        assert res[0]["ok"] and res[1].get("skipped")

    def test_a_clone_that_never_made_its_directory_is_still_a_clean_failure(
            self, sandbox, monkeypatch):
        # `util.rmtree`'s read-only retry hook chmods the missing path and
        # raises FileNotFoundError, which out of a worker thread turns "this
        # registry 404'd" into a crashed catalog tap.
        monkeypatch.setattr(policy, "check_tap_signing", lambda path: [])

        def clone(url, dest, sparse=True):
            raise BoostError("repository not found")

        monkeypatch.setattr(gitutil, "clone_shallow", clone)
        res = registry.add_many(["o/a", "o/b"], jobs=2)
        assert [r["ok"] for r in res] == [False, False]
        assert "not found" in res[0]["error"]

    def test_the_same_spec_twice_is_cloned_once(self, sandbox, fake_clone):
        # Two threads cloning into one directory is a corrupt clone, not a
        # race worth debugging.
        res = registry.add_many(["o/a", "o/a"], jobs=2)
        assert [r.get("ok") for r in res].count(True) == 1
        assert fake_clone["cloned"].count("https://github.com/o/a") <= 1
        assert len([t for t in registry.list_taps() if t.name == "o/a"]) == 1

    def test_it_actually_runs_concurrently(self, sandbox, fake_clone):
        registry.add_many(["o/%d" % i for i in range(8)], jobs=4)
        # Without this the change is a refactor: 463 x 1.6 s stays 13 minutes.
        assert fake_clone["peak"] > 1

    def test_no_specs_is_no_work_and_no_write(self, sandbox, fake_clone):
        assert registry.add_many([], jobs=4) == []
        assert fake_clone["cloned"] == []

    def test_pins_are_applied_per_tap(self, sandbox, fake_clone, monkeypatch):
        seen = {}
        monkeypatch.setattr(gitutil, "checkout_commit",
                            lambda repo, sha: seen.__setitem__(repo.name, sha))
        registry.add_many(["o/a", "o/b"], pins={"o/b": "b" * 40}, jobs=2)
        assert seen == {"o__b": "b" * 40}

    def test_a_pin_that_fails_removes_that_tap_only(self, sandbox, fake_clone,
                                                    monkeypatch):
        def checkout(repo, sha):
            raise BoostError("not our ref")

        monkeypatch.setattr(gitutil, "checkout_commit", checkout)
        res = registry.add_many(["o/a", "o/b"], pins={"o/b": "b" * 40}, jobs=2)
        by_name = {r["name"]: r for r in res}
        assert by_name["o/a"]["ok"] and not by_name["o/b"]["ok"]
        assert [t.name for t in registry.list_taps()] == ["o/a"]


class TestAddManyEdges:
    """The branches a happy path never reaches."""

    def test_an_unparseable_spec_is_reported_not_raised(self, sandbox,
                                                        fake_clone):
        # One bad row in a catalog selection must not abort the other 462, and
        # the spec never reaches a worker: `parse_spec` rejects it up front.
        res = registry.add_many(["not a repo!!", "o/b"], jobs=2)
        assert res[0]["ok"] is False
        assert "cannot parse" in res[0]["error"]
        assert res[1]["ok"] is True

    def test_an_existing_directory_is_replaced_before_cloning(self, sandbox,
                                                              fake_clone):
        stale = registry.Tap(name="o/a", url="u").path
        stale.mkdir(parents=True, exist_ok=True)
        (stale / "leftover.md").write_text("old", encoding="utf-8")
        registry.add_many(["o/a"], jobs=1)
        assert not (stale / "leftover.md").exists()

    def test_a_tap_failing_policy_is_removed_and_reported(self, sandbox,
                                                          fake_clone,
                                                          monkeypatch):
        monkeypatch.setattr(policy, "check_tap_signing",
                            lambda path: ["unsigned commits"])
        res = registry.add_many(["o/a"], jobs=1)
        assert res[0]["ok"] is False
        assert "provenance policy" in res[0]["error"]
        assert not registry.Tap(name="o/a", url="u").path.exists()
        assert registry.list_taps() == []

    def test_cleanup_failure_does_not_mask_the_real_error(self, sandbox,
                                                          fake_clone,
                                                          monkeypatch):
        def explode(path):
            raise OSError("permission denied")

        monkeypatch.setattr(registry.util, "rmtree", explode)
        res = registry.add_many(["o/boom"], jobs=1)
        # The clone's own error is the one worth reporting.
        assert "no such repo" in res[0]["error"]

    def test_on_done_fires_once_per_cloned_tap(self, sandbox, fake_clone):
        seen = []
        registry.add_many(["o/a", "o/b"], jobs=2, on_done=lambda r: seen.append(r["name"]))
        assert sorted(seen) == ["o/a", "o/b"]


class TestTapJobs:
    """Concurrency is clamped: this is someone else's server."""

    def test_default_when_unasked(self, monkeypatch):
        monkeypatch.delenv("BOOST_TAP_JOBS", raising=False)
        assert registry.tap_jobs() == registry.DEFAULT_TAP_JOBS

    def test_the_env_override_is_honoured(self, monkeypatch):
        monkeypatch.setenv("BOOST_TAP_JOBS", "3")
        assert registry.tap_jobs() == 3

    def test_junk_in_the_env_falls_back_rather_than_crashing(self, monkeypatch):
        monkeypatch.setenv("BOOST_TAP_JOBS", "lots")
        assert registry.tap_jobs() == registry.DEFAULT_TAP_JOBS

    @pytest.mark.parametrize("asked,want", [(0, 1), (-5, 1), (999, 16)])
    def test_it_clamps_both_ends(self, asked, want):
        assert registry.tap_jobs(asked) == want
