# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: the everyday loop from the visual guide, in-process.

tap → search → install → doctor → uninstall, asserting the user-visible
contract (output shapes, exit codes, real symlinks and lock file on disk).
"""
from __future__ import annotations

import json
import re

from boost_cli.core import paths


def test_tap_search_install_doctor_uninstall(boost, fixture_tap_src):
    r = boost("tap", fixture_tap_src)
    assert "Tapped" in r.out and "(5 items)" in r.out

    r = boost("search", "jira")
    assert "jira-integration" in r.out
    assert "ranked by full-content BM25" in r.out

    # --no-deps keeps this a single-skill lifecycle (doctor asserts "1 skill");
    # jira-integration otherwise pulls in its `requires: commit-messages`.
    r = boost("install", "jira-integration", "--no-deps")
    assert "copied to" in r.out
    assert "linked → claude-code · windsurf · cursor · antigravity" in r.out
    assert "lock updated (.skill-lock.json)" in r.out
    assert "quality score" in r.out

    # real filesystem effects
    store = paths.store_dir() / "jira-integration"
    assert (store / "SKILL.md").is_file()
    for agent_dir in (".claude", ".windsurf", ".cursor"):
        link = paths.home() / agent_dir / "skills" / "jira-integration"
        assert link.is_symlink() and link.resolve() == store.resolve()
    lock = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
    assert lock["version"] == 3
    assert "jira-integration" in lock["skills"]

    r = boost("doctor")
    assert "1 skill installed · 1 tap synced · 0 broken links" in r.out
    assert "lock file integrity OK · log rotation healthy" in r.out

    r = boost("uninstall", "jira-integration")
    assert "unlinked" in r.out
    assert not store.exists()
    assert not (paths.home() / ".claude" / "skills" / "jira-integration").exists()
    assert "jira-integration" not in json.loads(
        paths.lockfile_path().read_text(encoding="utf-8"))["skills"]


def test_install_unknown_skill_fails_with_hint(boost, tapped):
    r = boost("install", "definitely-not-a-skill", expect=1)
    assert "Error" in r.err


def test_unknown_command_suggests_closest(boost):
    r = boost("instal", expect=2)
    assert "install" in r.err


def test_version_and_help(boost):
    assert re.match(r"boost \S+", boost("--version").out)
    r = boost("--help")
    assert "81 commands · 8 groups" in r.out
    for group in ("Package Management", "Discovery & Search", "Intelligence",
                  "Quality & Health", "Team & Collaboration"):
        assert group in r.out
