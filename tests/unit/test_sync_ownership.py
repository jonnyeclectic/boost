# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost sync` over store dirs it did not install, and plugin duplicates.

The store dirs the lock does not record used to be one bucket, "orphaned
store dirs", that plain sync ignored and `--prune` deleted wholesale. On the
machine that prompted this they were three different things — a skill the
user wrote, ports of Cursor's built-in skills, and another tool's sync bucket
— and only the ports were copies. These tests pin each answer, and each
re-check standing between a confirm and a deletion.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from boost_cli.core import (
    agents,
    catalog,
    config,
    foreign,
    lockfile,
    paths,
    registry,
    store,
)

LINKED = ["claude-code", "windsurf", "cursor", "antigravity"]
EMPTY = {"adoptable_store": [], "older_copies": [], "foreign_store": [],
         "not_skill_store": []}


@pytest.fixture()
def installed(sandbox, fixture_tap_src):
    t = registry.add(str(fixture_tap_src))
    catalog.rebuild_tap(t)
    store.install(catalog.resolve_one("brainstorming"))
    return t


def _skill(d: Path, body: str = "# s\n", when: float | None = None) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(body, encoding="utf-8")
    if when is not None:
        os.utime(d / "SKILL.md", (when, when))
    return d


def _mine(name: str, body: str = "# mine\n", when: float | None = None) -> Path:
    return _skill(paths.store_dir() / name, body, when)


def _vendor(name: str, body: str = "# vendor\n") -> Path:
    return _skill(paths.home() / ".cursor" / "skills-cursor" / name, body)


def _codex(name: str, body: str = "# codex\n", when: float | None = None) -> Path:
    return _skill(paths.home() / ".codex" / "skills" / name, body, when)


def _classify(*names):
    return store.classify_unrecorded(list(names))


class TestUnrecordedStoreDirs:
    def test_only_unrecorded_directories(self, installed):
        _mine("a")
        (paths.store_dir() / "b").mkdir()
        (paths.store_dir() / ".trash").mkdir(exist_ok=True)
        (paths.store_dir() / "file.txt").write_text("x", encoding="utf-8")
        assert store.unrecorded_store_dirs(lockfile.installed()) == ["a", "b"]

    def test_an_unreadable_store_holds_none(self, sandbox, monkeypatch):
        _mine("a")

        def boom(_p):
            raise PermissionError("no")
        monkeypatch.setattr(store.os, "listdir", boom)
        assert store.unrecorded_store_dirs({}) == []


class TestClassifyUnrecorded:
    def test_nothing_to_classify_reads_nothing(self, sandbox, monkeypatch):
        monkeypatch.setattr(foreign, "inventory", lambda: pytest.fail("read"))
        assert _classify() == EMPTY

    def test_a_dir_without_skill_md_is_not_a_skill(self, sandbox):
        (paths.store_dir() / "synced" / "bucket").mkdir(parents=True)
        assert _classify("synced") == {**EMPTY, "not_skill_store": ["synced"]}

    def test_a_skill_nobody_else_has_is_adoptable(self, sandbox):
        _mine("pr-me")
        assert _classify("pr-me") == {**EMPTY, "adoptable_store": ["pr-me"]}

    def test_a_vendor_copy_is_foreign_whatever_its_bytes_or_age(self, sandbox):
        theirs = _vendor("automate", "# Cursor\n")
        _mine("automate", "# Codex port\n", when=4e9)     # newer, and changed
        assert _classify("automate") == {**EMPTY, "foreign_store": [
            ("automate", "Cursor's built-ins", str(theirs), "differs")]}

    def test_an_identical_vendor_copy_says_so(self, sandbox):
        theirs = _vendor("automate", "# same\n")
        _mine("automate", "# same\n")
        assert _classify("automate")["foreign_store"] == [
            ("automate", "Cursor's built-ins", str(theirs), "identical")]

    def test_a_vendor_outranks_a_plugin(self, claude_plugin, installed):
        claude_plugin("automate", "# plugin\n")
        theirs = _vendor("automate")
        _mine("automate")
        assert _classify("automate")["foreign_store"] == [
            ("automate", "Cursor's built-ins", str(theirs), "differs")]

    def test_a_plugin_skill_is_foreign(self, claude_plugin, installed):
        theirs = claude_plugin("eight-adr", "# plugin\n")
        _mine("eight-adr", "# plugin\n")
        assert _classify("eight-adr")["foreign_store"] == [
            ("eight-adr", "Claude Code plugin eight-backend@eight", str(theirs),
             "identical")]

    def test_an_identical_agent_copy_is_foreign(self, sandbox):
        theirs = _codex("pr-me", "# same\n", when=1e9)
        _mine("pr-me", "# same\n", when=4e9)
        assert _classify("pr-me")["foreign_store"] == [
            ("pr-me", "Codex", str(theirs), "identical")]

    def test_a_newer_agent_copy_owns_the_name(self, sandbox):
        _codex("pr-me", "# codex\n", when=2e9)
        newest = _skill(paths.home() / ".windsurf" / "skills" / "pr-me",
                        "# windsurf\n", when=3e9)
        _mine("pr-me", "# mine\n", when=1e9)
        assert _classify("pr-me") == {**EMPTY, "foreign_store": [
            ("pr-me", "Windsurf", str(newest), "differs")]}

    def test_a_tie_goes_to_the_other_copy(self, sandbox):
        theirs = _codex("pr-me", "# codex\n", when=2e9)
        _mine("pr-me", "# mine\n", when=2e9)
        assert _classify("pr-me")["foreign_store"] == [
            ("pr-me", "Codex", str(theirs), "differs")]

    def test_a_newer_store_copy_is_adopted_and_the_older_ones_named(self, sandbox):
        # The case that prompted the rule: a skill the user edits in
        # ~/.agents/skills, with a stale copy left in ~/.codex/skills.
        older = _codex("pr-me", "# old\n", when=1e9)
        oldest = _skill(paths.home() / ".windsurf" / "skills" / "pr-me",
                        "# older\n", when=5e8)
        _mine("pr-me", "# new\n", when=2e9)
        assert _classify("pr-me") == {**EMPTY,
                                      "adoptable_store": ["pr-me"],
                                      "older_copies": [
                                          ("pr-me", "Windsurf", str(oldest)),
                                          ("pr-me", "Codex", str(older))]}

    def test_every_name_is_answered_in_order(self, sandbox):
        _vendor("v")
        for n in ("z", "v", "a"):
            _mine(n)
        (paths.store_dir() / "e").mkdir()
        got = _classify("z", "v", "e", "a")
        assert got["adoptable_store"] == ["z", "a"]
        assert [r[0] for r in got["foreign_store"]] == ["v"]
        assert got["not_skill_store"] == ["e"]


class TestPluginDuplicates:
    def test_none_without_plugins(self, installed):
        assert store.plugin_duplicates() == []

    def test_an_identical_plugin_copy(self, claude_plugin, installed):
        theirs = claude_plugin()
        assert store.plugin_duplicates() == [
            ("brainstorming", "eight-backend@eight", str(theirs), "identical")]

    def test_a_different_plugin_copy(self, claude_plugin, installed):
        theirs = claude_plugin(body="# a different skill\n")
        assert store.plugin_duplicates() == [
            ("brainstorming", "eight-backend@eight", str(theirs), "differs")]

    def test_the_lock_passed_in_is_the_one_read(self, claude_plugin, installed):
        claude_plugin()
        assert store.plugin_duplicates({}) == []

    def test_not_while_claude_code_is_not_linked(self, claude_plugin, installed):
        claude_plugin()
        cfg = config.load()
        cfg["agents"]["claude-code"]["enabled"] = False
        config.save(cfg)
        assert store.plugin_duplicates() == []

    def test_not_for_a_skill_scoped_away_from_claude_code(self, claude_plugin, installed):
        claude_plugin()
        e = lockfile.get_skill("brainstorming")
        e["only_agents"] = ["cursor"]
        lockfile.set_skill("brainstorming", e)
        assert store.plugin_duplicates() == []

    @pytest.mark.parametrize("key,value", [("quarantined", True),
                                           ("sidelined_by", "focus")])
    def test_not_for_a_skill_with_no_link(self, claude_plugin, installed, key, value):
        claude_plugin()
        e = lockfile.get_skill("brainstorming")
        e[key] = value
        lockfile.set_skill("brainstorming", e)
        assert store.plugin_duplicates() == []

    def test_not_for_a_gutted_store_copy(self, claude_plugin, installed):
        claude_plugin()
        (paths.store_dir() / "brainstorming" / "SKILL.md").unlink()
        assert store.plugin_duplicates() == []

    def test_sync_plan_carries_them_only_while_the_lock_vouches(self, claude_plugin, installed):
        claude_plugin()
        assert [r[0] for r in store.sync_plan()["plugin_duplicates"]] == [
            "brainstorming"]
        paths.lockfile_path().write_text("{nope", encoding="utf-8")
        assert store.sync_plan()["plugin_duplicates"] == []


class TestPlanIssues:
    def test_counts_problems_and_not_notes(self):
        plan = {"missing_links": [("a", "cursor")], "foreign_store": [1, 2],
                "older_copies": [1, 2, 3], "not_skill_store": ["x"],
                "plugin_duplicates": [("a", "p", "/x", "identical"),
                                      ("b", "p", "/y", "differs")]}
        assert store.plan_issues(plan) == 4

    def test_an_empty_plan(self):
        assert store.plan_issues({}) == 0


class TestSyncPlanKeepsAnAdoptedSkillsLink:
    def test_a_hand_made_link_to_an_adoptable_skill_is_not_stale(self, installed):
        mine = _mine("pr-me")
        link = paths.home() / ".claude" / "skills" / "pr-me"
        link.symlink_to(mine)
        plan = store.sync_plan()
        assert plan["adoptable_store"] == ["pr-me"]
        assert plan["stale_links"] == []

    def test_a_link_to_a_foreign_copy_is_still_stale(self, installed):
        _vendor("automate")
        copy = _mine("automate")
        link = paths.home() / ".claude" / "skills" / "automate"
        link.symlink_to(copy)
        assert store.sync_plan()["stale_links"] == [str(link)]


class TestAdoption:
    def test_records_a_local_skill_and_links_it_everywhere(self, installed):
        _mine("pr-me")
        actions = store.sync_apply(store.sync_plan())
        assert actions == ["recorded pr-me as a local skill"] + [
            "linked pr-me → %s" % a for a in LINKED]
        e = lockfile.get_skill("pr-me")
        assert (e["tap"], e["source_dir"], e["commit"], e["version"]) == (
            "local", str(paths.store_dir() / "pr-me"), "", "0.0.0")
        assert e["agents"] == LINKED and e["only_agents"] is None
        assert all(os.path.islink(d / "pr-me")
                   for d in agents.linking_agents().values())
        assert store.sync_plan()["adoptable_store"] == []

    def test_a_hand_made_link_is_kept_as_the_scope(self, installed):
        mine = _mine("pr-me")
        (paths.home() / ".claude" / "skills" / "pr-me").symlink_to(mine)
        actions = store.sync_apply(store.sync_plan())
        assert actions == ["recorded pr-me as a local skill"]
        e = lockfile.get_skill("pr-me")
        assert e["agents"] == ["claude-code"]
        assert e["only_agents"] == ["claude-code"]
        assert (paths.home() / ".claude" / "skills" / "pr-me").is_symlink()
        assert not (paths.home() / ".cursor" / "skills" / "pr-me").exists()

    def test_a_copy_of_exactly_one_tapped_source_gets_its_record(self, installed):
        src = store.source_dir_for(catalog.resolve_one("tdd-workflow"))
        shutil.copytree(src, paths.store_dir() / "tdd-workflow")
        actions = store.sync_apply(store.sync_plan())
        assert actions[0] == "recorded tdd-workflow from %s" % installed.name
        assert lockfile.get_skill("tdd-workflow")["tap"] == installed.name

    def test_a_skill_recorded_since_the_plan_is_left_to_that_record(self, installed):
        _mine("pr-me")
        plan = store.sync_plan()
        lockfile.set_skill("pr-me", {"tap": "elsewhere", "agents": []})
        assert store.sync_apply(plan) == []
        assert lockfile.get_skill("pr-me")["tap"] == "elsewhere"

    def test_a_dir_that_lost_its_skill_md_since_is_skipped(self, installed):
        mine = _mine("pr-me")
        plan = store.sync_plan()
        (mine / "SKILL.md").unlink()
        assert store.adopt_unrecorded("pr-me") == []
        assert store.sync_apply(plan) == []
        assert lockfile.get_skill("pr-me") is None

    def test_a_real_dir_in_the_way_is_a_warning_not_a_link(self, installed):
        _mine("pr-me")
        (paths.home() / ".cursor" / "skills" / "pr-me").mkdir()
        lines = store.adopt_unrecorded("pr-me")
        refused = [ln for ln in lines if store.is_unrepaired(ln)]
        assert refused == ["pr-me was not linked: ~/.cursor/skills/pr-me is in "
                           "the way and is not boost's to replace"]
        assert "linked pr-me → cursor" not in lines
        assert "linked pr-me → claude-code" in lines

    def test_is_journaled_as_an_adoption(self, installed):
        _mine("pr-me")
        store.adopt_unrecorded("pr-me")
        events = [json.loads(ln) for ln in
                  paths.pulse_path().read_text(encoding="utf-8").splitlines()]
        assert {"action": "adopt", "subject": "pr-me"}.items() <= events[-1].items()

    def test_the_preview_words_the_same_decision(self, installed):
        _mine("pr-me")
        assert store.sync_preview(store.sync_plan()) == [
            "would record pr-me, which boost did not install, and link it"]

    def test_a_lost_lock_still_reads_as_recovered(self, installed):
        # The two paths share one recorder and must not share its wording.
        paths.lockfile_path().unlink()
        assert store.recover_unrecorded("brainstorming") == (
            "re-recorded brainstorming from %s" % installed.name)


class TestRemoveForeignCopy:
    def _row(self, name="automate", how="identical"):
        return (*store.classify_unrecorded([name])["foreign_store"][0][:3], how)

    def test_deletes_the_copy_and_keeps_the_original(self, installed):
        theirs = _vendor("automate", "# same\n")
        _mine("automate", "# same\n")
        assert store.remove_foreign_copy(self._row()) is None
        assert not os.path.lexists(paths.store_dir() / "automate")
        assert (theirs / "SKILL.md").is_file()

    def test_a_symlinked_store_entry_loses_only_the_link(self, installed):
        theirs = _vendor("automate")
        elsewhere = _skill(paths.home() / "work" / "automate", "# vendor\n")
        (paths.store_dir() / "automate").symlink_to(elsewhere)
        row = ("automate", "Cursor's built-ins", str(theirs), "identical")
        assert store.remove_foreign_copy(row) is None
        assert (elsewhere / "SKILL.md").is_file()

    def test_kept_when_already_gone(self, installed):
        theirs = _vendor("automate")
        row = ("automate", "x", str(theirs), "identical")
        assert store.remove_foreign_copy(row) == "it is already gone"

    def test_kept_when_boost_has_recorded_it_since(self, installed):
        _vendor("automate", "# same\n")
        _mine("automate", "# same\n")
        row = self._row()
        lockfile.set_skill("automate", {"tap": "t", "agents": []})
        assert store.remove_foreign_copy(row) == "boost has recorded it since"
        assert (paths.store_dir() / "automate").is_dir()

    def test_kept_when_the_original_is_gone(self, installed):
        theirs = _vendor("automate", "# same\n")
        _mine("automate", "# same\n")
        row = self._row()
        (theirs / "SKILL.md").unlink()
        assert store.remove_foreign_copy(row) == (
            "the copy it duplicates, ~/.cursor/skills-cursor/automate, is gone")
        assert (paths.store_dir() / "automate").is_dir()

    def test_kept_when_the_original_now_leads_into_the_store(self, installed):
        theirs = _vendor("automate", "# same\n")
        copy = _mine("automate", "# same\n")
        row = self._row()
        shutil.rmtree(theirs)
        theirs.symlink_to(copy)
        assert store.remove_foreign_copy(row) == (
            "~/.cursor/skills-cursor/automate now leads back into the store, "
            "so it is not a second copy")
        assert copy.is_dir()

    def test_an_identical_copy_edited_since_is_kept(self, installed):
        _vendor("automate", "# same\n")
        copy = _mine("automate", "# same\n")
        row = self._row()
        (copy / "SKILL.md").write_text("# edited\n", encoding="utf-8")
        assert store.remove_foreign_copy(row) == (
            "it has changed since it matched ~/.cursor/skills-cursor/automate")
        assert copy.is_dir()

    def test_a_copy_confirmed_as_different_is_deleted_as_one(self, installed):
        _vendor("automate", "# cursor\n")
        _mine("automate", "# port\n")
        row = self._row(how="differs")
        assert store.remove_foreign_copy(row) is None
        assert not (paths.store_dir() / "automate").exists()

    def test_is_journaled(self, installed):
        theirs = _vendor("automate", "# same\n")
        _mine("automate", "# same\n")
        store.remove_foreign_copy(self._row())
        last = json.loads(paths.pulse_path().read_text(
            encoding="utf-8").splitlines()[-1])
        assert (last["action"], last["subject"], last["copy_of"]) == (
            "prune", "automate", str(theirs))


class TestDropPluginLink:
    def _row(self):
        return store.plugin_duplicates()[0]

    def test_drops_only_claude_codes_link_and_narrows_the_scope(self, claude_plugin, installed):
        claude_plugin()
        ok, line = store.drop_plugin_link(self._row())
        assert ok is True
        assert line == ("unlinked brainstorming → claude-code (Claude Code loads "
                        "it from plugin eight-backend@eight)")
        e = lockfile.get_skill("brainstorming")
        rest = [a for a in LINKED if a != "claude-code"]
        assert e["only_agents"] == rest and e["agents"] == rest
        assert not os.path.lexists(paths.home() / ".claude" / "skills" / "brainstorming")
        assert (paths.home() / ".cursor" / "skills" / "brainstorming").is_symlink()
        plan = store.sync_plan()
        assert plan["missing_links"] == plan["plugin_duplicates"] == []
        assert plan["out_of_scope_links"] == []

    def test_a_refused_claude_code_is_forgotten_too(self, claude_plugin, installed):
        claude_plugin()
        e = lockfile.get_skill("brainstorming")
        e["refused_agents"] = ["claude-code", "cursor"]
        lockfile.set_skill("brainstorming", e)
        store.drop_plugin_link(self._row())
        assert lockfile.get_skill("brainstorming")["refused_agents"] == ["cursor"]

    def test_a_refusal_list_of_only_claude_code_is_removed(self, claude_plugin, installed):
        claude_plugin()
        e = lockfile.get_skill("brainstorming")
        e["refused_agents"] = ["claude-code"]
        lockfile.set_skill("brainstorming", e)
        store.drop_plugin_link(self._row())
        assert "refused_agents" not in lockfile.get_skill("brainstorming")

    def test_refused_when_claude_code_is_the_only_agent(self, claude_plugin, installed):
        claude_plugin()
        e = lockfile.get_skill("brainstorming")
        e["only_agents"] = ["claude-code"]
        lockfile.set_skill("brainstorming", e)
        ok, line = store.drop_plugin_link(self._row())
        assert ok is False
        assert line == ("kept brainstorming → claude-code: it is linked into no "
                        "other agent, and an empty scope means every agent — "
                        "`boost uninstall brainstorming` removes boost's copy "
                        "instead")
        assert lockfile.get_skill("brainstorming")["only_agents"] == ["claude-code"]
        assert (paths.home() / ".claude" / "skills" / "brainstorming").is_symlink()

    def test_refused_when_the_plugin_copy_changed_since(self, claude_plugin, installed):
        theirs = Path(claude_plugin())
        row = self._row()
        (theirs / "SKILL.md").write_text("# updated\n", encoding="utf-8")
        ok, line = store.drop_plugin_link(row)
        assert (ok, line) == (False, "kept brainstorming → claude-code: it no "
                              "longer matches the copy in plugin eight-backend@eight")
        assert lockfile.get_skill("brainstorming").get("only_agents") is None

    def test_refused_when_uninstalled_since(self, claude_plugin, installed):
        claude_plugin()
        row = self._row()
        store.uninstall("brainstorming")
        assert store.drop_plugin_link(row) == (
            False, "kept brainstorming: it is no longer linked into Claude Code")

    def test_refused_when_claude_code_was_disabled_since(self, claude_plugin, installed):
        claude_plugin()
        row = self._row()
        cfg = config.load()
        cfg["agents"]["claude-code"]["enabled"] = False
        config.save(cfg)
        assert store.drop_plugin_link(row)[0] is False

    def test_a_dir_that_refuses_the_unlink_keeps_the_scope(self, claude_plugin, installed,
                                                            monkeypatch):
        claude_plugin()
        row = self._row()

        def boom(self, *a, **kw):
            raise PermissionError("no")
        monkeypatch.setattr(Path, "unlink", boom)
        ok, line = store.drop_plugin_link(row)
        assert (ok, line) == (False, "kept brainstorming → claude-code: "
                              "~/.claude/skills refuses the unlink")
        assert lockfile.get_skill("brainstorming").get("only_agents") is None

    def test_a_real_dir_where_the_link_was_is_not_touched(self, claude_plugin, installed):
        claude_plugin()
        link = paths.home() / ".claude" / "skills" / "brainstorming"
        link.unlink()
        link.mkdir()
        ok, line = store.drop_plugin_link(self._row())
        assert ok is True and link.is_dir()
        assert line == ("stopped linking brainstorming → claude-code (Claude Code "
                        "loads it from plugin eight-backend@eight)")

    def test_is_journaled(self, claude_plugin, installed):
        claude_plugin()
        store.drop_plugin_link(self._row())
        last = json.loads(paths.pulse_path().read_text(
            encoding="utf-8").splitlines()[-1])
        assert (last["action"], last["subject"], last["plugin"]) == (
            "sync-prune", "brainstorming", "eight-backend@eight")


class TestWording:
    def test_foreign_lines_group_by_owner_and_count_the_changes(self, sandbox):
        cursor = str(paths.home() / ".cursor" / "skills-cursor")
        rows = [("a", "Cursor's built-ins", cursor + "/a", "identical"),
                ("b", "Cursor's built-ins", cursor + "/b", "differs"),
                ("c", "Codex", str(paths.home() / ".codex/skills/c"), "differs")]
        assert store.foreign_store_lines(rows) == [
            "a, b copy skills from Cursor's built-ins (~/.cursor/skills-cursor), "
            "not boost's (1 of them changed from the original) — remove with "
            "`boost sync --prune`",
            "c copies a skill from Codex (~/.codex/skills), not boost's "
            "(changed from the original) — remove with `boost sync --prune`"]

    def test_foreign_lines_for_identical_copies_say_nothing_changed(self, sandbox):
        rows = [("a", "o", "/x/a", "identical")]
        assert store.foreign_store_lines(rows) == [
            "a copies a skill from o (/x), not boost's — remove with "
            "`boost sync --prune`"]

    def test_foreign_lines_truncate_long_lists(self, sandbox):
        rows = [("s%d" % i, "o", "/x/s%d" % i, "identical") for i in range(10)]
        line = store.foreign_store_lines(rows)[0]
        assert line.startswith("s0, s1, s2, s3, s4, s5, s6, s7, … copy skills")

    def test_plugin_lines(self, sandbox):
        rows = [("a", "p@m", "/x", "identical"), ("b", "p@m", "/y", "identical"),
                ("c", "q@m", "/z", "identical"), ("d", "p@m", "/w", "differs")]
        assert store.plugin_duplicate_lines(rows) == [
            "a, b show twice in Claude Code — plugin p@m ships the same files; "
            "`boost sync --prune` drops boost's Claude Code link and keeps the "
            "other agents'",
            "c shows twice in Claude Code — plugin q@m ships the same files; "
            "`boost sync --prune` drops boost's Claude Code link and keeps the "
            "other agents'"]
        assert store.plugin_variant_lines(rows) == [
            "d shows twice in Claude Code — plugin p@m ships a different skill "
            "by that name; both left as they are"]

    def test_older_copy_lines(self, sandbox):
        rows = [("pr-me", "Codex", str(paths.home() / ".codex/skills/pr-me"))]
        assert store.older_copy_lines(rows) == [
            "pr-me: the copy in ~/.codex/skills/pr-me (Codex) is older by file "
            "times — left alone"]

    def test_not_skill_line(self, sandbox):
        assert store.not_skill_line(["synced"]) == (
            "~/.agents/skills/synced holds no SKILL.md, so it is not a skill — "
            "left alone")
        assert store.not_skill_line(["a", "b", "c", "d", "e", "f"]) == (
            "6 dirs in ~/.agents/skills hold no SKILL.md, so they are not "
            "skills (a, b, c, d, e, …) — left alone")

