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
REST = [a for a in LINKED if a != "claude-code"]
EMPTY = {"adoptable_store": [], "older_copies": [], "foreign_store": [],
         "not_skill_store": []}
PLUGIN = "eight-backend@eight"


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


def _claude_link(name: str = "brainstorming") -> Path:
    return paths.home() / ".claude" / "skills" / name


def _disable_claude_code() -> None:
    cfg = config.load()
    cfg["agents"]["claude-code"]["enabled"] = False
    config.save(cfg)


def _set(name: str, **fields) -> None:
    e = lockfile.get_skill(name)
    e.update(fields)
    lockfile.set_skill(name, e)


class TestUnrecordedStoreDirs:
    def test_only_unrecorded_directories(self, installed):
        _mine("a")
        (paths.store_dir() / "b").mkdir()
        (paths.store_dir() / ".trash").mkdir(exist_ok=True)
        (paths.store_dir() / "file.txt").write_text("x", encoding="utf-8")
        assert store.unrecorded_store_dirs(lockfile.installed()) == ["a", "b"]

    def test_an_unreadable_store_holds_none(self, sandbox, monkeypatch):
        _mine("a")
        _mine("b copy")

        def boom(_p):
            raise PermissionError("no")
        monkeypatch.setattr(store.os, "listdir", boom)
        assert store.unrecorded_store_dirs({}) == []
        assert store.misnamed_store_dirs() == []

    def test_a_name_boost_cannot_record_is_kept_apart(self, sandbox):
        # A Finder duplicate stopped `boost doctor` three checks in: every path
        # into the store refuses the name.
        _mine("a")
        _mine("brainstorming copy")
        _mine("café-notes")
        (paths.store_dir() / ".a copy").mkdir()
        (paths.store_dir() / "x y.txt").write_text("x", encoding="utf-8")
        assert store.unrecorded_store_dirs({}) == ["a"]
        assert store.misnamed_store_dirs() == ["brainstorming copy", "café-notes"]


class TestHasContent:
    def test_no_store(self, sandbox):
        assert store.has_content() is False

    def test_a_dir_without_skill_md_is_not_content(self, sandbox):
        # Another tool's bucket held `boost doctor` at "lock file missing"
        # for good: there was nothing a lock could have recorded.
        (paths.store_dir() / "synced").mkdir(parents=True)
        (paths.store_dir() / "synced" / "manifest.json").write_text(
            "{}", encoding="utf-8")
        assert store.has_content() is False

    def test_a_dot_dir_is_not_content(self, sandbox):
        _mine(".trash")
        assert store.has_content() is False

    def test_a_skill_is(self, sandbox):
        (paths.store_dir() / "synced").mkdir(parents=True)
        _mine("pr-me")
        assert store.has_content() is True

    def test_an_unreadable_store_holds_none(self, sandbox, monkeypatch):
        _mine("pr-me")

        def boom(_p):
            raise PermissionError("no")
        monkeypatch.setattr(store.os, "listdir", boom)
        assert store.has_content() is False


class TestLockVouches:
    def test_the_check_passed_in_is_the_one_read(self, installed, monkeypatch):
        monkeypatch.setattr(lockfile, "check", lambda: pytest.fail("read"))
        assert store.lock_vouches(lockfile.Integrity(True, None)) is True
        assert store.lock_vouches(lockfile.Integrity(False, "corrupt")) is False
        assert store.lock_vouches(lockfile.Integrity(False, "missing")) is False

    def test_a_missing_lock_over_an_empty_store_vouches(self, sandbox):
        assert store.lock_vouches(lockfile.Integrity(False, "missing")) is True


class TestClassifyUnrecorded:
    def test_nothing_to_classify_reads_nothing(self, sandbox, monkeypatch):
        monkeypatch.setattr(foreign, "inventory",
                            lambda *a, **k: pytest.fail("read"))
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
            ("eight-adr", "Claude Code plugin %s" % PLUGIN, str(theirs),
             "identical")]

    def test_a_plugin_skill_is_matched_by_its_skill_md_name(self, claude_plugin,
                                                            sandbox):
        # A `cp -r` keeps the plugin's dir name; Claude Code lists the skill
        # under the frontmatter one.
        body = "---\nname: eight-adr\n---\n# plugin\n"
        theirs = claude_plugin("adr", body)
        _mine("adr", body)
        assert _classify("adr") == {**EMPTY, "foreign_store": [
            ("adr", "Claude Code plugin %s" % PLUGIN, str(theirs), "identical")]}

    def test_an_agent_copy_under_the_skill_md_name_is_not_one(self, sandbox):
        # Only a plugin keys its skills by the frontmatter name.
        body = "---\nname: eight-adr\n---\n# same\n"
        _codex("eight-adr", body)
        _mine("adr", body)
        assert _classify("adr") == {**EMPTY, "adoptable_store": ["adr"]}

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

    def test_a_store_link_to_another_tools_skill_is_in_no_bucket(self, sandbox):
        # The user's own alias, so the agents that read the store see a skill
        # kept in ~/.claude/skills: not a copy to prune, not boost's to record.
        theirs = _skill(paths.home() / ".claude" / "skills" / "my-notes")
        _mine("z-mine")
        (paths.store_dir() / "my-notes").symlink_to(theirs)
        assert _classify("my-notes", "z-mine") == {
            **EMPTY, "adoptable_store": ["z-mine"]}

    def test_an_agent_owned_name_does_not_end_the_pass(self, sandbox):
        same = _codex("a", "# a\n")
        _mine("a", "# a\n")
        newer = _codex("b", "# codex b\n", when=3e9)
        _mine("b", "# mine b\n", when=1e9)
        _mine("c")
        assert _classify("a", "b", "c") == {**EMPTY,
                                            "adoptable_store": ["c"],
                                            "foreign_store": [
                                                ("a", "Codex", str(same), "identical"),
                                                ("b", "Codex", str(newer), "differs")]}

    def test_every_name_is_answered_in_order(self, sandbox):
        _vendor("v")
        for n in ("z", "v", "a"):
            _mine(n)
        (paths.store_dir() / "e").mkdir()
        got = _classify("z", "v", "e", "a")
        assert got["adoptable_store"] == ["z", "a"]
        assert [r[0] for r in got["foreign_store"]] == ["v"]
        assert got["not_skill_store"] == ["e"]


class TestCoveringPlugin:
    def test_none_without_plugins(self, installed):
        assert store.covering_plugin("brainstorming") is None

    def test_a_plugin_with_the_same_files(self, claude_plugin, installed):
        theirs = claude_plugin()
        plugin, path = store.covering_plugin("brainstorming")
        assert (plugin.id, str(path)) == (PLUGIN, str(theirs))

    def test_a_plugin_with_a_different_skill_by_the_name(self, claude_plugin,
                                                         installed):
        claude_plugin(body="# a different skill\n")
        assert store.covering_plugin("brainstorming") is None

    def test_matched_by_the_store_copys_skill_md_name(self, claude_plugin, sandbox):
        theirs = claude_plugin("adr", "---\nname: eight-adr\n---\n# p\n")
        shutil.copytree(theirs, paths.store_dir() / "adr")
        assert store.covering_plugin("adr")[0].id == PLUGIN

    def test_the_index_passed_in_is_the_one_read(self, claude_plugin, installed,
                                                 monkeypatch):
        claude_plugin()
        monkeypatch.setattr(foreign, "plugin_index", lambda: pytest.fail("read"))
        assert store.covering_plugin("brainstorming", {}) is None


class TestPluginCoverage:
    def test_identical_and_different_copies(self, claude_plugin, installed):
        store.install(catalog.resolve_one("tdd-workflow"))
        same = claude_plugin()
        other = claude_plugin("tdd-workflow", "# a different skill\n")
        assert store.plugin_coverage(lockfile.installed()) == {
            "brainstorming": (PLUGIN, str(same), "identical"),
            "tdd-workflow": (PLUGIN, str(other), "differs")}

    def test_none_while_claude_code_is_not_linked(self, claude_plugin, installed):
        claude_plugin()
        _disable_claude_code()
        assert store.plugin_coverage(lockfile.installed()) == {}

    @pytest.mark.parametrize("fields", [{"quarantined": True},
                                        {"sidelined_by": "focus"},
                                        {"only_agents": ["cursor"]}])
    def test_a_skill_with_no_claude_code_link_to_weigh(self, claude_plugin,
                                                       installed, fields):
        claude_plugin()
        _set("brainstorming", **fields)
        assert store.plugin_coverage(lockfile.installed()) == {}

    def test_a_skipped_skill_does_not_end_the_pass(self, claude_plugin, installed):
        theirs = claude_plugin()
        (paths.store_dir() / "aaa").mkdir()        # no SKILL.md
        _mine("aab")                               # no plugin ships it
        lock = {"aa0": {"quarantined": True}, "aaa": {}, "aab": {},
                **lockfile.installed()}
        assert store.plugin_coverage(lock) == {
            "brainstorming": (PLUGIN, str(theirs), "identical")}


class TestPluginDuplicates:
    def test_none_without_plugins(self, installed):
        assert store.plugin_duplicates() == []

    def test_an_identical_plugin_copy(self, claude_plugin, installed):
        theirs = claude_plugin()
        assert store.plugin_duplicates() == [
            ("brainstorming", PLUGIN, str(theirs), "identical")]

    def test_a_different_plugin_copy(self, claude_plugin, installed):
        theirs = claude_plugin(body="# a different skill\n")
        assert store.plugin_duplicates() == [
            ("brainstorming", PLUGIN, str(theirs), "differs")]

    def test_the_lock_passed_in_is_the_one_read(self, claude_plugin, installed):
        claude_plugin()
        assert store.plugin_duplicates({}) == []

    def test_the_coverage_passed_in_is_the_one_read(self, installed):
        row = ("p@m", "/x", "identical")
        assert store.plugin_duplicates(lockfile.installed(),
                                       {"brainstorming": row}) == [
            ("brainstorming", *row)]

    def test_not_while_claude_code_is_not_linked(self, claude_plugin, installed):
        claude_plugin()
        _disable_claude_code()
        assert store.plugin_duplicates() == []

    def test_not_for_a_skill_scoped_away_from_claude_code(self, claude_plugin, installed):
        claude_plugin()
        _set("brainstorming", only_agents=["cursor"])
        assert store.plugin_duplicates() == []

    @pytest.mark.parametrize("key,value", [("quarantined", True),
                                           ("sidelined_by", "focus")])
    def test_not_for_a_skill_with_no_link(self, claude_plugin, installed, key, value):
        claude_plugin()
        _set("brainstorming", **{key: value})
        assert store.plugin_duplicates() == []

    def test_not_for_a_gutted_store_copy(self, claude_plugin, installed):
        claude_plugin()
        (paths.store_dir() / "brainstorming" / "SKILL.md").unlink()
        assert store.plugin_duplicates() == []

    def test_not_once_boosts_link_is_gone(self, claude_plugin, installed):
        claude_plugin()
        _claude_link().unlink()
        assert store.plugin_duplicates() == []

    def test_not_while_the_link_leads_elsewhere(self, claude_plugin, installed):
        claude_plugin()
        _claude_link().unlink()
        _claude_link().symlink_to(_skill(paths.home() / "dev" / "brainstorming"))
        assert store.plugin_duplicates() == []

    def test_sync_plan_carries_them_only_while_the_lock_vouches(self, claude_plugin, installed):
        claude_plugin()
        assert [r[0] for r in store.sync_plan()["plugin_duplicates"]] == [
            "brainstorming"]
        paths.lockfile_path().write_text("{nope", encoding="utf-8")
        assert store.sync_plan()["plugin_duplicates"] == []


class TestCoveredSkills:
    def test_only_a_plugin_shipping_the_same_files_covers_a_skill(self):
        coverage = {"same": (PLUGIN, "/p/same", foreign.IDENTICAL),
                    "other": (PLUGIN, "/p/other", foreign.DIFFERS)}
        assert store.covered_skills(coverage) == {"same"}

    def test_no_coverage_covers_nothing(self):
        assert store.covered_skills({}) == set()


class TestLeftToPlugin:
    def _left(self, agent="claude-code", link=None, covered=("brainstorming",)):
        return store.left_to_plugin("brainstorming", agent,
                                    link or _claude_link(), set(covered))

    def test_a_missing_claude_code_link_to_a_covered_skill(self, installed):
        _claude_link().unlink()
        assert self._left()

    def test_not_another_agents_link(self, installed):
        link = paths.home() / ".cursor" / "skills" / "brainstorming"
        link.unlink()
        assert not self._left(agent="cursor", link=link)

    def test_not_a_skill_no_plugin_covers(self, installed):
        _claude_link().unlink()
        assert not self._left(covered=set())

    def test_not_while_boosts_link_is_there(self, installed):
        assert not self._left()

    def test_another_link_by_the_name_is_no_fault(self, installed):
        mine = _skill(paths.home() / "dev" / "brainstorming")
        _claude_link().unlink()
        _claude_link().symlink_to(mine)
        assert self._left()

    def test_a_dir_where_the_link_would_go_is_no_fault(self, installed):
        _claude_link().unlink()
        _claude_link().mkdir()
        assert self._left()


class TestLinkAgentsLeavesACoveredSkillToItsPlugin:
    def test_a_fresh_install_makes_no_claude_code_link(self, claude_plugin,
                                                       installed):
        claude_plugin()
        store.uninstall("brainstorming")
        res = store.install(catalog.resolve_one("brainstorming"))
        assert res.covered == [PLUGIN]
        assert res.linked == REST and res.refused == []
        assert not os.path.lexists(_claude_link())
        e = lockfile.get_skill("brainstorming")
        assert e["agents"] == REST and "refused_agents" not in e

    def test_an_explicit_claude_code_install_too(self, claude_plugin, installed):
        claude_plugin()
        _claude_link().unlink()
        res = store.link_agents("brainstorming", only=["claude-code"])
        assert (res.linked, res.covered) == ([], [PLUGIN])
        assert not os.path.lexists(_claude_link())

    def test_a_link_already_there_is_kept(self, claude_plugin, installed):
        claude_plugin()
        res = store.link_agents("brainstorming")
        assert res.linked == LINKED and res.covered == []
        assert _claude_link().is_symlink()

    def test_another_link_by_the_name_is_left_alone(self, claude_plugin, installed):
        claude_plugin()
        mine = _skill(paths.home() / "dev" / "brainstorming")
        _claude_link().unlink()
        _claude_link().symlink_to(mine)
        assert store.link_agents("brainstorming").covered == [PLUGIN]
        assert os.readlink(_claude_link()) == str(mine)

    def test_claude_codes_dir_is_not_created_for_it(self, claude_plugin, installed):
        claude_plugin()
        shutil.rmtree(paths.home() / ".claude" / "skills")
        store.link_agents("brainstorming")
        assert not os.path.lexists(paths.home() / ".claude" / "skills")

    def test_a_plugin_with_a_different_skill_does_not_cover_it(self, claude_plugin,
                                                               installed):
        claude_plugin(body="# a different skill\n")
        _claude_link().unlink()
        res = store.link_agents("brainstorming")
        assert "claude-code" in res.linked and res.covered == []
        assert _claude_link().is_symlink()

    def test_ending_a_sideline_does_not_bring_the_link_back(self, claude_plugin,
                                                            installed):
        claude_plugin()
        store.sideline("brainstorming", "focus")
        res = store.unsideline("brainstorming")
        assert res.covered == [PLUGIN]
        assert not os.path.lexists(_claude_link())
        assert lockfile.get_skill("brainstorming")["agents"] == REST


class TestSyncPlanLeavesACoveredSkillToItsPlugin:
    def test_its_missing_claude_code_link_is_no_repair(self, claude_plugin,
                                                       installed):
        claude_plugin()
        _claude_link().unlink()
        plan = store.sync_plan()
        assert plan["missing_links"] == plan["plugin_duplicates"] == []
        assert store.sync_apply(plan) == []
        assert not os.path.lexists(_claude_link())

    def test_something_where_its_link_would_go_blocks_nothing(self, claude_plugin,
                                                              installed):
        claude_plugin()
        _claude_link().unlink()
        _claude_link().mkdir()
        assert store.sync_plan()["blocked_links"] == []

    def test_claude_codes_dir_in_the_way_blocks_nothing(self, claude_plugin,
                                                        installed):
        claude_plugin()
        shutil.rmtree(paths.home() / ".claude" / "skills")
        (paths.home() / ".claude" / "skills").write_text("x", encoding="utf-8")
        assert store.sync_plan()["blocked_links"] == []

    def test_a_different_skill_by_the_name_still_gets_its_link(self, claude_plugin,
                                                               installed):
        claude_plugin(body="# a different skill\n")
        _claude_link().unlink()
        assert store.sync_plan()["missing_links"] == [
            ("brainstorming", "claude-code")]


class TestSortUnrecorded:
    def test_an_intact_lock_is_classified(self, installed):
        _mine("pr-me")
        theirs = _vendor("automate")
        _mine("automate")
        _mine("b copy")
        assert store.sort_unrecorded(lockfile.installed()) == {
            **EMPTY, "adoptable_store": ["pr-me"],
            "foreign_store": [("automate", "Cursor's built-ins", str(theirs),
                               "differs")],
            "unrecorded_store": [], "misnamed_store": ["b copy"]}

    def test_a_missing_lock_queues_what_boost_may_have_installed(self, installed):
        _mine("pr-me")
        older = _codex("old-me", "# old\n", when=1e9)
        _mine("old-me", "# new\n", when=2e9)
        _vendor("linked")
        _mine("linked")
        (paths.home() / ".cursor" / "skills" / "linked").symlink_to(
            paths.store_dir() / "linked")
        theirs = _vendor("unlinked")
        _mine("unlinked")
        _mine("b copy")
        paths.lockfile_path().unlink()
        assert store.sort_unrecorded(lockfile.installed()) == {
            **EMPTY,
            "unrecorded_store": ["brainstorming", "linked", "old-me", "pr-me"],
            "older_copies": [("old-me", "Codex", str(older))],
            "foreign_store": [("unlinked", "Cursor's built-ins", str(theirs),
                               "differs")],
            "misnamed_store": ["b copy"]}

    def test_a_corrupt_lock_reads_nothing_else(self, installed, monkeypatch):
        _mine("pr-me")
        _mine("b copy")
        paths.lockfile_path().write_text("{oops", encoding="utf-8")
        monkeypatch.setattr(foreign, "inventory",
                            lambda *a, **k: pytest.fail("read"))
        assert store.sort_unrecorded(lockfile.installed()) == {
            **EMPTY, "unrecorded_store": ["brainstorming", "pr-me"],
            "misnamed_store": ["b copy"]}

    def test_the_check_passed_in_is_the_one_read(self, installed, monkeypatch):
        _mine("pr-me")
        monkeypatch.setattr(lockfile, "check", lambda: pytest.fail("read"))
        got = store.sort_unrecorded({}, lockfile.Integrity(False, "corrupt"))
        assert got["unrecorded_store"] == ["brainstorming", "pr-me"]


class TestPlanIssues:
    def test_counts_problems_and_not_notes(self):
        plan = {"missing_links": [("a", "cursor")], "foreign_store": [1, 2],
                "older_copies": [1, 2, 3], "not_skill_store": ["x"],
                "misnamed_store": ["x y"],
                "plugin_duplicates": [("a", "p", "/x", "identical"),
                                      ("b", "p", "/y", "differs")]}
        assert store.plan_issues(plan) == 4

    def test_an_empty_plan(self):
        assert store.plan_issues({}) == 0


class TestSyncPlanKeepsAnAdoptedSkillsLink:
    def test_a_hand_made_link_to_an_adoptable_skill_is_not_stale(self, installed):
        mine = _mine("pr-me")
        _claude_link("pr-me").symlink_to(mine)
        plan = store.sync_plan()
        assert plan["adoptable_store"] == ["pr-me"]
        assert plan["stale_links"] == []

    def test_a_link_to_a_foreign_copy_is_still_stale(self, installed):
        _vendor("automate")
        copy = _mine("automate")
        link = _claude_link("automate")
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
        _claude_link("pr-me").symlink_to(mine)
        actions = store.sync_apply(store.sync_plan())
        assert actions == ["recorded pr-me as a local skill"]
        e = lockfile.get_skill("pr-me")
        assert e["agents"] == ["claude-code"]
        assert e["only_agents"] == ["claude-code"]
        assert _claude_link("pr-me").is_symlink()
        assert not (paths.home() / ".cursor" / "skills" / "pr-me").exists()

    def test_a_dangling_link_into_the_store_is_the_scope_too(self, installed):
        _mine("pr-me")
        cursor = paths.home() / ".cursor" / "skills" / "pr-me"
        cursor.symlink_to(paths.store_dir() / "pr-me-before-a-rename")
        store.adopt_unrecorded("pr-me")
        e = lockfile.get_skill("pr-me")
        assert e["only_agents"] == ["cursor"] and e["agents"] == ["cursor"]
        assert os.path.realpath(cursor) == os.path.realpath(
            paths.store_dir() / "pr-me")

    def test_a_copy_of_a_tapped_source_is_still_a_local_skill(self, installed,
                                                              monkeypatch):
        # Matching it hashed every same-named entry's source, and each hash
        # widened that entry's clone.
        src = store.source_dir_for(catalog.resolve_one("tdd-workflow"))
        shutil.copytree(src, paths.store_dir() / "tdd-workflow")
        monkeypatch.setattr(catalog, "find", lambda *a: pytest.fail("matched"))
        monkeypatch.setattr(store, "_skill_source_sha",
                            lambda *a: pytest.fail("hashed"))
        actions = store.sync_apply(store.sync_plan())
        assert actions[0] == "recorded tdd-workflow as a local skill"
        assert lockfile.get_skill("tdd-workflow")["tap"] == "local"

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
        assert refused == [
            "pr-me was not linked: ~/.cursor/skills/pr-me is in the way and is "
            "not boost's to replace — to link boost's copy, move or delete it, "
            "then re-run `boost sync`"]
        assert "linked pr-me → cursor" not in lines
        assert "linked pr-me → claude-code" in lines

    def test_the_users_own_link_is_left_where_it_leads(self, installed):
        # Any symlink used to count as boost's to replace, which re-pointed
        # Claude Code from the user's checkout to the store copy.
        checkout = _skill(paths.home() / "dev" / "pr-me", "# checkout\n", when=1e9)
        _mine("pr-me", "# store\n", when=2e9)
        _claude_link("pr-me").symlink_to(checkout)
        actions = store.sync_apply(store.sync_plan())
        assert actions == ["recorded pr-me as a local skill"] + [
            "linked pr-me → %s" % a for a in REST] + [
            "pr-me was not linked: ~/.claude/skills/pr-me is in the way and is "
            "not boost's to replace — to link boost's copy, move or delete it, "
            "then re-run `boost sync`"]
        assert os.readlink(_claude_link("pr-me")) == str(checkout)
        e = lockfile.get_skill("pr-me")
        assert e["only_agents"] is None and e["agents"] == REST

    def test_nothing_to_link_asks_for_no_links(self, installed, monkeypatch):
        # `link_agents` reads an empty list as every agent.
        _mine("pr-me")
        for adir in agents.linking_agents().values():
            (adir / "pr-me").mkdir()
        monkeypatch.setattr(store, "link_agents", lambda *a, **k: pytest.fail("linked"))
        lines = store.adopt_unrecorded("pr-me")
        assert lines[0] == "recorded pr-me as a local skill"
        assert len(lines) == 5 and all(store.is_unrepaired(ln) for ln in lines[1:])
        assert lockfile.get_skill("pr-me")["agents"] == []

    def test_an_unreadable_file_is_named_and_the_rest_still_runs(self, installed):
        secret = _mine("pr-me") / "secret.txt"
        secret.write_text("x", encoding="utf-8")
        secret.chmod(0)
        (paths.home() / ".cursor" / "skills" / "brainstorming").unlink()
        try:
            actions = store.sync_apply(store.sync_plan())
        finally:
            secret.chmod(0o644)
        line = ("pr-me was not recorded: ~/.agents/skills/pr-me/secret.txt is "
                "unreadable — make it readable, then re-run `boost sync`")
        assert line in actions and store.is_unrepaired(line)
        assert "linked brainstorming → cursor" in actions
        assert lockfile.get_skill("pr-me") is None

    def test_an_unreadable_file_under_a_lost_lock_is_named(self, installed):
        secret = paths.store_dir() / "brainstorming" / "secret.txt"
        secret.write_text("x", encoding="utf-8")
        secret.chmod(0)
        paths.lockfile_path().unlink()
        try:
            line = store.recover_unrecorded("brainstorming")
        finally:
            secret.chmod(0o644)
        assert line == ("brainstorming was not recorded: "
                        "~/.agents/skills/brainstorming/secret.txt is unreadable "
                        "— make it readable, then re-run `boost sync`")

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

    def test_the_preview_names_what_is_in_the_way(self, installed):
        _mine("pr-me")
        (paths.home() / ".cursor" / "skills" / "pr-me").mkdir()
        assert store.sync_preview(store.sync_plan()) == [
            "would record pr-me, which boost did not install, and link it "
            "(not into cursor: ~/.cursor/skills/pr-me is in the way)"]

    def test_the_preview_says_when_nothing_will_be_linked(self, installed):
        _mine("pr-me")
        for adir in agents.linking_agents().values():
            (adir / "pr-me").mkdir()
        assert store.sync_preview(store.sync_plan()) == [
            "would record pr-me, which boost did not install, and leave it "
            "unlinked (%s)" % "; ".join(
                "not into %s: ~/%s/pr-me is in the way" % (
                    a, paths.tilde(d).removeprefix("~/"))
                for a, d in agents.linking_agents().items())]

    def test_a_lost_lock_still_reads_as_recovered(self, installed):
        # The two paths share one recorder and must not share its wording.
        paths.lockfile_path().unlink()
        assert store.recover_unrecorded("brainstorming") == (
            "re-recorded brainstorming from %s" % installed.name)

    def test_a_queued_dir_that_lost_its_skill_md_is_left(self, installed):
        # A plan only queues a dir with a SKILL.md, so this is a dir emptied
        # between the plan and the run.
        paths.lockfile_path().unlink()
        (paths.store_dir() / "husk").mkdir()
        plan = {**store.sync_plan(), "unrecorded_store": ["husk"]}
        assert store.sync_preview(plan) == [
            "would leave husk unrecorded (no SKILL.md to record)"]
        assert store.sync_apply(plan) == [
            "left husk unrecorded (no SKILL.md to record)"]


class TestOnlyCopy:
    def test_a_local_skill_whose_source_is_its_store_dir(self, sandbox):
        mine = _mine("pr-me")
        assert store.only_copy("pr-me", {"tap": "local", "source_dir": str(mine)})

    def test_one_whose_source_reaches_the_store_another_way(self, sandbox):
        alias = paths.home() / "alias"
        alias.symlink_to(_mine("pr-me"))
        assert store.only_copy("pr-me", {"tap": "local", "source_dir": str(alias)})

    def test_one_whose_source_is_gone(self, sandbox):
        _mine("pr-me")
        entry = {"tap": "local", "source_dir": str(paths.home() / "gone")}
        assert store.only_copy("pr-me", entry)

    def test_not_one_whose_source_is_elsewhere(self, sandbox):
        _mine("pr-me")
        src = _skill(paths.home() / "dev" / "pr-me")
        assert not store.only_copy("pr-me", {"tap": "local", "source_dir": str(src)})

    def test_not_a_tapped_skill(self, installed):
        assert not store.only_copy("brainstorming",
                                   lockfile.get_skill("brainstorming"))

    def test_not_a_url_import(self, sandbox):
        _mine("pr-me")
        entry = {"tap": "local", "source_url": "https://example.test/r.git",
                 "source_dir": "skills/pr-me"}
        assert not store.only_copy("pr-me", entry)


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

    def test_answers_row_by_row(self, installed):
        theirs = _vendor("automate", "# same\n")
        _mine("automate", "# same\n")
        gone = ("explain", "x", str(_vendor("explain")), "identical")
        assert store.remove_foreign_copies([self._row(), gone]) == [
            None, "it is already gone"]
        assert (theirs / "SKILL.md").is_file()

    def test_kept_when_already_gone(self, installed):
        theirs = _vendor("automate")
        row = ("automate", "x", str(theirs), "identical")
        assert store.remove_foreign_copy(row) == "it is already gone"

    def test_kept_while_the_lock_cannot_be_read(self, installed):
        _vendor("automate", "# same\n")
        copy = _mine("automate", "# same\n")
        row = self._row()
        paths.lockfile_path().write_text("{oops", encoding="utf-8")
        assert store.remove_foreign_copies([row, row]) == [
            "the lock file cannot be read, so boost cannot tell whether it is "
            "boost's — restore the lock with `boost replay`"] * 2
        assert copy.is_dir()

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

    def test_kept_when_the_original_links_into_it_file_by_file(self, installed):
        theirs = _vendor("automate", "# same\n")
        copy = _mine("automate", "# same\n")
        row = self._row()
        (theirs / "SKILL.md").unlink()
        (theirs / "SKILL.md").symlink_to(copy / "SKILL.md")
        assert store.remove_foreign_copy(row) == (
            "~/.cursor/skills-cursor/automate links into the store file by "
            "file, so deleting this would empty it")
        assert copy.is_dir()

    def test_kept_when_it_lost_its_skill_md(self, installed):
        _vendor("automate", "# same\n")
        copy = _mine("automate", "# same\n")
        row = self._row()
        (copy / "notes.md").write_text("mine\n", encoding="utf-8")
        (copy / "SKILL.md").unlink()
        assert store.remove_foreign_copy(row) == "it no longer holds a SKILL.md"
        assert (copy / "notes.md").is_file()

    def test_kept_when_edited_into_the_newest_copy(self, installed):
        # An agent's copy owned the name by being newer; an edit since makes
        # the store copy the one the user is working on.
        _codex("pr-me", "# codex\n", when=3e9)
        copy = _mine("pr-me", "# mine\n", when=1e9)
        row = self._row("pr-me", "differs")
        _skill(copy, "# mine, edited\n", when=4e9)
        assert store.remove_foreign_copy(row) == (
            "it is now newer than ~/.codex/skills/pr-me")
        assert copy.is_dir()

    def test_kept_when_it_is_now_a_copy_of_something_else(self, installed):
        _codex("automate", "# codex\n", when=3e9)
        copy = _mine("automate", "# mine\n", when=1e9)
        row = self._row(how="differs")
        _vendor("automate", "# cursor\n")
        assert store.remove_foreign_copy(row) == (
            "it is now a copy of ~/.cursor/skills-cursor/automate instead")
        assert copy.is_dir()

    def test_kept_when_it_is_no_longer_a_copy(self, installed):
        # Now the user's alias of that skill: deleting it would unlink the
        # second path they made on purpose.
        theirs = _codex("pr-me", "# same\n")
        copy = _mine("pr-me", "# same\n")
        row = self._row("pr-me")
        shutil.rmtree(copy)
        copy.symlink_to(theirs)
        assert store.remove_foreign_copy(row) == (
            "it is no longer a copy of ~/.codex/skills/pr-me")
        assert copy.is_symlink()

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

    def test_a_different_copy_that_came_to_match_is_still_one(self, installed):
        _vendor("automate", "# cursor\n")
        copy = _mine("automate", "# port\n")
        row = self._row(how="differs")
        (copy / "SKILL.md").write_text("# cursor\n", encoding="utf-8")
        assert store.remove_foreign_copy(row) is None
        assert not os.path.lexists(copy)

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

    def test_drops_only_claude_codes_link_and_keeps_the_scope(self, claude_plugin,
                                                              installed):
        claude_plugin()
        ok, line = store.drop_plugin_link(self._row())
        assert ok is True
        assert line == ("unlinked brainstorming → claude-code (Claude Code loads "
                        "the same files from plugin %s)" % PLUGIN)
        e = lockfile.get_skill("brainstorming")
        assert e["only_agents"] is None and e["agents"] == REST
        assert not os.path.lexists(_claude_link())
        assert (paths.home() / ".cursor" / "skills" / "brainstorming").is_symlink()
        plan = store.sync_plan()
        assert plan["missing_links"] == plan["plugin_duplicates"] == []
        assert plan["out_of_scope_links"] == []
        assert store.sync_apply(plan) == []
        assert not os.path.lexists(_claude_link())

    def test_a_skill_scoped_to_claude_code_alone_is_dropped_too(self, claude_plugin,
                                                                installed):
        # An empty scope means every agent, so narrowing had no answer here.
        claude_plugin()
        for a in REST:
            (agents.linking_agents()[a] / "brainstorming").unlink()
        _set("brainstorming", only_agents=["claude-code"], agents=["claude-code"])
        ok, _line = store.drop_plugin_link(self._row())
        assert ok is True
        e = lockfile.get_skill("brainstorming")
        assert e["only_agents"] == ["claude-code"] and e["agents"] == []
        assert store.sync_plan()["missing_links"] == []

    def test_a_refused_claude_code_is_forgotten_too(self, claude_plugin, installed):
        claude_plugin()
        _set("brainstorming", refused_agents=["claude-code", "cursor"])
        store.drop_plugin_link(self._row())
        assert lockfile.get_skill("brainstorming")["refused_agents"] == ["cursor"]

    def test_a_refusal_list_of_only_claude_code_is_removed(self, claude_plugin, installed):
        claude_plugin()
        _set("brainstorming", refused_agents=["claude-code"])
        store.drop_plugin_link(self._row())
        assert "refused_agents" not in lockfile.get_skill("brainstorming")

    def test_refused_when_the_plugin_copy_changed_since(self, claude_plugin, installed):
        theirs = Path(claude_plugin())
        row = self._row()
        (theirs / "SKILL.md").write_text("# updated\n", encoding="utf-8")
        assert store.drop_plugin_link(row) == (
            False, "kept brainstorming → claude-code: it no longer matches the "
                   "copy in plugin %s" % PLUGIN)
        assert lockfile.get_skill("brainstorming")["agents"] == LINKED

    def test_refused_when_the_plugin_was_disabled_since(self, claude_plugin,
                                                        installed):
        claude_plugin()
        row = self._row()
        (paths.home() / ".claude" / "settings.json").write_text(
            json.dumps({"enabledPlugins": {PLUGIN: False}}), encoding="utf-8")
        assert store.drop_plugin_link(row) == (
            False, "kept brainstorming → claude-code: plugin %s is no longer "
                   "enabled" % PLUGIN)
        assert _claude_link().is_symlink()

    def test_refused_when_uninstalled_since(self, claude_plugin, installed):
        claude_plugin()
        row = self._row()
        store.uninstall("brainstorming")
        assert store.drop_plugin_link(row) == (
            False, "kept brainstorming: it is no longer linked into Claude Code")

    def test_refused_when_claude_code_was_disabled_since(self, claude_plugin, installed):
        claude_plugin()
        row = self._row()
        _disable_claude_code()
        assert store.drop_plugin_link(row) == (
            False, "kept brainstorming: it is no longer linked into Claude Code")

    def test_a_dir_that_refuses_the_unlink_keeps_the_record(self, claude_plugin,
                                                            installed, monkeypatch):
        claude_plugin()
        row = self._row()

        def boom(self, *a, **kw):
            raise PermissionError("no")
        monkeypatch.setattr(Path, "unlink", boom)
        assert store.drop_plugin_link(row) == (
            False, "kept brainstorming → claude-code: ~/.claude/skills refuses "
                   "the unlink")
        assert lockfile.get_skill("brainstorming")["agents"] == LINKED

    @pytest.mark.parametrize("swap", ["dir", "link"])
    def test_what_replaced_boosts_link_is_not_touched(self, claude_plugin,
                                                      installed, swap):
        claude_plugin()
        row = self._row()
        link = _claude_link()
        link.unlink()
        if swap == "dir":
            link.mkdir()
        else:
            link.symlink_to(_skill(paths.home() / "dev" / "brainstorming"))
        assert store.drop_plugin_link(row) == (
            False, "left brainstorming alone: ~/.claude/skills/brainstorming is "
                   "no longer boost's link")
        assert os.path.lexists(link)
        assert lockfile.get_skill("brainstorming")["agents"] == LINKED

    def test_is_journaled(self, claude_plugin, installed):
        claude_plugin()
        store.drop_plugin_link(self._row())
        last = json.loads(paths.pulse_path().read_text(
            encoding="utf-8").splitlines()[-1])
        assert (last["action"], last["subject"], last["plugin"]) == (
            "sync-prune", "brainstorming", PLUGIN)


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
            "`boost sync --prune` drops boost's Claude Code link",
            "c shows twice in Claude Code — plugin q@m ships the same files; "
            "`boost sync --prune` drops boost's Claude Code link"]
        assert store.plugin_variant_lines(rows) == [
            "d shows twice in Claude Code — plugin p@m ships a different skill "
            "by that name; both left as they are"]

    def test_plugin_lines_name_eight_and_cut_after_eight(self, sandbox):
        rows = [("s%d" % i, "p@m", "/x", "identical") for i in range(9)]
        assert store.plugin_duplicate_lines(rows[:8])[0].startswith(
            "s0, s1, s2, s3, s4, s5, s6, s7 show twice")
        assert store.plugin_duplicate_lines(rows)[0].startswith(
            "s0, s1, s2, s3, s4, s5, s6, s7, … show twice")

    def test_older_copy_lines(self, sandbox):
        rows = [("pr-me", "Codex", str(paths.home() / ".codex/skills/pr-me"))]
        assert store.older_copy_lines(rows) == [
            "pr-me: the copy in ~/.codex/skills/pr-me (Codex) is older by file "
            "times — left alone"]

    def test_not_skill_line(self, sandbox):
        assert store.not_skill_line(["synced"]) == (
            "~/.agents/skills/synced holds no SKILL.md, so it is not a skill — "
            "left alone")
        assert store.not_skill_line(["a", "b", "c", "d", "e"]) == (
            "5 dirs in ~/.agents/skills hold no SKILL.md, so they are not "
            "skills (a, b, c, d, e) — left alone")
        assert store.not_skill_line(["a", "b", "c", "d", "e", "f"]) == (
            "6 dirs in ~/.agents/skills hold no SKILL.md, so they are not "
            "skills (a, b, c, d, e, …) — left alone")

    def test_misnamed_line(self, sandbox):
        assert store.misnamed_line(["b copy"]) == (
            "~/.agents/skills/b copy: boost cannot record a skill by that name "
            "(only letters, digits, '.', '_' and '-') — left alone")
        assert store.misnamed_line(["b copy", "c copy"]) == (
            "2 dirs in ~/.agents/skills have names boost cannot record a skill "
            "by (b copy, c copy) — left alone")
