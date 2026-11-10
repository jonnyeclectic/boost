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
    assert "tapped" in r.out and "(5 items)" in r.out

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


def test_unknown_command_offers_help(boost):
    r = boost("hepl", expect=2)
    assert "did you mean: help" in r.err


def test_mcp_bad_action_names_the_metavar_not_the_dest(boost):
    r = boost("mcp", "bogus", expect=2)
    assert "argument ACTION: invalid choice: 'bogus'" in r.err
    assert "argument action" not in r.err


def test_missing_skill_in_a_named_tap_says_which_tap(boost, tapped):
    r = boost("install", "fixture-tap:nonesuch", expect=1)
    lines = r.err.splitlines()
    assert lines[0] == "Error: no skill named 'nonesuch' in tap fixture-tap"
    assert "hint: try `boost search nonesuch`" in lines[1]


def test_missing_skill_with_no_close_match_still_points_at_search(boost,
                                                                  tapped):
    r = boost("install", "zzqxv", expect=1)
    assert "Error: no skill named 'zzqxv' in any tap" in r.err
    assert "try `boost search zzqxv`" in r.err


def test_multi_install_warning_does_not_repeat_the_name(boost, tapped):
    boost("install", "brainstorming")
    # Already installed at this version is a warning beside the install that
    # did happen, not a failure of the run.
    r = boost("install", "brainstorming", "jira-integration", expect=0)
    assert "brainstorming is already installed" in r.err
    assert "brainstorming: brainstorming" not in r.err


def _disk_state():
    """Every file and link under the sandbox's agent and store dirs, with its
    bytes or target and mtime: what an install that changes nothing must
    leave exactly as it found it."""
    home = paths.home()
    state = {}
    for top in (".agents", ".claude", ".cursor", ".windsurf", ".gemini"):
        root = home / top
        if not root.exists():
            continue
        for p in sorted(root.rglob("*")):
            st = p.lstat()
            state[str(p)] = (str(p.readlink()) if p.is_symlink()
                             else p.read_bytes() if p.is_file() else None,
                             st.st_mtime_ns)
    return state


def test_reinstalling_the_same_version_is_a_warning_and_changes_nothing(
        boost, tapped):
    boost("install", "brainstorming")
    before = _disk_state()
    r = boost("install", "brainstorming", expect=0)
    # The hint stays beside the warning, on stderr, as `Error:`'s does.
    assert r.err == ("  ! brainstorming is already installed (v1.4.0)\n"
                     "  hint: `boost reinstall brainstorming` to force, "
                     "`boost update` to upgrade\n")
    assert "hint:" not in r.out
    assert "installed" not in r.out.replace("already installed", "")
    assert _disk_state() == before


def test_a_dry_run_over_an_installed_skill_still_plans_its_dependency(
        boost, tapped):
    # audit-cli 6: the plan named the missing dependency, then the installed
    # skill turned the whole preview into rc 1 with its name said twice.
    boost("install", "jira-integration", "--no-deps")
    before = _disk_state()
    r = boost("install", "jira-integration", "--dry-run", expect=0)
    assert "would install commit-messages" in r.out
    assert r.err.startswith(
        "  ! jira-integration is already installed (v2.1.0)\n  hint: ")
    assert "dry run — nothing was changed" in r.out
    assert _disk_state() == before
