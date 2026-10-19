# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Core helpers that let commands see project-scoped skills.

`integrity.installed_skill_rows` is the one walk over both locks,
`integrity.project_skill_dir` the one lookup of a project skill's copy, and
`integrity.locally_edited(..., base=)` the edit check for a project row.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from boost_cli.core import integrity, lockfile, projectlock, scopes, util


@pytest.fixture()
def repo(sandbox, tmp_path, monkeypatch):
    d = tmp_path / "psv-unit-repo"
    (d / ".git").mkdir(parents=True)
    monkeypatch.chdir(d)
    return d.resolve()


def _project_skill(repo, name, *, version="1.0.0", body="# x\n"):
    d = repo / ".claude" / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(body, encoding="utf-8")
    entry = {"kind": "skill", "version": version, "tap": "t",
             "sha256": util.sha256_dir(d), "scope": scopes.SCOPE_PROJECT,
             "materializations": [
                 {"agent": "claude-code", "path": ".claude/skills/" + name}]}
    projectlock.set_skill(repo, name, entry)
    return d, entry


class TestInstalledSkillRows:
    def test_union_sorted_user_first(self, repo):
        lockfile.set_skill("b", {"version": "1"})
        lockfile.set_skill("a", {"version": "2"})
        _project_skill(repo, "a")
        _project_skill(repo, "c")
        rows = integrity.installed_skill_rows()
        assert [(n, s, b) for n, _e, s, b in rows] == [
            ("a", scopes.SCOPE_USER, None),
            ("a", scopes.SCOPE_PROJECT, repo),
            ("b", scopes.SCOPE_USER, None),
            ("c", scopes.SCOPE_PROJECT, repo)]
        assert rows[0][1] == {"version": "2"}
        assert rows[1][1]["version"] == "1.0.0"

    def test_no_project_means_user_rows_only(self, sandbox, monkeypatch):
        # $HOME is never a project, so resolve_base answers None there.
        monkeypatch.chdir(sandbox)
        lockfile.set_skill("solo", {"version": "1"})
        assert integrity.installed_skill_rows() == [
            ("solo", {"version": "1"}, scopes.SCOPE_USER, None)]


class TestProjectSkillDir:
    def test_first_present_materialization(self, repo):
        d, entry = _project_skill(repo, "here")
        entry["materializations"].insert(
            0, {"agent": "cursor", "path": ".cursor/skills/here"})
        assert integrity.project_skill_dir(entry, repo) == d

    def test_none_when_absent_or_escaping(self, repo, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir()
        entry = {"materializations": [
            {"agent": "x", "path": ".claude/skills/gone"},
            {"agent": "y", "path": "../outside"}]}
        assert integrity.project_skill_dir(entry, repo) is None
        assert integrity.project_skill_dir({}, repo) is None


class TestLocallyEditedProject:
    def test_base_judges_the_repo_copy(self, repo):
        d, entry = _project_skill(repo, "ed")
        assert integrity.locally_edited("skill", "ed", entry, base=repo) is False
        (d / "SKILL.md").write_text("# changed\n", encoding="utf-8")
        assert integrity.locally_edited("skill", "ed", entry, base=repo) is True

    def test_without_base_the_user_store_is_asked(self, repo):
        d, entry = _project_skill(repo, "ed2")
        (d / "SKILL.md").write_text("# changed\n", encoding="utf-8")
        # No store dir for it: the user-scope question cannot see the edit.
        assert integrity.locally_edited("skill", "ed2", entry) is False
        assert Path(d).is_dir()
