# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: the everyday loop from the visual guide, in-process.

tap → search → install → doctor → uninstall, asserting the user-visible
contract (output shapes, exit codes, real symlinks and lock file on disk).
"""
from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import sys

import pytest

from boost_cli.core import lockfile, paths


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


@pytest.mark.parametrize("cmd", ["install", "uninstall", "info"])
def test_an_unknown_flag_is_named_not_reported_as_a_missing_name(boost, cmd):
    r = boost(cmd, "-x", expect=2)
    assert r.err.splitlines()[0] == "Error: unrecognized arguments: -x"
    assert "required" not in r.err


@pytest.mark.parametrize("cmd", ["install", "uninstall", "info"])
def test_a_missing_name_alone_still_says_it_is_required(boost, cmd):
    r = boost(cmd, expect=2)
    assert "the following arguments are required" in r.err.splitlines()[0]


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


def test_reinstalling_for_another_agent_is_still_a_refusal(boost, tapped):
    # Same version, same tap, but the request names an agent the install did
    # not reach: a no-op there would exit 0 with windsurf never linked.
    boost("install", "brainstorming", "--agent", "cursor")
    link = paths.home() / ".windsurf" / "skills" / "brainstorming"
    before = _disk_state()
    r = boost("install", "brainstorming", "--agent", "windsurf", expect=1)
    # cursor is carried: `--agent windsurf --force` alone would declare
    # windsurf only, leaving cursor's link for `sync --prune` to remove.
    hinted = ("boost install fixture-tap:brainstorming --path "
              "skills/brainstorming --agent cursor --agent windsurf --force")
    # Not `boost reinstall`: it replays cursor, the scope being changed.
    assert " ".join(r.err.split()) == (
        "Error: brainstorming is already installed (v1.4.0) "
        "hint: `%s` to apply it" % hinted)
    assert not link.is_symlink()
    assert _disk_state() == before
    # dry run agrees with the run
    r = boost("install", "brainstorming", "--agent", "windsurf", "--dry-run",
              expect=1)
    assert "`%s` to apply it" % hinted in " ".join(r.err.split())
    # ...and the hinted command is the one that does it.
    boost(*shlex.split(hinted)[1:], expect=0)
    assert link.is_symlink()
    assert (paths.home() / ".cursor" / "skills" / "brainstorming").is_symlink()
    assert lockfile.get_skill("brainstorming")["only_agents"] == [
        "cursor", "windsurf"]
    assert "outside its declared scope" not in boost("doctor", expect=None).out


def test_the_hint_for_a_path_with_a_space_runs_as_printed(
        boost, fixture_tap_src, tmp_path):
    tap = tmp_path / "spaced-tap"
    shutil.copytree(fixture_tap_src, tap)
    skill = tap / "my skills" / "spaced"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: spaced\ndescription: lives under a space\n"
        "version: 1.0.0\n---\n\n# Spaced\n\nBody.\n", encoding="utf-8")
    for argv in (["add", "-A"], ["commit", "-qm", "spaced"]):
        subprocess.run(["git", "-C", str(tap), *argv], check=True,
                       capture_output=True)
    boost("tap", tap)
    boost("install", "spaced", "--agent", "cursor")
    r = boost("install", "spaced", "--agent", "windsurf", expect=1)
    hinted = re.search(r"`(boost install [^`]*)` to apply it",
                       " ".join(r.err.split())).group(1)
    path = ('"my skills/spaced"' if sys.platform == "win32"
            else "'my skills/spaced'")
    assert f"--path {path}" in hinted
    boost(*shlex.split(hinted)[1:], expect=0)
    assert (paths.home() / ".windsurf" / "skills" / "spaced").is_symlink()
    assert (paths.home() / ".cursor" / "skills" / "spaced").is_symlink()


def test_reinstalling_for_the_same_agent_is_a_no_op(boost, tapped):
    boost("install", "brainstorming", "--agent", "cursor")
    before = _disk_state()
    r = boost("install", "brainstorming", "--agent", "cursor", expect=0)
    assert r.err.startswith("  ! brainstorming is already installed (v1.4.0)")
    assert _disk_state() == before
