# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`integrity.resolve_skill` / `installed_skills`: one answer across both scopes.

A reader that asked the user lock and then `~/.agents/skills/<name>` called a
skill installed `--local` "not installed" while `boost list` showed it. These
pin the row each helper returns — scope, base, and the directory to read.
"""
from __future__ import annotations

import pytest

from boost_cli.core import integrity, lockfile, paths, projectlock, scopes, util
from boost_cli.errors import BoostError


@pytest.fixture()
def repo(sandbox, tmp_path, monkeypatch):
    d = tmp_path / "isr-repo"
    (d / ".git").mkdir(parents=True)
    monkeypatch.chdir(d)
    return d.resolve()


def _project_skill(repo, name, *, tap="t", body="# x\n"):
    d = repo / ".claude" / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(body, encoding="utf-8")
    entry = {"kind": "skill", "version": "1.0.0", "tap": tap,
             "sha256": util.sha256_dir(d), "scope": scopes.SCOPE_PROJECT,
             "materializations": [
                 {"agent": "claude-code", "path": ".claude/skills/" + name}]}
    projectlock.set_skill(repo, name, entry)
    return d, entry


def _user_skill(name, *, tap="t", store=True):
    if store:
        d = paths.store_dir() / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("# u\n", encoding="utf-8")
    entry = {"version": "2.0.0", "tap": tap}
    lockfile.set_skill(name, entry)
    return entry


class TestResolveSkill:
    def test_project_only_name_resolves_to_the_repo_copy(self, repo):
        d, entry = _project_skill(repo, "p")
        row = integrity.resolve_skill("p")
        assert row == integrity.InstalledSkill(
            "p", entry, scopes.SCOPE_PROJECT, repo, d)
        assert row is not None and row.is_project is True

    def test_user_row_wins_over_project_row(self, repo):
        _project_skill(repo, "both")
        uentry = _user_skill("both")
        row = integrity.resolve_skill("both")
        assert row == integrity.InstalledSkill(
            "both", uentry, scopes.SCOPE_USER, None,
            paths.store_dir() / "both")
        assert row is not None and row.is_project is False

    def test_user_row_without_store_copy_has_no_dir(self, repo):
        _user_skill("gone", store=False)
        row = integrity.resolve_skill("gone")
        assert row is not None
        assert (row.scope, row.dir) == (scopes.SCOPE_USER, None)

    def test_project_row_without_copy_has_no_dir(self, repo):
        d, _entry = _project_skill(repo, "pgone")
        (d / "SKILL.md").unlink()
        d.rmdir()
        row = integrity.resolve_skill("pgone")
        assert row is not None
        assert (row.scope, row.base, row.dir) == (scopes.SCOPE_PROJECT, repo, None)

    def test_qualifier_is_held_against_the_project_tap(self, repo):
        d, _entry = _project_skill(repo, "q", tap="owner/alpha")
        hit = integrity.resolve_skill("alpha:q")
        assert hit is not None and hit.dir == d and hit.name == "q"
        assert integrity.resolve_skill("beta:q") is None

    def test_qualifier_mismatch_on_user_falls_to_project(self, repo):
        _user_skill("m", tap="owner/one")
        d, _ = _project_skill(repo, "m", tap="owner/two")
        row = integrity.resolve_skill("two:m")
        assert row is not None and row.scope == scopes.SCOPE_PROJECT
        assert row.dir == d

    def test_a_rule_does_not_answer(self, repo):
        lockfile.set_rule("r", {"tap": "t", "materializations": []})
        assert integrity.resolve_skill("r") is None

    def test_unsafe_user_name_has_no_dir(self, repo):
        lockfile.set_skill("..", {"tap": "t"})
        row = integrity.resolve_skill("..")
        assert row is not None and row.dir is None

    def test_outside_a_project_only_the_user_lock_answers(self, sandbox,
                                                          monkeypatch):
        monkeypatch.chdir(sandbox)
        assert integrity.resolve_skill("nothing") is None


class TestInstalledSkills:
    def test_both_scopes_each_with_its_dir(self, repo):
        _user_skill("a")
        pd, _ = _project_skill(repo, "a")
        qd, _ = _project_skill(repo, "b")
        rows = integrity.installed_skills()
        assert [(r.name, r.scope, r.base, r.dir) for r in rows] == [
            ("a", scopes.SCOPE_USER, None, paths.store_dir() / "a"),
            ("a", scopes.SCOPE_PROJECT, repo, pd),
            ("b", scopes.SCOPE_PROJECT, repo, qd)]


class TestRefuseProjectScope:
    def test_project_row_names_its_scope(self, repo):
        _project_skill(repo, "p")
        with pytest.raises(BoostError) as ei:
            integrity.refuse_project_only("p", "boost tag")
        assert str(ei.value) == (
            "p is installed at project scope (%s) — boost tag applies to "
            "user-scope skills" % paths.tilde(repo))
        assert ei.value.hint == "see it with `boost list --local`"

    def test_user_row_and_miss_return(self, repo):
        _user_skill("u")
        _project_skill(repo, "u")
        assert integrity.refuse_project_only("u", "boost tag") is None
        assert integrity.refuse_project_only("absent", "boost tag") is None


class TestEnforceRow:
    def test_modified_project_copy_refused_only_when_enforcing(self, repo):
        d, _ = _project_skill(repo, "e")
        (d / "SKILL.md").write_text("# edited\n", encoding="utf-8")
        row = integrity.resolve_skill("e")
        assert row is not None
        integrity.enforce_row(row)   # enforcement off: served as-is
        from boost_cli.core import config
        config.set_value(integrity.ENFORCE_KEY, "true")
        with pytest.raises(BoostError) as ei:
            integrity.enforce_row(row)
        assert str(ei.value) == (
            "e has been modified since install — its content no longer "
            "matches the project lock file")

    def test_intact_project_copy_served_when_enforcing(self, repo):
        _project_skill(repo, "ok")
        from boost_cli.core import config
        config.set_value(integrity.ENFORCE_KEY, "true")
        row = integrity.resolve_skill("ok")
        assert row is not None
        assert integrity.enforce_row(row) is None

    def test_user_row_goes_through_enforce(self, repo):
        _user_skill("uu")
        d = paths.store_dir() / "uu"
        lockfile.set_skill("uu", {"tap": "t", "sha256": "0" * 64})
        from boost_cli.core import config
        config.set_value(integrity.ENFORCE_KEY, "true")
        row = integrity.resolve_skill("uu")
        assert row is not None and row.dir == d
        with pytest.raises(BoostError, match="no longer matches the lock file"):
            integrity.enforce_row(row)


class TestReadSkillMetaAtDir:
    def test_skill_dir_is_read_instead_of_the_store(self, repo):
        d, _ = _project_skill(
            repo, "rm", body="---\nname: rm\ndescription: here\n---\nbody\n")
        from boost_cli.core import store
        meta, body = store.read_skill_meta("rm", d)
        assert (meta["name"], meta["description"], body.strip()) == (
            "rm", "here", "body")
        assert store.read_skill_meta("rm") is None   # nothing in the store
