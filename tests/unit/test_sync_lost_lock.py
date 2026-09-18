# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A lost lock file must make `boost sync` a repair, never an uninstaller.

Measured on the release before this fix: with the lock file deleted from an
otherwise intact install, `boost doctor` prescribed `boost sync` twice, and
running it removed every live, store-resolving agent link of the install —
four green ticks, no prompt, exit 0. `sync_plan` asked `link.name not in lock`
of `lockfile.installed()`, which collapses a missing lock into an empty record,
so "not recorded" read as "not installed".

The lock is authoritative only while it can vouch (`store.lock_vouches`). When
it cannot, nothing it lacks is stale or orphaned; when it is merely *missing*,
sync re-records the store from what is on disk.
"""
from __future__ import annotations

import json

import pytest

from boost_cli.core import catalog, journal, lockfile, paths, registry, store, util

LINKED = ["claude-code", "windsurf", "cursor", "antigravity"]


@pytest.fixture()
def installed(sandbox, fixture_tap_src):
    t = registry.add(str(fixture_tap_src))
    catalog.rebuild_tap(t)
    store.install(catalog.resolve_one("brainstorming"))
    return t


def _links(name="brainstorming"):
    return {a: store.agents.linking_agents()[a] / name for a in LINKED}


def _lose_lock():
    paths.lockfile_path().unlink()


def _corrupt_lock():
    paths.lockfile_path().write_text("{not json", encoding="utf-8")


class TestLockVouches:
    def test_a_parsing_lock_vouches(self, installed):
        assert store.lock_vouches()

    def test_a_missing_lock_over_an_empty_store_vouches(self, sandbox):
        """A fresh machine: nothing installed, nothing to disown."""
        assert not paths.lockfile_path().exists()
        assert store.lock_vouches()

    def test_a_missing_lock_over_a_populated_store_does_not(self, installed):
        _lose_lock()
        assert not store.lock_vouches()

    def test_a_corrupt_lock_does_not(self, installed):
        _corrupt_lock()
        assert not store.lock_vouches()

    def test_a_lock_in_another_schema_does_not(self, installed):
        data = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
        data["version"] = lockfile.SCHEMA_VERSION + 1
        paths.lockfile_path().write_text(json.dumps(data), encoding="utf-8")
        assert not store.lock_vouches()


class TestPlanWithoutAVouchingLock:
    @pytest.mark.parametrize("lose", [_lose_lock, _corrupt_lock])
    def test_live_links_into_the_store_are_not_stale(self, installed, lose):
        lose()
        assert store.sync_plan()["stale_links"] == []

    @pytest.mark.parametrize("lose", [_lose_lock, _corrupt_lock])
    def test_store_dirs_are_unrecorded_not_orphaned(self, installed, lose):
        """Orphans are what `--prune` deletes; an unrecorded dir never is."""
        lose()
        plan = store.sync_plan()
        assert plan["orphaned_store"] == []
        assert plan["unrecorded_store"] == ["brainstorming"]

    def test_a_broken_link_is_still_stale(self, installed):
        """Dangling is decided by the link alone, so the lock is not needed."""
        link = _links()["cursor"]
        link.unlink()
        link.symlink_to(paths.store_dir() / "gone")
        _lose_lock()
        assert store.sync_plan()["stale_links"] == [str(link)]

    def test_with_a_vouching_lock_an_unrecorded_dir_is_an_orphan(self, installed):
        (paths.store_dir() / "rogue").mkdir()
        plan = store.sync_plan()
        assert plan["orphaned_store"] == ["rogue"]
        assert plan["unrecorded_store"] == []

    def test_a_dot_dir_in_the_store_is_neither(self, installed):
        (paths.store_dir() / ".cache").mkdir()
        plan = store.sync_plan()
        assert ".cache" not in plan["orphaned_store"] + plan["unrecorded_store"]


class TestSyncApplyRecovers:
    def test_a_lost_lock_is_rebuilt_from_the_store_and_the_links_survive(
            self, installed):
        before = lockfile.get_skill("brainstorming")
        _lose_lock()
        actions = store.sync_apply(store.sync_plan())
        assert actions == ["re-recorded brainstorming from %s" % before["tap"]]
        for link in _links().values():
            assert link.is_symlink() and link.exists()
        after = lockfile.get_skill("brainstorming")
        for key in ("tap", "source_dir", "sha256", "version"):
            assert after[key] == before[key], key
        assert sorted(after["agents"]) == sorted(before["agents"])
        assert after["only_agents"] is None
        assert store.lock_vouches()

    def test_the_re_record_is_the_record_install_wrote(self, installed):
        """Every field, not a sample: a record missing `pinned` or `tags` reads
        back as a default today and as a KeyError in the next consumer."""
        stamps = ("installed_at", "updated_at")
        before = lockfile.get_skill("brainstorming")
        _lose_lock()
        store.sync_apply(store.sync_plan())
        after = lockfile.get_skill("brainstorming")
        assert after["installed_at"] and after["installed_at"] == after["updated_at"]
        assert ({k: v for k, v in after.items() if k not in stamps}
                == {k: v for k, v in before.items() if k not in stamps})

    def test_the_recovery_is_journaled(self, installed):
        _lose_lock()
        store.sync_apply(store.sync_plan())
        [event] = journal.events(action="recover")
        assert (event["subject"], event["how"]) == ("brainstorming", installed.name)

    def test_a_bare_catalog_entry_takes_install_defaults(self, installed, monkeypatch):
        """No `version` or `rel_dir` in the entry: the defaults `install` uses."""
        bare = {k: v for k, v in catalog.resolve_one("brainstorming").items()
                if k not in ("version", "rel_dir")}
        monkeypatch.setattr(catalog, "find", lambda n: [bare])
        same = util.sha256_dir(store.skill_store_dir("brainstorming"))
        monkeypatch.setattr(store, "_skill_source_sha", lambda _e: same)
        _lose_lock()
        store.sync_apply(store.sync_plan())
        entry = lockfile.get_skill("brainstorming")
        assert (entry["version"], entry["source_dir"]) == ("0.0.0", ".")

    def test_a_second_sync_changes_nothing(self, installed):
        _lose_lock()
        store.sync_apply(store.sync_plan())
        plan = store.sync_plan()
        assert not any(plan.values()), plan

    def test_an_edited_store_copy_is_kept_and_recorded_as_local(self, installed):
        """Reinstalling would have been the obvious repair, and it silently
        discards edits to the store copy."""
        skill_md = store.skill_store_dir("brainstorming") / "SKILL.md"
        skill_md.write_text(skill_md.read_text(encoding="utf-8") + "\n# mine\n",
                            encoding="utf-8")
        _lose_lock()
        [action] = store.sync_apply(store.sync_plan())
        assert action == (
            "re-recorded brainstorming as a local skill (its content matches no "
            "tapped source; `boost reinstall brainstorming` replaces it with a "
            "tap's copy)")
        assert "# mine" in skill_md.read_text(encoding="utf-8")
        entry = lockfile.get_skill("brainstorming")
        assert {k: entry[k] for k in ("version", "tap", "source_dir", "commit")} == {
            "version": "0.0.0", "tap": "local",
            "source_dir": str(store.skill_store_dir("brainstorming")), "commit": ""}
        assert entry["sha256"] == util.sha256_dir(store.skill_store_dir("brainstorming"))
        assert all(link.exists() for link in _links().values())

    def test_two_identical_sources_are_ambiguous_and_recorded_as_local(
            self, installed, monkeypatch):
        twin = dict(catalog.resolve_one("brainstorming"), tap="twin")
        real_find = catalog.find
        monkeypatch.setattr(catalog, "find", lambda n: [*real_find(n), twin])
        same = util.sha256_dir(store.skill_store_dir("brainstorming"))
        monkeypatch.setattr(store, "_skill_source_sha", lambda _e: same)
        _lose_lock()
        [action] = store.sync_apply(store.sync_plan())
        assert "matches more than one tapped source" in action

    def test_only_skill_entries_can_vouch_for_a_store_dir(
            self, installed, monkeypatch):
        """A rule of the same name is not a second source; an entry with no
        `kind` is a skill, as it is everywhere else in the catalog."""
        skill = {k: v for k, v in catalog.resolve_one("brainstorming").items()
                 if k != "kind"}
        rule = dict(skill, kind="rule", tap="rules")
        monkeypatch.setattr(catalog, "find", lambda n: [skill, rule])
        same = util.sha256_dir(store.skill_store_dir("brainstorming"))
        monkeypatch.setattr(store, "_skill_source_sha", lambda _e: same)
        _lose_lock()
        assert store.sync_apply(store.sync_plan()) == [
            "re-recorded brainstorming from %s" % installed.name]

    def test_a_narrowed_install_keeps_its_narrowing(self, installed):
        for agent in ("windsurf", "antigravity"):
            _links()[agent].unlink()
        _lose_lock()
        store.sync_apply(store.sync_plan())
        entry = lockfile.get_skill("brainstorming")
        assert entry["only_agents"] == ["claude-code", "cursor"]
        assert store.sync_plan()["missing_links"] == []

    def test_a_dir_without_skill_md_is_left_unrecorded(self, installed):
        gutted = paths.store_dir() / "gutted"
        gutted.mkdir()
        _lose_lock()
        actions = store.sync_apply(store.sync_plan())
        assert "left gutted unrecorded (no SKILL.md to record)" in actions
        assert lockfile.get_skill("gutted") is None

    def test_a_corrupt_lock_is_never_overwritten(self, installed):
        """`boost replay` restores a corrupt lock; sync must not paper over it."""
        _corrupt_lock()
        raw = paths.lockfile_path().read_text(encoding="utf-8")
        actions = store.sync_apply(store.sync_plan())
        assert actions == []
        assert paths.lockfile_path().read_text(encoding="utf-8") == raw
        assert all(link.exists() for link in _links().values())
