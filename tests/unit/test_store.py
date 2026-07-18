"""Unit tests: boost_cli/core/store.py — install/uninstall/link/sync (no CLI)."""
from __future__ import annotations

import re
import shutil

import pytest

from boost_cli.core import (catalog, journal, lockfile, paths,
                           policy, registry, store, util)
from boost_cli.errors import BoostError

ISO = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
AGENT_DIRS = {"claude-code": ".claude", "windsurf": ".windsurf", "cursor": ".cursor"}


def _link(agent):
    return paths.home() / AGENT_DIRS[agent] / "skills" / "brainstorming"


@pytest.fixture()
def tap(sandbox, fixture_tap_src):
    t = registry.add(str(fixture_tap_src))
    catalog.rebuild_tap(t)
    return t


@pytest.fixture()
def entry(tap):
    return catalog.resolve_one("brainstorming")


@pytest.fixture()
def brainstorming(entry):
    store.install(entry)
    return entry


class TestInstall:
    def test_happy_path(self, tap, entry):
        src = tap.path / "skills" / "brainstorming"
        (src / ".git").mkdir()
        (src / ".git" / "config").write_text("junk")
        (src / "__pycache__").mkdir()
        (src / "__pycache__" / "x.pyc").write_text("junk")
        (src / ".DS_Store").write_text("junk")

        res = store.install(entry)

        dest = paths.store_dir() / "brainstorming"
        assert res.name == "brainstorming"
        assert res.dest == dest
        assert res.linked == ["claude-code", "windsurf", "cursor"]
        assert res.conflicts == []
        assert res.upgraded is False
        assert res.score == 95
        assert (dest / "SKILL.md").is_file()
        assert not (dest / ".git").exists()
        assert not (dest / "__pycache__").exists()
        assert not (dest / ".DS_Store").exists()
        for agent in AGENT_DIRS:
            link = _link(agent)
            assert link.is_symlink()
            assert link.resolve() == dest.resolve()

        e = lockfile.get_skill("brainstorming")
        assert e["version"] == "1.4.0"
        assert e["tap"] == "fixture-tap"
        assert e["source_dir"] == "skills/brainstorming"
        assert re.fullmatch(r"[0-9a-f]{40}", e["commit"])
        assert re.fullmatch(r"[0-9a-f]{64}", e["sha256"])
        assert e["sha256"] == util.sha256_dir(dest)
        assert re.fullmatch(ISO, e["installed_at"])
        assert e["updated_at"] == e["installed_at"]
        assert e["pinned"] is False
        assert e["quarantined"] is False
        assert e["agents"] == ["claude-code", "windsurf", "cursor"]
        assert e["tags"] == []

        ev = journal.events(action="install")[0]
        assert ev["subject"] == "brainstorming"
        assert ev["tap"] == "fixture-tap"
        assert ev["version"] == "1.4.0"

    def test_installed_passthrough(self, brainstorming):
        assert set(store.installed()) == {"brainstorming"}

    def test_duplicate_raises_with_reinstall_hint(self, brainstorming, entry):
        with pytest.raises(BoostError) as ei:
            store.install(entry)
        assert ei.value.message == "brainstorming is already installed (v1.4.0)"
        assert ei.value.hint == (
            "`boost reinstall brainstorming` to force, `boost update` to upgrade")

    def test_force_upgrades_preserving_installed_at_and_tags(self, brainstorming, entry):
        e = lockfile.get_skill("brainstorming")
        e["tags"] = ["keeper"]
        e["pinned"] = True
        lockfile.set_skill("brainstorming", e)
        orig_at = e["installed_at"]

        res = store.install(entry, force=True)
        assert res.upgraded is True
        e2 = lockfile.get_skill("brainstorming")
        assert e2["installed_at"] == orig_at
        assert e2["tags"] == ["keeper"]
        assert e2["pinned"] is True

    def test_pinned_reinstall_raises(self, brainstorming, entry):
        e = lockfile.get_skill("brainstorming")
        e["pinned"] = True
        lockfile.set_skill("brainstorming", e)
        with pytest.raises(BoostError):
            store.install(entry)

    def test_pinned_error_mentions_pin(self, brainstorming, entry):
        e = lockfile.get_skill("brainstorming")
        e["pinned"] = True
        lockfile.set_skill("brainstorming", e)
        with pytest.raises(BoostError) as ei:
            store.install(entry)
        assert "pinned" in ei.value.message

    def test_policy_block_then_restore(self, tap, entry):
        policy.save({"blocked_skills": ["brainstorming"]})
        with pytest.raises(BoostError) as ei:
            store.install(entry)
        assert ei.value.message == ("policy blocks installing brainstorming: "
                                    "skill 'brainstorming' is on the blocklist")
        assert ei.value.hint == "inspect with `boost policy list`"
        assert lockfile.get_skill("brainstorming") is None

        policy.save({})
        store.install(entry)
        assert (paths.store_dir() / "brainstorming" / "SKILL.md").is_file()

    def test_only_agents_links_subset(self, tap, entry):
        res = store.install(entry, only_agents=["claude-code"])
        assert res.linked == ["claude-code"]
        assert _link("claude-code").is_symlink()
        assert not _link("windsurf").exists()
        assert not _link("cursor").exists()
        assert lockfile.get_skill("brainstorming")["agents"] == ["claude-code"]

    def test_preexisting_real_dir_is_conflict_not_clobbered(self, tap, entry):
        blocker = _link("claude-code")
        blocker.mkdir(parents=True)
        (blocker / "precious.txt").write_text("mine")

        res = store.install(entry)
        assert res.conflicts == [str(blocker)]
        assert res.linked == ["windsurf", "cursor"]
        assert not blocker.is_symlink()
        assert (blocker / "precious.txt").read_text() == "mine"
        assert lockfile.get_skill("brainstorming")["agents"] == ["windsurf", "cursor"]

    def test_source_vanished_raises(self, tap, entry):
        shutil.rmtree(tap.path / "skills" / "brainstorming")
        with pytest.raises(BoostError) as ei:
            store.install(entry)
        assert ei.value.message == (
            "source for brainstorming vanished from tap fixture-tap")
        assert ei.value.hint == "run `boost update fixture-tap`"


class TestUnlinkAgents:
    def test_removes_only_symlinks(self, brainstorming):
        cursor_link = _link("cursor")
        cursor_link.unlink()
        cursor_link.mkdir()
        removed = store.unlink_agents("brainstorming")
        assert removed == ["claude-code", "windsurf"]
        assert cursor_link.is_dir()
        assert not _link("claude-code").exists()
        assert not _link("windsurf").exists()


class TestInstallFromPath:
    def _src(self, tmp_path, fm, extras=True):
        src = tmp_path / "dir-name-skill"
        src.mkdir()
        (src / "SKILL.md").write_text(fm + "\n\n# Title\n\nBody line\n")
        if extras:
            (src / "notes.txt").write_text("extra")
            (src / ".git").mkdir()
            (src / ".git" / "HEAD").write_text("ref")
            (src / "__pycache__").mkdir()
            (src / "__pycache__" / "x.pyc").write_text("junk")
        return src

    def test_name_from_frontmatter(self, sandbox, tmp_path):
        src = self._src(tmp_path, "---\nname: imported-skill\nversion: 9.9.9\n---")
        res = store.install_from_path(src)
        assert res.name == "imported-skill"
        dest = paths.store_dir() / "imported-skill"
        assert (dest / "SKILL.md").is_file()
        assert (dest / "notes.txt").is_file()
        assert not (dest / ".git").exists()
        assert not (dest / "__pycache__").exists()
        e = lockfile.get_skill("imported-skill")
        assert e["version"] == "9.9.9"
        assert e["tap"] == "local"
        assert e["source_dir"] == str(src)
        assert e["commit"] == ""
        assert e["pinned"] is False
        assert e["agents"] == ["claude-code", "windsurf", "cursor"]

    def test_name_falls_back_to_dirname(self, sandbox, tmp_path):
        src = self._src(tmp_path, "---\nversion: 1.0\n---", extras=False)
        res = store.install_from_path(src)
        assert res.name == "dir-name-skill"
        assert lockfile.get_skill("dir-name-skill")["version"] == "1.0"

    def test_explicit_name_wins(self, sandbox, tmp_path):
        src = self._src(tmp_path, "---\nname: meta-name\n---", extras=False)
        res = store.install_from_path(src, name="override", tap_label="team")
        assert res.name == "override"
        e = lockfile.get_skill("override")
        assert e["tap"] == "team"
        assert e["version"] == "0.0.0"

    def test_missing_skill_md_raises(self, sandbox, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(BoostError) as ei:
            store.install_from_path(empty)
        assert ei.value.message == "%s has no SKILL.md" % empty


class TestUninstall:
    def test_uninstall_removes_everything(self, brainstorming):
        result = store.uninstall("brainstorming")
        assert result["name"] == "brainstorming"
        assert result["unlinked"] == ["claude-code", "windsurf", "cursor"]
        assert result["entry"]["version"] == "1.4.0"
        assert not (paths.store_dir() / "brainstorming").exists()
        for agent in AGENT_DIRS:
            assert not _link(agent).exists()
        assert lockfile.get_skill("brainstorming") is None

    def test_uninstall_missing_raises(self, sandbox):
        with pytest.raises(BoostError) as ei:
            store.uninstall("ghost")
        assert ei.value.message == "ghost is not installed"
        assert ei.value.hint == "see what is with `boost list`"


class TestSyncPlan:
    EMPTY = {"missing_store": [], "missing_links": [],
             "stale_links": [], "orphaned_store": []}

    def test_clean_state_empty_plan(self, brainstorming):
        assert store.sync_plan() == self.EMPTY

    def test_missing_links(self, brainstorming):
        _link("windsurf").unlink()
        plan = store.sync_plan()
        assert plan == {**self.EMPTY,
                        "missing_links": [("brainstorming", "windsurf")]}

    def test_quarantined_excluded_from_missing_links(self, brainstorming):
        e = lockfile.get_skill("brainstorming")
        e["quarantined"] = True
        lockfile.set_skill("brainstorming", e)
        for agent in AGENT_DIRS:
            _link(agent).unlink()
        assert store.sync_plan() == self.EMPTY

    def test_stale_dangling_symlink(self, brainstorming):
        ghost = paths.home() / ".claude" / "skills" / "ghost"
        ghost.symlink_to(paths.store_dir() / "ghost")   # target missing
        plan = store.sync_plan()
        assert plan == {**self.EMPTY, "stale_links": [str(ghost)]}

    def test_unmanaged_link_into_store_is_stale(self, brainstorming):
        orphan_store = paths.store_dir() / "orphan"
        orphan_store.mkdir()
        (orphan_store / "f.txt").write_text("x")
        link = paths.home() / ".cursor" / "skills" / "orphan"
        link.symlink_to(orphan_store)
        plan = store.sync_plan()
        assert plan["stale_links"] == [str(link)]
        assert plan["orphaned_store"] == ["orphan"]

    def test_valid_symlink_outside_store_not_stale(self, brainstorming):
        target = paths.home() / "elsewhere"
        target.mkdir()
        link = paths.home() / ".claude" / "skills" / "external"
        link.symlink_to(target)
        assert store.sync_plan() == self.EMPTY

    def test_orphaned_store_dir(self, brainstorming):
        rogue = paths.store_dir() / "rogue"
        rogue.mkdir()
        (paths.store_dir() / "stray.txt").write_text("not a dir")
        plan = store.sync_plan()
        assert plan == {**self.EMPTY, "orphaned_store": ["rogue"]}

    def test_missing_agent_dir_reports_missing_links_not_stale(self, tap, entry):
        # only claude-code was linked, so the other agent dirs were never
        # created — sync still wants links there, and the stale-link scan
        # skips the nonexistent dirs.
        store.install(entry, only_agents=["claude-code"])
        assert not (paths.home() / ".windsurf" / "skills").exists()
        plan = store.sync_plan()
        assert plan == {**self.EMPTY, "missing_links": [
            ("brainstorming", "windsurf"), ("brainstorming", "cursor")]}

    def test_missing_store(self, brainstorming):
        shutil.rmtree(paths.store_dir() / "brainstorming")
        plan = store.sync_plan()
        assert plan["missing_store"] == ["brainstorming"]
        assert plan["missing_links"] == []          # skipped via continue
        assert plan["orphaned_store"] == []
        assert sorted(plan["stale_links"]) == sorted(
            str(_link(a)) for a in AGENT_DIRS)       # links now dangle


class TestSyncApply:
    def test_repairs_missing_link(self, brainstorming):
        _link("windsurf").unlink()
        actions = store.sync_apply(store.sync_plan())
        assert actions == ["linked brainstorming → windsurf"]
        assert _link("windsurf").is_symlink()

    def test_removes_stale_link(self, brainstorming):
        ghost = paths.home() / ".claude" / "skills" / "ghost"
        ghost.symlink_to(paths.store_dir() / "ghost")
        actions = store.sync_apply(store.sync_plan())
        assert actions == ["removed stale link %s" % ghost]
        assert not ghost.is_symlink()

    def test_missing_store_reinstalled_from_tap(self, brainstorming):
        shutil.rmtree(paths.store_dir() / "brainstorming")
        actions = store.sync_apply(store.sync_plan())
        assert len(actions) == 4                     # 3 stale links + reinstall
        assert actions[-1] == "reinstalled missing brainstorming from fixture-tap"
        assert (paths.store_dir() / "brainstorming" / "SKILL.md").is_file()
        assert lockfile.get_skill("brainstorming") is not None
        for agent in AGENT_DIRS:
            assert _link(agent).is_symlink()

    def test_missing_store_reinstall_fails_falls_back_to_drop(self, tap, brainstorming):
        # catalog cache still lists the skill, but its source dir vanished
        # from the tap clone: the reinstall attempt raises and is swallowed,
        # then the entry is dropped from the lock.
        shutil.rmtree(paths.store_dir() / "brainstorming")
        shutil.rmtree(tap.path / "skills" / "brainstorming")
        actions = store.sync_apply(store.sync_plan())
        assert ("dropped brainstorming from lock (store dir missing, source gone)"
                in actions)
        assert not any(a.startswith("reinstalled") for a in actions)
        assert lockfile.get_skill("brainstorming") is None

    def test_missing_store_tap_gone_dropped_from_lock(self, brainstorming):
        registry.remove("fixture-tap")
        shutil.rmtree(paths.store_dir() / "brainstorming")
        actions = store.sync_apply(store.sync_plan())
        assert ("dropped brainstorming from lock (store dir missing, source gone)"
                in actions)
        assert lockfile.get_skill("brainstorming") is None

    def test_nothing_to_do_no_actions(self, brainstorming):
        assert store.sync_apply(store.sync_plan()) == []
