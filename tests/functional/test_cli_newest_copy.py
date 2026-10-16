# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost sync`, `doctor`, `heal` and `update` when a plugin ships a different
skill under a name boost installed, and the dates say which copy is newer.

The fixture tap's one commit is made when the session starts, so a plugin
checkout committed in 2100 is newer than boost's copy and one committed in
2020 is older.
"""
from __future__ import annotations

import json
import os
import re
import subprocess

from boost_cli.core import paths

PLUGIN = "eight-backend@eight"
OLD, FUTURE = 1577836800, 4102444800       # 2020-01-01, 2100-01-01


def _flat(text):
    return " ".join(text.split())


def _lock():
    return json.loads(paths.lockfile_path().read_text(encoding="utf-8"))["skills"]


def _git_plugin(claude_plugin, when):
    """A plugin whose checkout has the history to date its skill exactly."""
    theirs = claude_plugin(body="# the plugin's own brainstorming\n")
    root = theirs.parent.parent
    env = os.environ | {"GIT_AUTHOR_DATE": "@%d +0000" % when,
                        "GIT_COMMITTER_DATE": "@%d +0000" % when}
    for args in (["init", "-q"], ["config", "user.email", "t@test"],
                 ["config", "user.name", "T"], ["add", "-A"],
                 ["commit", "-qm", "c"]):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                       env=env)
    return theirs


def _link():
    return paths.home() / ".claude" / "skills" / "brainstorming"


class TestAPluginsNewerCopyWins:
    def test_sync_names_it_and_prune_drops_boosts_link(self, boost, installed,
                                                       claude_plugin):
        _git_plugin(claude_plugin, FUTURE)
        r = boost("sync")
        assert ("brainstorming shows twice in Claude Code — plugin %s ships a "
                "newer copy (by commit dates); `boost sync --prune` drops "
                "boost's older Claude Code link" % PLUGIN) in _flat(r.out)
        assert "everything in sync" not in r.out
        assert _link().is_symlink()
        r = boost("sync", "--prune")       # BOOST_ASSUME_YES confirms
        assert ("unlinked brainstorming → claude-code (Claude Code loads plugin "
                "%s's newer copy, by commit dates)" % PLUGIN) in _flat(r.out)
        assert not os.path.lexists(_link())
        assert (paths.home() / ".cursor" / "skills" / "brainstorming").is_symlink()
        assert "claude-code" not in _lock()["brainstorming"]["agents"]
        r = boost("sync")
        assert "everything in sync" in r.out
        assert not os.path.lexists(_link()), "sync does not bring the link back"

    def test_the_prune_prompt_says_newer_copy(self, boost, installed,
                                              claude_plugin, monkeypatch):
        _git_plugin(claude_plugin, FUTURE)
        monkeypatch.delenv("BOOST_ASSUME_YES")
        r = boost("sync", "--prune")       # non-tty stdin declines
        assert ("1 skill still linked into Claude Code beside a plugin's copy "
                "(declined): brainstorming") in _flat(r.out)
        assert _link().is_symlink()

    def test_install_makes_no_claude_code_link(self, boost, tapped, claude_plugin):
        boost("install", "brainstorming")
        _git_plugin(claude_plugin, FUTURE)
        boost("uninstall", "brainstorming")
        boost("install", "brainstorming")
        assert not os.path.lexists(_link())
        assert (paths.home() / ".cursor" / "skills" / "brainstorming").is_symlink()

    def test_doctor_counts_it_until_prune(self, boost, installed, claude_plugin):
        _git_plugin(claude_plugin, FUTURE)
        r = boost("doctor", expect=1)
        assert ("brainstorming shows twice in Claude Code — plugin %s ships a "
                "newer copy" % PLUGIN) in _flat(r.out)
        r = boost("heal")
        assert "ships a newer copy" in _flat(r.out)
        assert _link().is_symlink()
        boost("sync", "--prune")
        r = boost("doctor")
        assert "shows twice" not in r.out and "● healthy" in r.out
        assert re.search(r"claude-code\s+1/1 ✓", boost("health").out)


class TestBoostsNewerCopyKeepsItsLink:
    HINT = ("brainstorming shows twice in Claude Code — boost's copy is newer "
            "than plugin %s's (by commit dates), which still loads; boost "
            "leaves Claude Code's plugin settings alone — to list only "
            "boost's, disable %s with `/plugin` in Claude Code, which turns "
            "off all of its skills" % (PLUGIN, PLUGIN))

    def test_sync_keeps_the_link_and_says_how_to_disable_the_plugin(
            self, boost, installed, claude_plugin):
        _git_plugin(claude_plugin, OLD)
        r = boost("sync", "--prune")
        assert self.HINT in _flat(r.out)
        assert "everything in sync" in r.out
        assert _link().is_symlink()
        settings = paths.home() / ".claude" / "settings.json"
        assert json.loads(settings.read_text(encoding="utf-8"))[
            "enabledPlugins"] == {PLUGIN: True}, "boost never writes it"

    def test_doctor_notes_it(self, boost, installed, claude_plugin):
        _git_plugin(claude_plugin, OLD)
        assert self.HINT in _flat(boost("doctor").out)

    def test_sync_json_carries_the_verdict(self, boost, installed, claude_plugin):
        theirs = _git_plugin(claude_plugin, OLD)
        got = json.loads(boost("sync", "--json").out)["plugin_duplicates"]
        assert got == [["brainstorming", PLUGIN, str(theirs), "newer-in-boost:git"]]


class TestUpdateDatesWhatWasInstalledBefore:
    def test_a_skill_with_no_date_gets_one(self, boost, installed):
        lock = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
        want = lock["skills"]["brainstorming"].pop("source_updated_at")
        paths.lockfile_path().write_text(json.dumps(lock), encoding="utf-8")
        boost("update")
        assert _lock()["brainstorming"]["source_updated_at"] == want
