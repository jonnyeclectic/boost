# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional: a rule's block in a context file that the lock has lost.

With the lock gone, ``<!-- boost:rule:<name> start -->`` stays in
``~/.claude/CLAUDE.md``, `boost uninstall` answers "not installed", and
`boost doctor` used to print "healthy" over a block no command can remove.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

from boost_cli.core import lockfile, paths, rules, store

RULE = "orphan-rule"


def _flat(text):
    return " ".join(text.split())


@pytest.fixture()
def rule_tap(boost, fixture_tap_src, tmp_path):
    tap = tmp_path / "orphan-rule-tap"
    shutil.copytree(fixture_tap_src, tap)
    (tap / "rules").mkdir()
    (tap / "rules" / "orphan.mdc").write_text(
        "---\nname: %s\nversion: 1.0.0\n---\n\nAlways type it.\n" % RULE,
        encoding="utf-8")
    subprocess.run(["git", "-C", str(tap), "add", "-A"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tap), "commit", "-qm", "rule"],
                   check=True, capture_output=True)
    boost("tap", tap)
    return tap


def _claude_md():
    return paths.home() / ".claude" / "CLAUDE.md"


def _context_files():
    """Every user-scope context file a rule's block lands in by default."""
    h = paths.home()
    return [h / ".claude" / "CLAUDE.md", h / ".gemini" / "GEMINI.md",
            h / ".codex" / "AGENTS.md"]


def _lose_lock(boost):
    boost("install", RULE)
    assert ("boost:rule:%s start" % RULE) in _claude_md().read_text(
        encoding="utf-8")
    paths.lockfile_path().unlink()


WANT = ("~/.claude/CLAUDE.md carries the block of rule %s, which the lock "
        "does not record — no boost command removes it until `boost install "
        "%s` re-records it, or delete the block by hand" % (RULE, RULE))


class TestLostLock:
    def test_plan_names_the_block_and_counts_it(self, boost, rule_tap):
        _lose_lock(boost)
        plan = store.sync_plan()
        assert sorted(plan["rule_blocks"]) == sorted(
            (RULE, str(p)) for p in _context_files())
        assert store.plan_issues(plan) == 3
        assert store.orphaned_rule_blocks({RULE: {}}) == []

    def test_doctor_is_not_healthy_over_it(self, boost, rule_tap):
        _lose_lock(boost)
        boost("uninstall", RULE, expect=1)
        flat = _flat(boost("doctor", expect=1).out)
        assert WANT in flat
        assert "● healthy" not in flat
        assert "3 issues need attention" in flat

    def test_the_mcp_doctor_counts_it_as_the_user_s(self, boost, rule_tap):
        from boost_cli.commands import configuration
        _lose_lock(boost)
        text, _ = configuration._tool_doctor({})
        assert WANT in _flat(text)
        assert text.splitlines()[-1] == ("3 issue(s) — 3 are the user's to "
                                         "change, and `boost sync` leaves them")

    def test_heal_and_sync_name_it_and_heal_does_not_exit_0(self, boost,
                                                            rule_tap):
        _lose_lock(boost)
        assert WANT in _flat(boost("heal", expect=1).out)
        assert WANT in _flat(boost("sync").out)
        # Left alone: the block is still there, byte for byte.
        assert ("boost:rule:%s start" % RULE) in _claude_md().read_text(
            encoding="utf-8")

    def test_the_named_install_re_records_and_converges(self, boost,
                                                        rule_tap):
        _lose_lock(boost)
        boost("install", RULE)
        assert lockfile.installed_rules().get(RULE) is not None
        text = _claude_md().read_text(encoding="utf-8")
        assert text.count("boost:rule:%s start" % RULE) == 1
        assert store.sync_plan()["rule_blocks"] == []
        assert "● healthy" in _flat(boost("doctor").out)
        boost("uninstall", RULE)
        for p in _context_files():
            assert (not p.exists()
                    or "boost:rule:%s" % RULE not in p.read_text(
                        encoding="utf-8"))

    def test_a_corrupt_lock_reports_no_block(self, boost, rule_tap):
        boost("install", RULE)
        paths.lockfile_path().write_text("{not json", encoding="utf-8")
        assert store.sort_unrecorded({})["rule_blocks"] == []


class TestBlockNames:
    def test_names_each_start_marker_once_in_order(self):
        text = ("x\n<!-- boost:rule:b start -->\n# B\n<!-- boost:rule:b end -->"
                "\n<!-- boost:rule:a start -->\n<!-- boost:rule:b start -->\n")
        assert rules.block_names(text) == ["b", "a"]

    def test_ignores_what_no_rule_could_be_named(self):
        assert rules.block_names("<!-- boost:rule:../x start -->") == []
        assert rules.block_names("<!-- boost:rule: start -->") == []
        assert rules.block_names("<!-- boost:rule:a end -->") == []
        assert rules.block_names("<!-- boost:rule:a") == []
        assert rules.block_names("<!-- boost:rule:a\nb start -->") == []
        assert rules.block_names("") == []
