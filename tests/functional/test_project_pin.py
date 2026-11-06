# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A skill installed `--local` can be pinned, unpinned and reinstalled.

Its row lives in ``<repo>/.boost/skill-lock.json``, and `pin`, `unpin` and
`reinstall` read only the user lock: they answered "not installed" beside a
`boost list` that showed the skill, so `boost update` always moved it
although its loop honours a project pin.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

from boost_cli.core import integrity, lockfile, projectlock


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t.test", "-c", "user.name=t",
                    *args], cwd=str(cwd), check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    d = tmp_path / "ppd-repo"
    (d / ".git").mkdir(parents=True)
    monkeypatch.chdir(d)
    return d.resolve()


@pytest.fixture()
def src(boost, fixture_tap_src, tmp_path):
    copy = tmp_path / "ppd-tap"
    shutil.copytree(fixture_tap_src, copy)
    boost("tap", copy)
    return copy


def _bump_cowboy(src):
    md = src / "skills" / "cowboy-coding" / "SKILL.md"
    md.write_text(md.read_text(encoding="utf-8")
                  .replace("version: 0.1.0", "version: 0.2.0")
                  + "\nnew upstream line\n", encoding="utf-8")
    _git(src, "commit", "-qam", "bump cowboy-coding")


def _said(r):
    return " ".join((r.out + r.err).split())


def _project_md(repo, name):
    entry = projectlock.get_skill(repo, name)
    assert entry is not None
    d = integrity.project_skill_dir(entry, repo)
    assert d is not None
    return d / "SKILL.md"


class TestPinAProjectSkill:
    def test_pin_writes_the_project_lock_and_update_holds_it(
            self, boost, src, repo):
        boost("install", "--local", "cowboy-coding")
        r = boost("pin", "cowboy-coding")
        assert ("pinned cowboy-coding (project) at v0.1.0 — `boost update` "
                "will skip it") in _said(r)
        assert projectlock.get_skill(repo, "cowboy-coding")["pinned"] is True
        assert lockfile.get_skill("cowboy-coding") is None
        _bump_cowboy(src)
        r = boost("update")
        said = _said(r)
        assert "upgraded cowboy-coding" not in said
        assert ("1 pinned item has an update held back — `boost outdated` "
                "lists it, `boost unpin <name>` lets one update") in said
        assert projectlock.get_skill(repo, "cowboy-coding")["version"] == "0.1.0"

    def test_pin_twice_says_already_pinned(self, boost, src, repo):
        boost("install", "--local", "cowboy-coding")
        boost("pin", "cowboy-coding")
        r = boost("pin", "cowboy-coding")
        assert "cowboy-coding (project) is already pinned at v0.1.0" in _said(r)

    def test_unpin_releases_it_and_update_moves_it(self, boost, src, repo):
        boost("install", "--local", "cowboy-coding")
        boost("pin", "cowboy-coding")
        r = boost("unpin", "cowboy-coding")
        assert ("unpinned cowboy-coding (project) (v0.1.0) — updates apply "
                "again") in _said(r)
        assert "pinned" not in projectlock.get_skill(repo, "cowboy-coding")
        r = boost("unpin", "cowboy-coding")
        assert "cowboy-coding (project) is already unpinned" in _said(r)
        _bump_cowboy(src)
        boost("update")
        assert projectlock.get_skill(repo, "cowboy-coding")["version"] == "0.2.0"

    def test_commit_pin_is_refused_and_writes_nothing(self, boost, src, repo):
        boost("install", "--local", "cowboy-coding")
        r = boost("pin", "--commit", "cowboy-coding", expect=1)
        assert ("cowboy-coding is installed at project scope — --commit "
                "applies to user-scope installs") in _said(r)
        assert "pinned" not in projectlock.get_skill(repo, "cowboy-coding")

    def test_a_name_in_neither_lock_is_still_not_installed(
            self, boost, src, repo):
        r = boost("pin", "nope-not-here", expect=1)
        assert "nope-not-here is not installed" in _said(r)


class TestReinstallAProjectSkill:
    def test_reinstall_restores_the_repo_copy_and_keeps_the_pin(
            self, boost, src, repo):
        boost("install", "--local", "cowboy-coding")
        boost("pin", "cowboy-coding")
        md = _project_md(repo, "cowboy-coding")
        original = md.read_text(encoding="utf-8")
        md.write_text(original + "\nlocal edit\n", encoding="utf-8")
        r = boost("reinstall", "cowboy-coding")
        assert "reinstalled cowboy-coding v0.1.0 (this repo)" in _said(r)
        assert md.read_text(encoding="utf-8") == original
        entry = projectlock.get_skill(repo, "cowboy-coding")
        assert entry["pinned"] is True
        assert entry["scope"] == "project"
        assert "base" not in entry
        assert lockfile.get_skill("cowboy-coding") is None

    def test_reinstall_of_a_pinned_moved_project_skill_is_held(
            self, boost, src, repo):
        boost("install", "--local", "cowboy-coding")
        boost("pin", "cowboy-coding")
        _bump_cowboy(src)
        boost("update")
        r = boost("reinstall", "cowboy-coding", expect=1)
        assert ("cowboy-coding: not reinstalled — pinned at v0.1.0, and its "
                "source has changed since") in _said(r)
        assert projectlock.get_skill(repo, "cowboy-coding")["version"] == "0.1.0"
