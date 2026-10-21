# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""One answer to "which directory is this project", and where it may not be.

``onboard``, ``decay`` and ``health`` used the raw cwd, so run from
``src/`` they wrote a dead GitHub workflow there and judged every skill
irrelevant. ``install --local`` took boost's own managed dirs — an installed
skill's store dir, a tap clone, a bare repo — as an unmarked project and wrote
into them. And ``onboard`` committed every repo's ``--local`` rows into this
one, absolute ``base`` and all.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from boost_cli.commands import quality
from boost_cli.core import lockfile, paths, scopes
from boost_cli.errors import BoostError

# ── project_dir ──────────────────────────────────────────────────────────


def test_project_dir_walks_up_to_the_git_root(sandbox, tmp_path):
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    deep = root / "packages" / "api" / "src"
    deep.mkdir(parents=True)
    assert scopes.project_dir(deep) == root.resolve()


def test_project_dir_honors_a_worktree_git_file(sandbox, tmp_path):
    root = tmp_path / "wt"
    (root / "src").mkdir(parents=True)
    (root / ".git").write_text("gitdir: /elsewhere/.git/worktrees/wt\n",
                               encoding="utf-8")
    assert scopes.project_dir(root / "src") == root.resolve()


def test_project_dir_unmarked_is_the_start_itself(sandbox, tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert scopes.project_dir(plain) == plain


def test_project_dir_in_home_falls_back_to_home(sandbox):
    # project_base refuses $HOME as a project; a repo-wide reader still needs
    # *a* directory, and the start is the honest one.
    home = paths.home()
    assert scopes.project_base(home) == (None, None)
    assert scopes.project_dir(home) == Path(home)


def test_project_dir_defaults_to_cwd(sandbox, tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    (root / "src").mkdir()
    monkeypatch.chdir(root / "src")
    assert scopes.project_dir() == root.resolve()


def test_project_dir_cwd_outside_any_project(sandbox, monkeypatch):
    monkeypatch.chdir(paths.home())
    assert scopes.project_dir() == Path.cwd()


# ── managed_by_boost / refuse_managed ────────────────────────────────────


def test_the_store_dir_and_a_skill_inside_it_are_refused(sandbox):
    skill = paths.store_dir() / "commit-messages"
    skill.mkdir(parents=True)
    assert scopes.managed_by_boost(skill) == (
        "~/.agents/skills/commit-messages is inside boost's skill store "
        "(~/.agents/skills)")
    assert scopes.managed_by_boost(paths.store_dir()) == (
        "~/.agents/skills is inside boost's skill store (~/.agents/skills)")


def test_a_tap_clone_is_refused(sandbox):
    clone = paths.repos_dir() / "rwtap"
    clone.mkdir(parents=True)
    assert scopes.managed_by_boost(clone) == (
        "~/.boost/repos/rwtap is inside boost's own state directory (~/.boost)")


def test_an_agent_user_skills_dir_is_refused(sandbox):
    adir = paths.home() / ".claude" / "skills" / "x"
    adir.mkdir(parents=True)
    assert scopes.managed_by_boost(adir) == (
        "~/.claude/skills/x is inside an agent's user skills directory "
        "(~/.claude/skills)")


def test_a_bare_repo_and_a_dir_inside_it_are_refused(sandbox):
    bare = paths.home() / "bare.git"
    (bare / "objects").mkdir(parents=True)
    (bare / "refs" / "heads").mkdir(parents=True)
    (bare / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    want = "is inside a bare git repository (~/bare.git)"
    assert scopes.managed_by_boost(bare) == "~/bare.git " + want
    assert scopes.managed_by_boost(bare / "refs" / "heads") == (
        "~/bare.git/refs/heads " + want)


@pytest.mark.parametrize("missing", ["HEAD", "objects", "refs"])
def test_bare_detection_needs_all_three(sandbox, missing):
    d = paths.home() / "almost"
    d.mkdir()
    if missing != "HEAD":
        (d / "HEAD").write_text("x\n", encoding="utf-8")
    for sub in ("objects", "refs"):
        if sub != missing:
            (d / sub).mkdir()
    assert scopes.managed_by_boost(d) is None


def test_bare_detection_stops_at_home(sandbox):
    # A HEAD/objects/refs triple *at* $HOME is not a bare repo the project
    # sits in — the walk stops there, as project_root's does.
    home = paths.home()
    (home / "HEAD").write_text("x\n", encoding="utf-8")
    (home / "objects").mkdir()
    (home / "refs").mkdir()
    proj = home / "code" / "proj"
    proj.mkdir(parents=True)
    assert scopes.managed_by_boost(proj) is None


def test_an_ordinary_project_is_allowed(sandbox):
    proj = paths.home() / "code" / "proj"
    (proj / ".git").mkdir(parents=True)
    assert scopes.managed_by_boost(proj) is None
    scopes.refuse_managed(proj)          # does not raise


def test_a_sibling_named_like_the_store_is_allowed(sandbox):
    # Prefix, not ancestry: ~/.agents/skills-old is not inside ~/.agents/skills.
    sib = paths.home() / ".agents" / "skills-old"
    sib.mkdir(parents=True)
    assert scopes.managed_by_boost(sib) is None


def test_refuse_managed_raises_with_the_reason_and_a_hint(sandbox):
    skill = paths.store_dir() / "s"
    skill.mkdir(parents=True)
    with pytest.raises(BoostError) as ei:
        scopes.refuse_managed(skill)
    assert ei.value.message == (
        "cannot install --local here: ~/.agents/skills/s is inside boost's "
        "skill store (~/.agents/skills)")
    assert ei.value.hint == ("cd into a project checkout, or drop --local to "
                             "install for your user")


# ── lockfile.portable(base=) ─────────────────────────────────────────────


def _lock(home, this, other):
    return {"version": 3, "skills": {"s": {"version": "1"}}, "rules": {
        "mine": {"kind": "rule", "scope": "project", "base": str(this),
                 "materializations": [
                     {"agent": "cursor",
                      "path": str(this / ".cursor" / "rules" / "mine.mdc")}]},
        "global": {"kind": "rule", "materializations": [
            {"agent": "claude-code", "path": str(home / ".claude" / "CLAUDE.md")}]},
    }, "workflows": {
        "theirs": {"kind": "workflow", "scope": "project", "base": str(other),
                   "materializations": [
                       {"agent": "claude-code", "path": str(
                           other / ".claude" / "commands" / "theirs.md")}]},
    }}


def test_portable_for_a_repo_keeps_only_its_own_project_rows(sandbox):
    home = paths.home()
    this, other = home / "code" / "oss", home / "code" / "secret-client"
    this.mkdir(parents=True)
    other.mkdir(parents=True)
    out = lockfile.portable(_lock(home, this, other), base=this)
    assert out["workflows"] == {}
    assert out["rules"]["mine"]["base"] == "."
    assert out["rules"]["mine"]["materializations"][0]["path"] == \
        ".cursor/rules/mine.mdc"
    assert out["rules"]["global"]["materializations"][0]["path"] == \
        "~/.claude/CLAUDE.md"
    assert out["skills"] == {"s": {"version": "1"}}
    raw = json.dumps(out)
    assert "secret-client" not in raw and str(home) not in raw


def test_portable_without_a_repo_contracts_base_too(sandbox):
    home = paths.home()
    this, other = home / "code" / "oss", home / "code" / "secret-client"
    out = lockfile.portable(_lock(home, this, other))
    assert out["rules"]["mine"]["base"] == "~/code/oss"
    assert out["workflows"]["theirs"]["base"] == "~/code/secret-client"
    assert out["rules"]["mine"]["materializations"][0]["path"] == \
        "~/code/oss/.cursor/rules/mine.mdc"


def test_portable_project_path_outside_the_repo_is_tilded(sandbox):
    home = paths.home()
    this = home / "code" / "oss"
    this.mkdir(parents=True)
    lock = {"version": 3, "skills": {}, "workflows": {}, "rules": {
        "r": {"kind": "rule", "scope": "project", "base": str(this),
              "materializations": [
                  {"agent": "cursor", "path": str(home / "code" / "oss-x" / "r.mdc")},
                  {"agent": "gemini", "path": "relative/r.md"}]}}}
    mats = lockfile.portable(lock, base=this)["rules"]["r"]["materializations"]
    assert [m["path"] for m in mats] == ["~/code/oss-x/r.mdc", "relative/r.md"]


def test_portable_contracts_a_scopeless_rows_base(sandbox):
    # `update` can write a row back with `base` and no `scope`: it is not this
    # repo's project row, so it stays — but its $HOME path must not.
    home = paths.home()
    this = home / "code" / "oss"
    this.mkdir(parents=True)
    lock = {"version": 3, "skills": {}, "workflows": {}, "rules": {
        "r": {"kind": "rule", "base": str(home / "code" / "other")}}}
    out = lockfile.portable(lock, base=this)
    assert out["rules"]["r"]["base"] == "~/code/other"


def test_portable_drops_a_project_row_with_no_usable_base(sandbox):
    this = paths.home() / "code" / "oss"
    this.mkdir(parents=True)
    lock = {"version": 3, "skills": {}, "workflows": {}, "rules": {
        "r": {"kind": "rule", "scope": "project", "base": "."}}}
    assert lockfile.portable(lock, base=this)["rules"] == {}


# ── decay / health probe the project root ────────────────────────────────


@pytest.mark.parametrize("cmd", ["cmd_decay", "cmd_health"])
def test_decay_and_health_probe_the_root_from_a_subdir(sandbox, tmp_path,
                                                       monkeypatch, cmd):
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    (root / "packages" / "api").mkdir(parents=True)
    monkeypatch.chdir(root / "packages" / "api")
    seen = []
    monkeypatch.setattr(quality, "_decay_rows",
                        lambda cwd: seen.append(cwd) or [])
    getattr(quality, cmd)(["--json"])
    assert seen == [root.resolve()]
