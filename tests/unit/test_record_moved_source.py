# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""store.record_moved_source: an unchanged item's new upstream location.

An upstream `git mv` with no edit left the lock naming a path the tap no
longer has, so `boost update` warned on every run and `boost drift` called
the skill source-missing. These pin exactly which fields are written.
"""
from __future__ import annotations

from boost_cli.core import lockfile, projectlock, store


def _skill_row(**extra):
    return {"version": "1.0.0", "tap": "t", "source_dir": "skills/old",
            "commit": "c1", "sha256": "s"} | extra


class TestUserLock:
    def test_a_skill_row_takes_the_new_dir_and_commit(self, sandbox):
        lockfile.set_skill("x", _skill_row())
        assert store.record_moved_source(
            "skill", "x", {"rel_dir": "skills/new"}, "c2") is True
        assert lockfile.get_skill("x") == _skill_row(
            source_dir="skills/new", commit="c2")

    def test_a_rule_row_takes_the_new_file(self, sandbox):
        lockfile.set_rule("r", {"tap": "t", "source_file": "rules/a/r.mdc",
                                "commit": "c1"})
        assert store.record_moved_source(
            "rule", "r", {"skill_md": "rules/b/r.mdc", "rel_dir": "rules/b"},
            "c2") is True
        assert lockfile.get_rule("r") == {
            "tap": "t", "source_file": "rules/b/r.mdc", "commit": "c2"}

    def test_a_workflow_row_takes_the_new_file(self, sandbox):
        lockfile.set_workflow("w", {"tap": "t", "source_file": "commands/w.md",
                                    "commit": "c1"})
        assert store.record_moved_source(
            "workflow", "w", {"skill_md": "agents/w.md"}, "c1") is True
        assert lockfile.get_workflow("w") == {
            "tap": "t", "source_file": "agents/w.md", "commit": "c1"}

    def test_no_commit_leaves_the_recorded_one(self, sandbox):
        lockfile.set_skill("x", _skill_row())
        assert store.record_moved_source(
            "skill", "x", {"rel_dir": "skills/new"}, "") is True
        assert lockfile.get_skill("x")["commit"] == "c1"

    def test_a_row_already_there_is_not_rewritten(self, sandbox):
        lockfile.set_skill("x", _skill_row())
        assert store.record_moved_source(
            "skill", "x", {"rel_dir": "skills/old"}, "c1") is False
        assert store.record_moved_source(
            "skill", "x", {"rel_dir": "skills/old"}, "") is False

    def test_a_new_commit_alone_is_recorded(self, sandbox):
        lockfile.set_skill("x", _skill_row())
        assert store.record_moved_source(
            "skill", "x", {"rel_dir": "skills/old"}, "c2") is True
        assert lockfile.get_skill("x")["commit"] == "c2"

    def test_a_missing_rel_dir_is_the_tap_root(self, sandbox):
        lockfile.set_skill("x", _skill_row())
        store.record_moved_source("skill", "x", {}, "c1")
        assert lockfile.get_skill("x")["source_dir"] == "."

    def test_a_row_that_is_gone_is_not_recreated(self, sandbox):
        assert store.record_moved_source(
            "skill", "ghost", {"rel_dir": "skills/new"}, "c2") is False
        assert lockfile.get_skill("ghost") is None


class TestProjectLock:
    def test_the_project_row_is_written_and_the_user_lock_is_not(
            self, sandbox, tmp_path):
        base = tmp_path / "proj"
        base.mkdir()
        projectlock.set_skill(base, "x", _skill_row())
        lockfile.set_skill("x", _skill_row(source_dir="skills/user"))
        assert store.record_moved_source(
            "skill", "x", {"rel_dir": "skills/new"}, "c2", base=base) is True
        assert projectlock.get_skill(base, "x") == _skill_row(
            source_dir="skills/new", commit="c2")
        assert lockfile.get_skill("x")["source_dir"] == "skills/user"

    def test_a_project_without_the_row_writes_nothing(self, sandbox, tmp_path):
        base = tmp_path / "proj"
        base.mkdir()
        projectlock.set_skill(base, "y", _skill_row())
        assert store.record_moved_source(
            "skill", "x", {"rel_dir": "skills/new"}, "c2", base=base) is False
        assert projectlock.installed(base) == {"y": _skill_row()}
