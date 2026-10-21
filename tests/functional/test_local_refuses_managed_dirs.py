# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""``install --local`` refuses boost's own managed dirs and bare repos.

None of them carries a project marker, so the unmarked fallback claimed them:
from an installed skill's store dir it wrote agent dirs into the skill (and
``verify`` then called it modified), from a tap clone it planted copies the
next rescan indexed as that tap's items, and in a bare repo it wrote files no
commit can carry.
"""
from __future__ import annotations

from boost_cli.core import paths

_DIRS = (".boost", ".claude", ".cursor", ".gemini", ".windsurf", ".codex")


def _assert_untouched(d, before):
    assert sorted(p.name for p in d.iterdir()) == before
    for name in _DIRS:
        assert not (d / name).exists()


def test_refused_inside_an_installed_skills_store_dir(boost, installed,
                                                      monkeypatch):
    d = paths.store_dir() / "brainstorming"
    before = sorted(p.name for p in d.iterdir())
    monkeypatch.chdir(d)
    r = boost("install", "brainstorming", "--local", expect=1)
    assert ("cannot install --local here: ~/.agents/skills/brainstorming is "
            "inside boost's skill store (~/.agents/skills)") in r.err
    assert "starts a new one here" not in r.out + r.err
    _assert_untouched(d, before)
    monkeypatch.chdir(paths.home())
    boost("verify")


def test_refused_inside_a_tap_clone(boost, tapped, monkeypatch):
    clones = [p for p in paths.repos_dir().iterdir() if p.is_dir()]
    assert clones
    d = clones[0]
    before = sorted(p.name for p in d.iterdir())
    monkeypatch.chdir(d)
    r = boost("install", "brainstorming", "--local", expect=1)
    assert "is inside boost's own state directory (~/.boost)" in r.err
    _assert_untouched(d, before)


def test_refused_in_a_bare_repo(boost, tapped, monkeypatch):
    import subprocess
    bare = paths.home() / "bare.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    before = sorted(p.name for p in bare.iterdir())
    monkeypatch.chdir(bare)
    r = boost("install", "brainstorming", "--local", expect=1)
    assert ("cannot install --local here: ~/bare.git is inside a bare git "
            "repository (~/bare.git)") in r.err
    _assert_untouched(bare, before)


def test_an_ordinary_checkout_still_installs(boost, tapped, monkeypatch):
    proj = paths.home() / "code" / "proj"
    (proj / ".git").mkdir(parents=True)
    monkeypatch.chdir(proj)
    boost("install", "brainstorming", "--local")
    assert (proj / ".claude" / "skills" / "brainstorming" / "SKILL.md").is_file()
