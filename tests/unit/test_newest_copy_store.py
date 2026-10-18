# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Newest copy wins: boost's Claude Code link beside a plugin's copy of a skill.

Two different skills that share a name both load in Claude Code, so it lists
the name twice. Boost cannot turn a plugin off, but it can stop serving its
own copy, so when the dates show the plugin's copy is the newer, boost's
Claude Code link goes the way an identical copy's does: none is made, and
``sync --prune`` drops one already there. When boost's copy is the newer, its
link stays and the user is told how to disable the plugin. When the dates
cannot say, nothing changes. Every other agent keeps boost's link throughout.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from boost_cli.core import (
    agents,
    catalog,
    foreign,
    gitutil,
    lockfile,
    paths,
    registry,
    store,
    util,
)

PLUGIN = "eight-backend@eight"
LINKED = ["claude-code", "windsurf", "cursor", "antigravity"]
REST = [a for a in LINKED if a != "claude-code"]
OLD, NEW = 1577836800, 1609459200          # 2020-01-01, 2021-01-01
#: Later than any commit the fixture tap can have been made at.
FUTURE = 4102444800                        # 2100-01-01


@pytest.fixture()
def installed(sandbox, fixture_tap_src):
    t = registry.add(str(fixture_tap_src))
    catalog.rebuild_tap(t)
    store.install(catalog.resolve_one("brainstorming"))
    return t


def _git(*args, cwd, when=None):
    env = os.environ.copy()
    if when is not None:
        env |= {"GIT_AUTHOR_DATE": "@%d +0000" % when,
                "GIT_COMMITTER_DATE": "@%d +0000" % when}
    return subprocess.run(["git", *args], cwd=str(cwd), check=True,
                          capture_output=True, text=True, env=env)


def _commit_all(root: Path, when: int) -> None:
    if not (root / ".git").exists():
        _git("init", "-q", cwd=root)
        _git("config", "user.email", "t@test", cwd=root)
        _git("config", "user.name", "T", cwd=root)
    _git("add", "-A", cwd=root)
    _git("commit", "-qm", "c", cwd=root, when=when)


def _git_plugin(claude_plugin, when: int, body: str = "# the plugin's\n",
                pid: str = PLUGIN) -> Path:
    """A plugin whose cache checkout has the history to date its skill exactly."""
    theirs = claude_plugin(body=body, pid=pid)
    _commit_all(theirs.parent.parent, when)
    return theirs


def _cache_plugin(claude_plugin, when: float, body: str = "# the plugin's\n") -> Path:
    """A plugin installed as most are: no history, file times from the install."""
    theirs = claude_plugin(body=body)
    os.utime(theirs / "SKILL.md", (when, when))
    return theirs


def _date(name: str = "brainstorming", when: int | None = None) -> None:
    e = lockfile.get_skill(name)
    if when is None:
        e.pop("source_updated_at", None)
    else:
        e["source_updated_at"] = util.iso_from_epoch(when)
    lockfile.set_skill(name, e)


def _claude_link(name: str = "brainstorming") -> Path:
    return paths.home() / ".claude" / "skills" / name


def _tap_date(tap, rel: str = "skills/brainstorming") -> str:
    out = _git("log", "-1", "--format=%ct", "--", rel, cwd=tap.path).stdout
    return util.iso_from_epoch(int(out))


class TestInstallRecordsTheDate:
    def test_the_newest_commit_touching_the_skill(self, installed):
        e = lockfile.get_skill("brainstorming")
        assert e["source_updated_at"] == _tap_date(installed)
        assert util.epoch_from_iso(e["source_updated_at"]) is not None

    def test_survives_the_lock_round_trip(self, installed):
        before = lockfile.get_skill("brainstorming")["source_updated_at"]
        lockfile.write(lockfile.read())
        assert lockfile.get_skill("brainstorming")["source_updated_at"] == before

    def test_an_unknown_date_writes_no_field(self, installed, monkeypatch):
        monkeypatch.setattr(gitutil, "path_updated_at", lambda *a, **k: None)
        store.install(catalog.resolve_one("brainstorming"), force=True)
        assert "source_updated_at" not in lockfile.get_skill("brainstorming")


class TestSourceUpdatedAt:
    def test_a_tap_skill(self, installed):
        got = store.source_updated_at(installed.name, "skills/brainstorming")
        assert got == _tap_date(installed)

    @pytest.mark.parametrize("tap", [None, "", "local", "no-such-tap"])
    def test_no_tap_to_read(self, installed, tap):
        assert store.source_updated_at(tap, "skills/brainstorming") is None

    def test_a_tap_not_cloned(self, installed, monkeypatch):
        shutil.rmtree(installed.path)
        monkeypatch.setattr(gitutil, "run", lambda *a, **k: pytest.fail("ran git"))
        assert store.source_updated_at(installed.name, ".") is None

    def test_no_git(self, installed, monkeypatch):
        monkeypatch.setattr(gitutil, "has_git", lambda: False)
        assert store.source_updated_at(installed.name, ".") is None

    def test_a_shallow_tap_is_deepened_first(self, sandbox, tmp_path):
        src = tmp_path / "src"
        (src / "skills" / "a").mkdir(parents=True)
        (src / "skills" / "a" / "SKILL.md").write_text(
            "---\nname: a\ndescription: d\n---\n# a\n", encoding="utf-8")
        _commit_all(src, OLD)
        (src / "README.md").write_text("x", encoding="utf-8")
        _commit_all(src, NEW)
        tap = registry.add(str(src))
        # A path clone ignores --depth; re-clone over file:// as a real tap is.
        util.rmtree(tap.path)
        gitutil.clone_shallow(src.as_uri(), tap.path)
        assert gitutil.is_shallow(tap.path)
        assert store.source_updated_at(tap.name, "skills/a") == util.iso_from_epoch(OLD)
        assert not gitutil.is_shallow(tap.path)

    def test_at_a_revision(self, installed):
        assert store.source_updated_at(installed.name, ".", rev="f" * 40) is None


class TestBackfill:
    def test_dates_a_skill_installed_before_dates_were_kept(self, installed):
        want = lockfile.get_skill("brainstorming")["source_updated_at"]
        _date(when=None)
        assert store.backfill_source_dates([installed.name]) == ["brainstorming"]
        assert lockfile.get_skill("brainstorming")["source_updated_at"] == want

    def test_a_dated_skill_is_left_as_it_is(self, installed):
        _date(when=OLD)
        assert store.backfill_source_dates([installed.name]) == []
        assert lockfile.get_skill("brainstorming")["source_updated_at"] == (
            util.iso_from_epoch(OLD))

    def test_only_the_taps_named(self, installed):
        _date(when=None)
        assert store.backfill_source_dates(["other"]) == []
        assert "source_updated_at" not in lockfile.get_skill("brainstorming")

    def test_not_an_import(self, installed):
        _date(when=None)
        e = lockfile.get_skill("brainstorming")
        lockfile.set_skill("brainstorming", {**e, "source_url": "https://x/y"})
        assert store.backfill_source_dates([installed.name]) == []

    def test_read_at_the_installed_commit(self, installed, monkeypatch):
        _date(when=None)
        seen = []
        monkeypatch.setattr(store, "source_updated_at",
                            lambda tap, rel, rev: seen.append((tap, rel, rev)))
        store.backfill_source_dates([installed.name])
        e = lockfile.get_skill("brainstorming")
        assert seen == [(installed.name, "skills/brainstorming", e["commit"])]

    def test_an_undatable_skill_is_skipped(self, installed, monkeypatch):
        _date(when=None)
        monkeypatch.setattr(store, "source_updated_at", lambda *a: None)
        assert store.backfill_source_dates([installed.name]) == []
        assert "source_updated_at" not in lockfile.get_skill("brainstorming")


class TestPluginCoverage:
    def test_a_plugin_copy_with_newer_commits(self, claude_plugin, installed):
        theirs = _git_plugin(claude_plugin, NEW)
        _date(when=OLD)
        assert store.plugin_coverage(lockfile.installed()) == {
            "brainstorming": (PLUGIN, str(theirs), "newer-in-plugin:git")}

    def test_boosts_copy_newer(self, claude_plugin, installed):
        theirs = _git_plugin(claude_plugin, OLD)
        _date(when=NEW)
        assert store.plugin_coverage(lockfile.installed()) == {
            "brainstorming": (PLUGIN, str(theirs), "newer-in-boost:git")}

    def test_newer_than_an_install_date_proves_nothing(self, claude_plugin,
                                                        installed):
        theirs = _cache_plugin(claude_plugin, NEW)
        _date(when=OLD)
        assert store.plugin_coverage(lockfile.installed()) == {
            "brainstorming": (PLUGIN, str(theirs), "differs")}

    def test_older_than_an_install_date_shows_boosts_is_newer(self, claude_plugin,
                                                               installed):
        theirs = _cache_plugin(claude_plugin, OLD)
        _date(when=NEW)
        assert store.plugin_coverage(lockfile.installed()) == {
            "brainstorming": (PLUGIN, str(theirs), "newer-in-boost:upper-bound")}

    def test_no_date_for_boosts_copy_reads_nothing(self, claude_plugin, installed,
                                                   monkeypatch):
        theirs = _git_plugin(claude_plugin, NEW)
        _date(when=None)
        monkeypatch.setattr(foreign, "plugin_skill_updated_at",
                            lambda *a: pytest.fail("dated"))
        assert store.plugin_coverage(lockfile.installed()) == {
            "brainstorming": (PLUGIN, str(theirs), "differs")}

    def test_identical_whatever_the_dates(self, claude_plugin, installed):
        theirs = claude_plugin()
        _commit_all(theirs.parent.parent, FUTURE)
        _date(when=OLD)
        assert store.plugin_coverage(lockfile.installed()) == {
            "brainstorming": (PLUGIN, str(theirs), "identical")}

    def test_the_newest_of_two_newer_plugins(self, claude_plugin, installed):
        _date(when=OLD)
        _git_plugin(claude_plugin, NEW, pid="a-first@m")
        second = _git_plugin(claude_plugin, NEW + 10, pid="b-second@m")
        assert store.plugin_coverage(lockfile.installed()) == {
            "brainstorming": ("b-second@m", str(second), "newer-in-plugin:git")}

    def test_a_newer_plugin_over_an_older_one_listed_first(self, claude_plugin,
                                                           installed):
        _date(when=NEW)
        _git_plugin(claude_plugin, OLD, pid="a-first@m")
        second = _git_plugin(claude_plugin, NEW + 10, pid="b-second@m")
        assert store.plugin_coverage(lockfile.installed()) == {
            "brainstorming": ("b-second@m", str(second), "newer-in-plugin:git")}

    def test_otherwise_the_first_plugins_verdict(self, claude_plugin, installed):
        _date(when=NEW)
        first = _git_plugin(claude_plugin, OLD, pid="a-first@m")
        _git_plugin(claude_plugin, OLD + 10, pid="b-second@m")
        assert store.plugin_coverage(lockfile.installed()) == {
            "brainstorming": ("a-first@m", str(first), "newer-in-boost:git")}


class TestServingPlugin:
    def test_identical(self, claude_plugin, installed):
        theirs = claude_plugin()
        plugin, path, how = store.serving_plugin("brainstorming", None)
        assert (plugin.id, path, how) == (PLUGIN, theirs, "identical")

    def test_a_newer_plugin_copy(self, claude_plugin, installed):
        theirs = _git_plugin(claude_plugin, NEW)
        plugin, path, how = store.serving_plugin("brainstorming",
                                                 util.iso_from_epoch(OLD))
        assert (plugin.id, path, how) == (PLUGIN, theirs, "newer-in-plugin:git")

    @pytest.mark.parametrize("ours", [None, "garbage", "2021-01-01T00:00:00Z"])
    def test_not_an_older_or_undated_one(self, claude_plugin, installed, ours):
        _git_plugin(claude_plugin, NEW)
        assert store.serving_plugin("brainstorming", ours) is None

    def test_no_plugins(self, installed):
        assert store.serving_plugin("brainstorming", None) is None
        assert store.serving_plugin("brainstorming", None, {}) is None

    def test_a_plugin_shipping_another_name(self, claude_plugin, installed):
        claude_plugin("tdd-workflow", "# x\n")
        assert store.serving_plugin("brainstorming", None) is None


class TestPluginServes:
    @pytest.mark.parametrize("how,want", [
        ("identical", True), ("newer-in-plugin:git", True),
        ("newer-in-plugin:files", True), ("newer-in-boost:git", False),
        ("newer-in-boost:upper-bound", False), ("differs", False)])
    def test_each_verdict(self, how, want):
        assert store.plugin_serves(how) is want

    def test_covered_skills_follow_it(self):
        assert store.covered_skills({
            "a": (PLUGIN, "/a", "identical"), "b": (PLUGIN, "/b", "newer-in-plugin:git"),
            "c": (PLUGIN, "/c", "newer-in-boost:git"), "d": (PLUGIN, "/d", "differs"),
        }) == {"a", "b"}

    def test_plan_issues_follow_it(self):
        plan = {"plugin_duplicates": [("a", "p", "/a", "identical"),
                                      ("b", "p", "/b", "newer-in-plugin:files"),
                                      ("c", "p", "/c", "newer-in-boost:git"),
                                      ("d", "p", "/d", "differs")]}
        assert store.plan_issues(plan) == 2


class TestLinkAgents:
    def test_install_makes_no_claude_code_link_beside_a_newer_copy(
            self, claude_plugin, installed):
        _git_plugin(claude_plugin, FUTURE)
        store.uninstall("brainstorming")
        res = store.install(catalog.resolve_one("brainstorming"))
        assert res.covered == [PLUGIN] and res.linked == REST
        assert not os.path.lexists(_claude_link())
        assert lockfile.get_skill("brainstorming")["agents"] == REST

    def test_install_links_beside_an_older_copy(self, claude_plugin, installed):
        _git_plugin(claude_plugin, OLD)
        store.uninstall("brainstorming")
        res = store.install(catalog.resolve_one("brainstorming"))
        assert res.covered == [] and res.linked == LINKED
        assert _claude_link().is_symlink()

    def test_the_date_being_installed_decides_not_the_lock(self, claude_plugin,
                                                          installed, monkeypatch):
        # The lock still holds the old version's date; the install's is newer.
        _git_plugin(claude_plugin, NEW)
        _date(when=OLD)
        _claude_link().unlink()
        res = store.install(catalog.resolve_one("brainstorming"), force=True)
        assert "claude-code" in res.linked

    def test_others_read_the_lock(self, claude_plugin, installed):
        _git_plugin(claude_plugin, NEW)
        _date(when=OLD)
        _claude_link().unlink()
        res = store.link_agents("brainstorming")
        assert res.covered == [PLUGIN] and res.linked == REST
        _date(when=NEW + 1)
        assert store.link_agents("brainstorming").linked == LINKED

    def test_an_explicit_date_overrides_the_lock(self, claude_plugin, installed):
        _git_plugin(claude_plugin, NEW)
        _date(when=OLD)
        _claude_link().unlink()
        res = store.link_agents("brainstorming", updated_at=None)
        assert res.linked == LINKED

    def test_an_existing_link_stays_until_prune(self, claude_plugin, installed):
        _git_plugin(claude_plugin, NEW)
        _date(when=OLD)
        assert store.link_agents("brainstorming").linked == LINKED


class TestSyncPlan:
    def test_a_newer_plugin_copys_row(self, claude_plugin, installed):
        theirs = _git_plugin(claude_plugin, NEW)
        _date(when=OLD)
        plan = store.sync_plan()
        assert plan["plugin_duplicates"] == [
            ("brainstorming", PLUGIN, str(theirs), "newer-in-plugin:git")]
        assert store.plan_issues(plan) == 1

    def test_its_missing_link_is_no_repair(self, claude_plugin, installed):
        _git_plugin(claude_plugin, NEW)
        _date(when=OLD)
        _claude_link().unlink()
        plan = store.sync_plan()
        assert plan["missing_links"] == plan["plugin_duplicates"] == []

    def test_an_older_plugin_copy_still_gets_boosts_link(self, claude_plugin,
                                                         installed):
        _git_plugin(claude_plugin, OLD)
        _date(when=NEW)
        _claude_link().unlink()
        assert store.sync_plan()["missing_links"] == [
            ("brainstorming", "claude-code")]

    def test_other_agents_are_repaired_either_way(self, claude_plugin, installed):
        _git_plugin(claude_plugin, NEW)
        _date(when=OLD)
        (agents.linking_agents()["windsurf"] / "brainstorming").unlink()
        assert store.sync_plan()["missing_links"] == [("brainstorming", "windsurf")]


class TestDropPluginLink:
    def _row(self, theirs, how="newer-in-plugin:git"):
        return ("brainstorming", PLUGIN, str(theirs), how)

    def test_drops_the_link_to_the_older_copy(self, claude_plugin, installed):
        theirs = _git_plugin(claude_plugin, NEW)
        _date(when=OLD)
        ok, line = store.drop_plugin_link(self._row(theirs))
        assert ok and not os.path.lexists(_claude_link())
        assert line == ("unlinked brainstorming → claude-code (Claude Code loads "
                        "plugin %s's newer copy, by commit dates)" % PLUGIN)
        assert lockfile.get_skill("brainstorming")["agents"] == REST

    def test_kept_once_boosts_copy_is_the_newer(self, claude_plugin, installed):
        theirs = _git_plugin(claude_plugin, NEW)
        _date(when=NEW + 1)
        ok, line = store.drop_plugin_link(self._row(theirs))
        assert not ok and _claude_link().is_symlink()
        assert line == ("kept brainstorming → claude-code: plugin %s's copy is "
                        "no longer the newer one" % PLUGIN)

    def test_an_identical_rows_wording_is_unchanged(self, claude_plugin, installed):
        theirs = _git_plugin(claude_plugin, NEW)
        _date(when=NEW + 1)
        ok, line = store.drop_plugin_link(self._row(theirs, "identical"))
        assert not ok
        assert line.endswith("it no longer matches the copy in plugin %s" % PLUGIN)


class TestWording:
    ROWS = (("a", "p@m", "/a", "identical"),
            ("b", "p@m", "/b", "newer-in-plugin:git"),
            ("c", "q@m", "/c", "newer-in-plugin:files"),
            ("d", "p@m", "/d", "newer-in-boost:upper-bound"),
            ("e", "p@m", "/e", "differs"))

    def test_newer_plugin_copies(self):
        assert store.plugin_newer_lines(self.ROWS) == [
            "b shows twice in Claude Code — plugin p@m ships a newer copy (by "
            "commit dates); `boost sync --prune` drops boost's older Claude "
            "Code link",
            "c shows twice in Claude Code — plugin q@m ships a newer copy (by "
            "boost's commits against the plugin's file times); `boost sync "
            "--prune` drops boost's older Claude Code link"]

    def test_duplicate_lines_carry_them_after_the_identical(self):
        lines = store.plugin_duplicate_lines(self.ROWS)
        assert len(lines) == 3 and lines[0].startswith("a shows twice")
        assert lines[1:] == store.plugin_newer_lines(self.ROWS)

    def test_variant_lines(self):
        assert store.plugin_variant_lines(self.ROWS) == [
            "d shows twice in Claude Code — boost's copy is newer than plugin "
            "p@m's (by boost's commits against the plugin's install date), "
            "which still loads; boost leaves Claude Code's plugin settings "
            "alone — to list only boost's, disable p@m with `/plugin` in "
            "Claude Code, which turns off all of its skills",
            "e shows twice in Claude Code — plugin p@m ships a different skill "
            "by that name; both left as they are"]

    @pytest.mark.parametrize("source,words", [
        ("git", "commit dates"),
        ("files", "boost's commits against the plugin's file times"),
        ("upper-bound", "boost's commits against the plugin's install date"),
        ("", "dates boost could not place")])
    def test_date_words(self, source, words):
        assert foreign.date_words(source) == words

    def test_how_round_trips(self):
        assert foreign.dated_how(foreign.NEWER_IN_PLUGIN, "git") == "newer-in-plugin:git"
        assert foreign.dated_how(foreign.DIFFERS, "git") == "differs"
        assert foreign.split_how("newer-in-boost:files") == ("newer-in-boost", "files")
        assert foreign.split_how("identical") == ("identical", "")
