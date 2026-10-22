# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""lockfile.rehome: a snapshot's rule/workflow rows land on this $HOME.

Measured before the fix: a snapshot saved under one HOME and restored under
another kept every ``materializations[].path`` under the first, so doctor
called the rows fully materialized off the other home's files and `boost
uninstall` deleted them there.
"""
from __future__ import annotations

import os
import sys

import pytest

from boost_cli.core import lockfile


@pytest.fixture()
def homes(tmp_path):
    old, new = tmp_path / "h1", tmp_path / "h2"
    dirs = {"claude-code": new / ".claude" / "skills",
            "cursor": new / ".cursor" / "skills",
            "antigravity": new / ".gemini" / "antigravity-cli" / "skills"}
    return old, new, dirs


def _rule(*rows, **extra):
    return {"rules": {"r": {"materializations": list(rows), **extra}},
            "workflows": {}, "skills": {}}


def _m(agent, p):
    return {"agent": agent, "path": str(p)}


@pytest.mark.parametrize("recorded", [True, False])
def test_a_row_under_the_old_home_moves_onto_this_one(homes, recorded):
    old, new, dirs = homes
    lock = _rule(_m("claude-code", old / ".claude" / "CLAUDE.md"),
                 _m("cursor", old / ".cursor" / "rules" / "r.mdc"))
    lock["workflows"]["w"] = {
        "materializations": [_m("claude-code",
                                old / ".claude" / "commands" / "w.md")],
        "foreign": [_m("antigravity",
                       old / ".gemini" / "antigravity-cli" / "w.md")]}
    moved, unplaced = lockfile.rehome(lock, new, str(old) if recorded else None,
                                      dirs)
    assert (moved, unplaced) == (["rule r", "workflow w"], [])
    assert [m["path"] for m in lock["rules"]["r"]["materializations"]] == [
        str(new / ".claude" / "CLAUDE.md"),
        str(new / ".cursor" / "rules" / "r.mdc")]
    assert lock["workflows"]["w"]["materializations"][0]["path"] == str(
        new / ".claude" / "commands" / "w.md")
    assert lock["workflows"]["w"]["foreign"][0]["path"] == str(
        new / ".gemini" / "antigravity-cli" / "w.md")


def test_the_last_dotdir_in_the_path_is_the_one(homes):
    # An old home that itself sits under a `.claude` dir: the agent's dotdir
    # is the one nearest the file.
    _old, new, dirs = homes
    p = new.parent / ".claude" / "u" / ".claude" / "CLAUDE.md"
    lock = _rule(_m("claude-code", p))
    assert lockfile.rehome(lock, new, None, dirs) == (["rule r"], [])
    assert lock["rules"]["r"]["materializations"][0]["path"] == str(
        new / ".claude" / "CLAUDE.md")


def test_paths_that_belong_here_are_left_alone(homes, tmp_path):
    old, new, dirs = homes
    custom = tmp_path / "opt" / "agentx" / "skills"
    lock = _rule(_m("claude-code", new / ".claude" / "CLAUDE.md"),
                 _m("agentx", custom.parent / "rules.md"),
                 {"agent": "cursor", "path": "relative/r.mdc"},
                 {"agent": "cursor"},
                 "not-a-row")
    before = repr(lock)
    assert lockfile.rehome(lock, new, str(old),
                           {**dirs, "agentx": custom}) == ([], [])
    assert repr(lock) == before


def test_a_sibling_of_this_home_is_not_inside_it(homes):
    _old, new, dirs = homes
    p = new.parent / (new.name + "-backup") / ".claude" / "CLAUDE.md"
    lock = _rule(_m("claude-code", p))
    assert lockfile.rehome(lock, new, None, dirs) == (["rule r"], [])
    assert lock["rules"]["r"]["materializations"][0]["path"] == str(
        new / ".claude" / "CLAUDE.md")


def test_the_recorded_home_wins_over_inference(homes):
    old, new, dirs = homes
    # Under the old home but not under any agent dotdir: only the recorded
    # home can place it.
    lock = _rule(_m("claude-code", old / "notes" / "CLAUDE.md"))
    assert lockfile.rehome(lock, new, str(old), dirs) == (["rule r"], [])
    assert lock["rules"]["r"]["materializations"][0]["path"] == os.path.join(
        str(new), "notes", "CLAUDE.md")


@pytest.mark.parametrize("agent, rel", [
    ("claude-code", ("notes", "CLAUDE.md")),     # no dotdir in it
    ("nobody", (".claude", "CLAUDE.md")),        # no such agent here
])
def test_a_path_nothing_places_is_unplaced_and_kept(homes, agent, rel):
    old, new, dirs = homes
    p = str(old.joinpath(*rel))
    lock = _rule(_m(agent, p), _m(agent, p))
    assert lockfile.rehome(lock, new, None, dirs) == ([], ["rule r"])
    assert lock["rules"]["r"]["materializations"][0]["path"] == p


def test_an_agent_dir_outside_home_cannot_infer(homes, tmp_path):
    old, new, _dirs = homes
    lock = _rule(_m("agentx", old / ".agentx" / "r.md"))
    assert lockfile.rehome(lock, new, None,
                           {"agentx": tmp_path / "opt" / ".agentx" / "skills"}
                           ) == ([], ["rule r"])


def test_project_rows_and_skills_are_not_touched(homes):
    old, new, dirs = homes
    p = str(old / ".claude" / "CLAUDE.md")
    lock = _rule(_m("claude-code", p), scope="project")
    lock["skills"]["s"] = {"materializations": [_m("claude-code", p)]}
    lock["workflows"]["bad"] = "not-a-row"
    assert lockfile.rehome(lock, new, str(old), dirs) == ([], [])
    assert lock["rules"]["r"]["materializations"][0]["path"] == p
    assert lock["skills"]["s"]["materializations"][0]["path"] == p


def test_a_lock_without_sections_has_nothing(homes):
    _old, new, _dirs = homes
    assert lockfile.rehome({}, new) == ([], [])


def test_an_unrecorded_home_is_inferred_for_rows_no_dotdir_names(homes):
    # Measured on a five-agent install: Gemini's skills dir is the canonical
    # store, so its ~/.gemini rows (and a row with no agent) were unplaceable
    # and every snapshot saved before `home` was recorded was refused.
    old, new, dirs = homes
    dirs = {**dirs, "gemini": new / ".agents" / "skills"}
    lock = _rule(_m("claude-code", old / ".claude" / "CLAUDE.md"),
                 _m("gemini", old / ".gemini" / "GEMINI.md"),
                 {"path": str(old / "x" / "w.md")})
    assert lockfile.rehome(lock, new, None, dirs) == (["rule r"], [])
    assert [m["path"] for m in lock["rules"]["r"]["materializations"]] == [
        str(new / ".claude" / "CLAUDE.md"), str(new / ".gemini" / "GEMINI.md"),
        str(new / "x" / "w.md")]


def test_homes_that_disagree_infer_nothing(homes, tmp_path):
    old, new, dirs = homes
    lock = _rule(_m("claude-code", old / ".claude" / "CLAUDE.md"),
                 _m("cursor", tmp_path / "h3" / ".cursor" / "r.mdc"))
    # One dotdir-less row under each home: whichever guess won, one of
    # them would be placed.
    lock["workflows"]["w"] = {"materializations": [
        _m("gemini", old / ".gemini" / "GEMINI.md")]}
    lock["workflows"]["x"] = {"materializations": [
        _m("gemini", tmp_path / "h3" / ".gemini" / "GEMINI.md")]}
    assert lockfile.rehome(lock, new, None, dirs) == (
        ["rule r"], ["workflow w", "workflow x"])
    assert lock["rules"]["r"]["materializations"][1]["path"] == str(
        new / ".cursor" / "r.mdc")


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privilege")
def test_a_path_under_the_resolved_old_home_lands_inside_this_one(
        homes, tmp_path):
    old, new, dirs = homes
    real = tmp_path / "real"
    (real / ".claude").mkdir(parents=True)
    old.symlink_to(real)
    lock = _rule(_m("claude-code",
                    os.path.join(os.path.realpath(old), "notes", "CLAUDE.md")))
    assert lockfile.rehome(lock, new, str(old), dirs) == (["rule r"], [])
    assert lock["rules"]["r"]["materializations"][0]["path"] == os.path.join(
        str(new), "notes", "CLAUDE.md")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX root")
@pytest.mark.parametrize("recorded", [True, False])
def test_a_home_of_root_lands_inside_this_one(homes, recorded):
    # HOME=/ in a container: "/" stripped to "", which relpath read as cwd.
    _old, new, dirs = homes
    lock = _rule(_m("claude-code", "/.claude/CLAUDE.md"),
                 _m("gemini", "/.gemini/GEMINI.md"))
    assert lockfile.rehome(lock, new, "/" if recorded else None,
                           {**dirs, "gemini": new / ".agents" / "skills"}
                           ) == (["rule r"], [])
    assert [m["path"] for m in lock["rules"]["r"]["materializations"]] == [
        str(new / ".claude" / "CLAUDE.md"), str(new / ".gemini" / "GEMINI.md")]
