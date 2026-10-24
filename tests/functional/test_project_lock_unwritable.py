# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A read-only ``.boost/`` is one refusal naming it, never a crash report.

Measured before the fix: ``chmod a-w .boost`` then ``boost uninstall NAME
--local`` deleted every agent copy, then crashed at exit 70 on a
PermissionError for ``.boost/.boost-*.tmp`` with a "file an issue" hint, and
``boost list --local`` still listed the skill. ``install --local`` left
unrecorded copies that the rerun then refused. The user scope has long said
which directory and which ``chmod``; the project lock now does too, and asks
before anything on disk changes.
"""
from __future__ import annotations

import os
import sys

import pytest

from boost_cli.core import paths, projectlock

pytestmark = [
    pytest.mark.skipif(sys.platform == "win32",
                       reason="chmod can't make a directory read-only on "
                              "Windows"),
    pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0,
                       reason="root ignores mode bits"),
]


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """A project directory that looks like a git repo, cd'd into."""
    d = tmp_path / "plu repo"
    (d / ".git").mkdir(parents=True)
    monkeypatch.chdir(d)
    return d.resolve()


@pytest.fixture()
def readonly(boost, tapped, repo):
    boost("install", "brainstorming", "--local")
    d = projectlock.lock_path(repo).parent
    raw = projectlock.lock_path(repo).read_bytes()
    d.chmod(0o555)
    try:
        yield d, raw
    finally:
        d.chmod(0o755)


def _flat(text: str) -> str:
    return " ".join(text.split())


def _refusal(verb: str, name: str, d) -> str:
    where = paths.tilde(d)
    return ("Error: cannot %s %s: %s is not writable "
            "hint: run `chmod u+w %s`, then re-run" % (verb, name, where, where))


def _no_crash():
    assert not list(paths.logs_dir().glob("crash-*.log"))


def test_uninstall_refuses_before_removing_a_copy(boost, repo, readonly):
    d, raw = readonly
    r = boost("uninstall", "brainstorming", "--local", expect=1)
    assert _flat(r.err) == _refusal("uninstall", "brainstorming", d)
    _no_crash()
    assert (repo / ".claude" / "skills" / "brainstorming" / "SKILL.md").is_file()
    assert projectlock.lock_path(repo).read_bytes() == raw
    assert "brainstorming" in boost("list", "--local").out


def test_install_refuses_before_copying(boost, repo, readonly):
    d, raw = readonly
    r = boost("install", "cowboy-coding", "--local", expect=1)
    assert _flat(r.err) == _refusal("install", "cowboy-coding", d)
    _no_crash()
    assert not (repo / ".claude" / "skills" / "cowboy-coding").exists()
    assert projectlock.lock_path(repo).read_bytes() == raw


def test_pin_names_the_lock_and_the_chmod(boost, repo, readonly):
    d, raw = readonly
    r = boost("pin", "brainstorming", "--local", expect=1)
    assert _flat(r.err) == (
        "Error: could not save %s (Permission denied): %s is not writable "
        "hint: run `chmod u+w %s`, then re-run"
        % (paths.tilde(projectlock.lock_path(repo)), paths.tilde(d),
           paths.tilde(d)))
    _no_crash()
    assert projectlock.lock_path(repo).read_bytes() == raw


def test_once_writable_the_rerun_succeeds(boost, repo, readonly):
    d, _raw = readonly
    boost("uninstall", "brainstorming", "--local", expect=1)
    d.chmod(0o755)
    boost("uninstall", "brainstorming", "--local")
    assert not (repo / ".claude" / "skills" / "brainstorming").exists()
    assert projectlock.get_skill(repo, "brainstorming") is None
