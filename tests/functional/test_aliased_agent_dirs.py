# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""One skills dir reached two ways is swept once, and boost's links are
boost's however ``$HOME`` is spelled.

Two agents sharing a dir (``~/.cursor/skills -> ../.claude/skills``) made
doctor count each broken link twice and heal crash with rc 70 unlinking the
same entry a second time. Reached through another spelling of ``$HOME``
(macOS ``/tmp`` -> ``/private/tmp``), uninstall left every agent link
dangling and clean said there was nothing to clean.
"""
from __future__ import annotations

import os
import shutil

import pytest

from boost_cli.core import paths

pytestmark = pytest.mark.skipif(
    os.name == "nt", reason="symlinked directories need POSIX symlinks")


def _links(name):
    """The real dir of every symlink called ``name`` under ``$HOME``.

    ``os.walk`` does not follow a symlinked dir, so a shared dir is walked
    once — the count of links that physically exist.
    """
    found = set()
    for root, dirs, files in os.walk(paths.home()):
        for d in (*dirs, *files):
            p = os.path.join(root, d)
            if d == name and os.path.islink(p):
                found.add(os.path.realpath(root))
    return found


@pytest.fixture()
def shared_dir(boost, tapped):
    """``~/.cursor/skills`` is a symlink to ``~/.claude/skills``."""
    home = paths.home()
    (home / ".claude" / "skills").mkdir(parents=True)
    (home / ".cursor").mkdir()
    (home / ".cursor" / "skills").symlink_to(
        os.path.join("..", ".claude", "skills"))
    boost("install", "brainstorming")
    return home


def test_doctor_counts_each_broken_link_once(boost, shared_dir):
    shutil.rmtree(paths.store_dir() / "brainstorming")
    on_disk = len(_links("brainstorming"))
    out = boost("doctor", expect=1).out
    assert "%d broken symlinks in agent dirs" % on_disk in out


def test_heal_removes_each_link_once_and_reinstalls(boost, shared_dir):
    shutil.rmtree(paths.store_dir() / "brainstorming")
    res = boost("heal")
    assert res.rc == 0
    assert res.out.count(
        "removed broken link ~/.claude/skills/brainstorming") == 1
    assert "~/.cursor/skills/brainstorming" not in res.out
    assert (paths.store_dir() / "brainstorming" / "SKILL.md").is_file()
    link = shared_dir / ".claude" / "skills" / "brainstorming"
    assert os.path.realpath(link) == os.path.realpath(
        paths.store_dir() / "brainstorming")


def test_clean_dry_run_and_clean_agree(boost, shared_dir):
    shutil.rmtree(paths.store_dir() / "brainstorming")
    on_disk = len(_links("brainstorming"))
    assert "%d item(s)" % on_disk in boost("clean", "--dry-run").out
    assert "cleaned %d item(s)" % on_disk in boost("clean").out
    assert _links("brainstorming") == set()


@pytest.fixture()
def respelled_home(boost, installed, monkeypatch):
    """Installed under one spelling of ``$HOME``, now reached by another."""
    real = paths.home()
    alias = real.parent / "home-alias"
    alias.symlink_to(real)
    # Only the spelling is changed; config.json keeps no absolute path here.
    paths.state_dir().joinpath("link-dirs.json").unlink(missing_ok=True)
    monkeypatch.setenv("HOME", str(alias))
    assert paths.home() == alias
    return real


def test_uninstall_removes_links_made_under_the_other_spelling(
        boost, respelled_home):
    assert _links("brainstorming")
    boost("uninstall", "brainstorming")
    assert _links("brainstorming") == set()


def test_clean_sees_dangling_links_made_under_the_other_spelling(
        boost, respelled_home):
    shutil.rmtree(paths.store_dir() / "brainstorming")
    on_disk = len(_links("brainstorming"))
    assert on_disk
    assert "cleaned %d item(s)" % on_disk in boost("clean").out
    assert _links("brainstorming") == set()


def test_a_link_of_the_user_s_is_left_alone_under_either_spelling(
        boost, respelled_home):
    # Never widened to someone else's link: dangling, in a dir boost sweeps,
    # pointing next to the store rather than into it.
    mine = paths.home() / ".claude" / "skills" / "mine"
    mine.symlink_to(respelled_home / ".agents" / "skills-backup" / "mine")
    boost("uninstall", "brainstorming")
    boost("clean")
    boost("heal")
    assert os.path.islink(mine)
    assert os.readlink(mine) == str(
        respelled_home / ".agents" / "skills-backup" / "mine")
