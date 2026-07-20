"""Unit tests: boost_cli/core/store.py — install/uninstall/link/sync (no CLI)."""
from __future__ import annotations

import re
import shutil

import pytest

from boost_cli.core import (catalog, gitutil, journal, lockfile, paths,
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
    def test_workflow_kind_still_refused(self, tap, entry):
        # Rules install now (see TestRuleInstall); workflows remain tap-only.
        wf = dict(entry, kind="workflow", name="some-workflow")
        with pytest.raises(BoostError) as ei:
            store.install(wf)
        assert ei.value.message == (
            "some-workflow is a workflow, which boost indexes but cannot install yet")
        assert ei.value.hint == (
            "workflows show up in `boost search`/`boost taps` for now")
        assert lockfile.get_skill("some-workflow") is None

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
        assert e["commit"] == gitutil.head_commit(tap.path)   # tap HEAD, not cwd
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
        # a fixed *past* timestamp — the second-granularity `now` of the force
        # reinstall must not collide with it, or a dropped-preservation
        # regression would masquerade as passing.
        e["installed_at"] = "2020-01-01T00:00:00Z"
        e["tags"] = ["keeper"]
        e["pinned"] = True
        lockfile.set_skill("brainstorming", e)

        res = store.install(entry, force=True)
        assert res.upgraded is True
        e2 = lockfile.get_skill("brainstorming")
        assert e2["installed_at"] == "2020-01-01T00:00:00Z"   # preserved
        assert e2["updated_at"] != "2020-01-01T00:00:00Z"     # refreshed to now
        assert re.fullmatch(ISO, e2["updated_at"])
        assert e2["tags"] == ["keeper"]
        assert e2["pinned"] is True

    def test_missing_version_defaults_to_zero(self, tap, entry):
        no_ver = {k: v for k, v in entry.items() if k != "version"}
        store.install(no_ver)
        assert lockfile.get_skill("brainstorming")["version"] == "0.0.0"

    def test_policy_block_joins_multiple_violations(self, tap, entry):
        policy.save({"blocked_skills": ["brainstorming"],
                     "blocked_taps": ["fixture-tap"]})
        with pytest.raises(BoostError) as ei:
            store.install(entry)
        assert ei.value.message == (
            "policy blocks installing brainstorming: "
            "skill 'brainstorming' is on the blocklist; "
            "tap 'fixture-tap' is blocked")

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
        assert ei.value.message == "brainstorming is pinned"
        assert ei.value.hint == "`boost unpin brainstorming` first"

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

    def test_max_skills_uses_live_installed_count(self, tap, entry):
        # exercises the `installed_count` argument wiring into check_install:
        # with the cap at 0 even the first install is over budget.
        policy.save({"max_skills": 0})
        with pytest.raises(BoostError) as ei:
            store.install(entry)
        assert "max_skills limit (0) reached" in ei.value.message
        assert lockfile.get_skill("brainstorming") is None

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
        assert e["quarantined"] is False
        assert e["tags"] == []
        assert re.fullmatch(r"[0-9a-f]{64}", e["sha256"])
        assert re.fullmatch(ISO, e["installed_at"])
        assert e["updated_at"] == e["installed_at"]   # both set to `now`
        assert e["agents"] == ["claude-code", "windsurf", "cursor"]

    def test_reinstall_preserves_installed_at_and_tags(self, sandbox, tmp_path):
        src = self._src(tmp_path, "---\nname: keep\nversion: 1.0\n---", extras=False)
        store.install_from_path(src)
        e = lockfile.get_skill("keep")
        e["installed_at"] = "2019-06-06T06:06:06Z"   # fixed past — no `now` collision
        e["tags"] = ["fav", "team"]
        lockfile.set_skill("keep", e)

        store.install_from_path(src)
        e2 = lockfile.get_skill("keep")
        assert e2["installed_at"] == "2019-06-06T06:06:06Z"   # preserved
        assert e2["updated_at"] != "2019-06-06T06:06:06Z"     # refreshed
        assert re.fullmatch(ISO, e2["updated_at"])
        assert e2["tags"] == ["fav", "team"]                  # preserved

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


class TestCopySkillAtomic:
    def _mkskill(self, root, name, body="v1"):
        d = root / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(body)
        return d

    def _leftovers(self, parent, keep):
        return sorted(p.name for p in parent.iterdir() if p.name != keep)

    def test_fresh_copy(self, tmp_path):
        src = self._mkskill(tmp_path / "src", "sk")
        (src / ".git").mkdir()
        (src / ".git" / "cfg").write_text("junk")
        dest = tmp_path / "store" / "sk"
        store._copy_skill(src, dest)
        assert (dest / "SKILL.md").read_text() == "v1"
        assert not (dest / ".git").exists()           # ignore patterns honoured
        assert self._leftovers(dest.parent, "sk") == []   # no temp/backup dirs

    def test_reinstall_replaces_and_cleans_up(self, tmp_path):
        src1 = self._mkskill(tmp_path / "s1", "sk", body="old")
        dest = tmp_path / "store" / "sk"
        store._copy_skill(src1, dest)
        src2 = self._mkskill(tmp_path / "s2", "sk", body="new")
        store._copy_skill(src2, dest)
        assert (dest / "SKILL.md").read_text() == "new"
        assert self._leftovers(dest.parent, "sk") == []

    def test_swap_in_failure_rolls_back_to_original(self, tmp_path, monkeypatch):
        src1 = self._mkskill(tmp_path / "s1", "sk", body="original")
        dest = tmp_path / "store" / "sk"
        store._copy_skill(src1, dest)          # dest now holds the good copy
        src2 = self._mkskill(tmp_path / "s2", "sk", body="broken")

        real = store.os.replace
        calls = {"n": 0}

        def flaky(a, b):
            calls["n"] += 1
            if calls["n"] == 2:                # the swap-IN of the new copy
                raise OSError("swap failed")
            return real(a, b)

        monkeypatch.setattr(store.os, "replace", flaky)
        with pytest.raises(OSError, match="swap failed"):
            store._copy_skill(src2, dest)
        # original survives intact, nothing half-swapped, no debris
        assert (dest / "SKILL.md").read_text() == "original"
        assert self._leftovers(dest.parent, "sk") == []

    def test_copytree_failure_preserves_existing(self, tmp_path, monkeypatch):
        src1 = self._mkskill(tmp_path / "s1", "sk", body="original")
        dest = tmp_path / "store" / "sk"
        store._copy_skill(src1, dest)

        def boom(*a, **k):
            raise OSError("copy failed")

        monkeypatch.setattr(store.shutil, "copytree", boom)
        with pytest.raises(OSError, match="copy failed"):
            store._copy_skill(tmp_path / "s1" / "sk", dest)
        assert (dest / "SKILL.md").read_text() == "original"
        assert self._leftovers(dest.parent, "sk") == []


def _rule_entry(tap, name="team-conventions", rel="rules/team.mdc"):
    """Write a rule file into the tap clone and return its catalog entry."""
    src = tap.path / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("---\nname: Team Conventions\n---\n\nAlways write tests first.\n")
    return {
        "name": name, "kind": "rule", "tap": tap.name, "version": "1.0.0",
        "rel_dir": str(src.parent.relative_to(tap.path)), "skill_md": rel,
        "description": "team rules", "curated": False,
        "meta": {"name": "Team Conventions"},
    }


class TestRuleInstall:
    def _claude_md(self):
        return paths.home() / ".claude" / "CLAUDE.md"

    def test_materializes_into_each_agent_native_format(self, tap):
        res = store.install(_rule_entry(tap))
        assert set(res.linked) == {"claude-code", "windsurf", "cursor"}

        # Claude Code has no rules folder -> managed block in CLAUDE.md.
        text = self._claude_md().read_text()
        assert "boost:rule:team-conventions start" in text
        assert "# Team Conventions" in text
        assert "Always write tests first." in text
        assert "name: Team Conventions" not in text  # frontmatter stripped for CLAUDE.md

        # Cursor: verbatim .mdc drop, frontmatter preserved (native metadata).
        cur = paths.home() / ".cursor" / "rules" / "team-conventions.mdc"
        assert cur.is_file()
        assert "name: Team Conventions" in cur.read_text()

        # Windsurf: .md drop.
        assert (paths.home() / ".windsurf" / "rules" / "team-conventions.md").is_file()

        rec = lockfile.get_rule("team-conventions")
        assert rec["kind"] == "rule"
        assert rec["tap"] == tap.name
        assert {m["agent"] for m in rec["materializations"]} == {
            "claude-code", "windsurf", "cursor"}
        assert lockfile.get_skill("team-conventions") is None  # not a skill

    def test_uninstall_reverses_every_materialization(self, tap):
        store.install(_rule_entry(tap))
        claude_md = self._claude_md()
        # A hand-authored note above our block must survive uninstall.
        claude_md.write_text("# My own standing notes\n\n" + claude_md.read_text())

        info = store.uninstall("team-conventions")
        assert set(info["unlinked"]) == {"claude-code", "windsurf", "cursor"}
        assert lockfile.get_rule("team-conventions") is None
        text = claude_md.read_text()
        assert "boost:rule" not in text
        assert "# My own standing notes" in text
        assert not (paths.home() / ".cursor" / "rules" / "team-conventions.mdc").exists()
        assert not (paths.home() / ".windsurf" / "rules" / "team-conventions.md").exists()

    def test_uninstall_removes_claude_md_when_only_our_block(self, tap):
        store.install(_rule_entry(tap, name="solo"))
        store.uninstall("solo")
        # CLAUDE.md held only our block -> boost created it -> removed on uninstall.
        assert not self._claude_md().exists()

    def test_reinstall_requires_force_and_stays_idempotent(self, tap):
        entry = _rule_entry(tap)
        store.install(entry)
        with pytest.raises(BoostError):
            store.install(entry)
        res = store.install(entry, force=True)
        assert res.upgraded is True
        assert self._claude_md().read_text().count("boost:rule:team-conventions start") == 1

    def test_only_agents_limits_materialization(self, tap):
        res = store.install(_rule_entry(tap), only_agents=["cursor"])
        assert res.linked == ["cursor"]
        assert (paths.home() / ".cursor" / "rules" / "team-conventions.mdc").is_file()
        assert not self._claude_md().exists()

    def test_missing_source_raises(self, tap):
        entry = _rule_entry(tap)
        (tap.path / entry["skill_md"]).unlink()
        with pytest.raises(BoostError, match="vanished from tap"):
            store.install(entry)
