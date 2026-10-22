# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional: a rule's block present twice in one context file.

A dotfiles merge or two concatenated context files make the shape. doctor,
verify and heal called it healthy; `boost update` rewrote the first copy and
left the stale one live, and uninstall removed only the first copy.
"""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from boost_cli.core import paths, rules, store

RULE = "strict-types"


def _flat(text):
    return " ".join(text.split())


def _commit(tap, body, msg):
    (tap / "rules" / "strict-types.mdc").write_text(
        "---\nname: %s\nversion: 1.0.0\n---\n\n%s\n" % (RULE, body),
        encoding="utf-8")
    subprocess.run(["git", "-C", str(tap), "add", "-A"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tap), "commit", "-qm", msg],
                   check=True, capture_output=True)


@pytest.fixture()
def rule_tap(boost, fixture_tap_src, tmp_path):
    tap = tmp_path / "dup-rule-tap"
    shutil.copytree(fixture_tap_src, tap)
    (tap / "rules").mkdir()
    _commit(tap, "Use strict types everywhere.", "rule")
    boost("tap", tap)
    return tap


def _claude_md():
    return paths.home() / ".claude" / "CLAUDE.md"


def _double(boost):
    """Install, then lay the file out as the finding did."""
    boost("install", RULE)
    c = _claude_md()
    block = c.read_text(encoding="utf-8").strip("\n")
    c.write_text("user top\n%s\nuser middle\n%s\n" % (block, block),
                 encoding="utf-8")
    return block


WANT = ("rule strict-types's block appears 2 times in ~/.claude/CLAUDE.md — "
        "the agent reads every copy; `boost heal` keeps the first")


class TestDuplicatedBlock:
    def test_doctor_verify_and_heal_converge(self, boost, rule_tap):
        block = _double(boost)
        assert store.duplicate_rule_blocks() == [
            (RULE, str(_claude_md()), 2)]
        flat = _flat(boost("doctor", expect=1).out)
        assert WANT in flat
        assert "● healthy" not in flat
        r = boost("verify", expect=1)
        assert ("block appears 2 times in ~/.claude/CLAUDE.md — `boost heal` "
                "keeps the first") in _flat(r.out)
        row = next(x for x in json.loads(boost("verify", "--json",
                                               expect=1).out)["skills"]
                   if x["name"] == RULE)
        assert row["status"] == "modified" and row["passed"] is False
        assert row["duplicate_blocks"] == [
            {"path": "~/.claude/CLAUDE.md", "count": 2}]

        r = boost("heal", "--dry-run")
        assert "re-materialize" not in r.out      # named once, as a dedupe
        assert ("would keep one of rule strict-types's 2 blocks in "
                "~/.claude/CLAUDE.md") in r.out
        assert _claude_md().read_text(encoding="utf-8").count(
            rules.markers(RULE)[0]) == 2
        r = boost("heal")
        assert ("kept one of rule strict-types's 2 blocks in "
                "~/.claude/CLAUDE.md") in r.out
        assert _claude_md().read_text(encoding="utf-8") == (
            "user top\n%s\nuser middle\n" % block)
        assert store.duplicate_rule_blocks() == []
        assert "nothing to heal" in boost("heal").out
        assert WANT not in _flat(boost("doctor", expect=None).out)
        boost("verify")

    def test_update_rewrites_every_copy_and_uninstall_removes_them(
            self, boost, rule_tap):
        _double(boost)
        _commit(rule_tap, "Use strict types everywhere. NEVER use Any.", "v2")
        r = boost("update")
        assert "refreshed rule strict-types" in r.out
        text = _claude_md().read_text(encoding="utf-8")
        assert text.count(rules.markers(RULE)[0]) == 1
        assert "NEVER use Any." in text
        assert text.startswith("user top\n") and "user middle\n" in text
        boost("verify")
        boost("uninstall", RULE)
        assert _claude_md().read_text(encoding="utf-8") == (
            "user top\nuser middle\n")
