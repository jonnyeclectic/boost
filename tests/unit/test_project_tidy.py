# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The last project skill out takes the empty lock and the dirs installs made.

``boost uninstall --local`` of the last skill used to leave
``.boost/skill-lock.json`` holding ``{"skills": {}}`` and five empty agent
skills directories. Installs now note the directories they create
(``store.DIRS_CREATED_KEY``), and the last uninstall removes those that are
empty, then the lock. Nothing that held anything before, or holds anything
now, is touched.
"""
from __future__ import annotations

import json
import os

import pytest

from boost_cli.core import projectlock, store


@pytest.fixture()
def base(sandbox, tmp_path):
    d = tmp_path / "repo"
    (d / ".git").mkdir(parents=True)
    return d


class TestMissingParents:
    def test_names_every_missing_dir_below_base(self, base):
        dests = [base / ".claude" / "skills" / "x",
                 base / ".cursor" / "skills" / "x"]
        assert store.missing_parents(base, dests) == [
            ".claude", ".claude/skills", ".cursor", ".cursor/skills"]

    def test_an_existing_dir_is_not_boosts(self, base):
        (base / ".claude").mkdir()
        assert store.missing_parents(
            base, [base / ".claude" / "skills" / "x"]) == [".claude/skills"]

    def test_never_base_or_above_and_never_the_dest(self, base, tmp_path):
        assert store.missing_parents(base, [base / "x"]) == []
        assert store.missing_parents(base, [tmp_path / "elsewhere" / "x"]) == []

    def test_a_dangling_symlink_is_not_missing(self, base):
        # Something is there, so it is not a directory boost made.
        (base / ".claude").symlink_to(base / "nowhere")
        assert store.missing_parents(
            base, [base / ".claude" / "skills" / "x"]) == [".claude/skills"]


def _lock(base, **top):
    path = projectlock.lock_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "updated": "t", "skills": {}}
                               | top), encoding="utf-8")
    return path


class TestRemoveIfEmpty:
    def test_an_empty_lock_and_its_dir_go(self, base):
        path = _lock(base)
        assert projectlock.remove_if_empty(base) is True
        assert not path.exists()
        assert not path.parent.exists()

    def test_a_lock_holding_a_skill_stays(self, base):
        path = _lock(base, skills={"x": {}})
        assert projectlock.remove_if_empty(base) is False
        assert path.is_file()

    def test_an_unknown_key_keeps_it_unless_owned(self, base):
        path = _lock(base, mine=1)
        assert projectlock.remove_if_empty(base) is False
        assert path.is_file()
        assert projectlock.remove_if_empty(base, owned=("mine",)) is True
        assert not path.exists()

    def test_a_corrupt_lock_is_not_read_as_empty(self, base):
        path = projectlock.lock_path(base)
        path.parent.mkdir(parents=True)
        path.write_text("{not json", encoding="utf-8")
        assert projectlock.remove_if_empty(base) is False
        assert path.read_text(encoding="utf-8") == "{not json"

    def test_a_skills_value_that_is_not_an_empty_object_stays(self, base):
        path = _lock(base, skills=[])
        assert projectlock.remove_if_empty(base) is False
        assert path.is_file()

    def test_no_lock_is_nothing_to_do(self, base):
        assert projectlock.remove_if_empty(base) is False
        assert not (base / projectlock.LOCK_DIRNAME).exists()

    def test_other_files_keep_the_dir(self, base):
        path = _lock(base)
        (path.parent / "notes").write_text("x", encoding="utf-8")
        assert projectlock.remove_if_empty(base) is True
        assert not path.exists()
        assert (path.parent / "notes").is_file()


def _legal(base, name="x"):
    return {base / ".claude" / "skills" / name, base / ".cursor" / "skills" / name}


class TestRemoveCreatedDirs:
    def test_removes_empty_recorded_dirs_deepest_first(self, base):
        (base / ".claude" / "skills").mkdir(parents=True)
        assert store.remove_created_dirs(
            base, [".claude", ".claude/skills"], _legal(base)) == [
                ".claude/skills", ".claude"]
        assert not (base / ".claude").exists()

    def test_a_dir_holding_anything_stays(self, base):
        (base / ".cursor" / "skills").mkdir(parents=True)
        (base / ".cursor" / "skills" / "notes.txt").write_text("x",
                                                               encoding="utf-8")
        assert store.remove_created_dirs(
            base, [".cursor", ".cursor/skills"], _legal(base)) == []
        assert (base / ".cursor" / "skills" / "notes.txt").is_file()

    def test_a_dir_no_install_writes_through_is_refused(self, base):
        # The record is committed input: an empty `src/` stays put.
        (base / "src").mkdir()
        assert store.remove_created_dirs(base, ["src", "../out", ""],
                                         _legal(base)) == []
        assert (base / "src").is_dir()

    def test_a_symlinked_dir_is_not_removed(self, base):
        (base / "real").mkdir()
        (base / ".claude").symlink_to(base / "real")
        assert store.remove_created_dirs(base, [".claude"], _legal(base)) == []
        assert os.path.islink(base / ".claude")

    def test_a_redirected_ancestor_is_not_walked(self, base):
        (base / "elsewhere" / "skills").mkdir(parents=True)
        (base / ".claude").symlink_to(base / "elsewhere")
        assert store.remove_created_dirs(
            base, [".claude/skills"], _legal(base)) == []
        assert (base / "elsewhere" / "skills").is_dir()

    @pytest.mark.parametrize("recorded", [None, "x", {"a": 1}])
    def test_a_record_that_is_not_a_list_removes_nothing(self, base, recorded):
        (base / ".claude").mkdir()
        assert store.remove_created_dirs(base, recorded, _legal(base)) == []
        assert (base / ".claude").is_dir()

    def test_non_string_rows_are_skipped(self, base):
        (base / ".claude").mkdir()
        assert store.remove_created_dirs(
            base, [3, None, ".claude"], _legal(base)) == [".claude"]


class TestTidyEmptyProject:
    def test_a_project_still_holding_a_skill_is_left_alone(self, base):
        (base / ".claude").mkdir()
        path = _lock(base, skills={"y": {}},
                     **{store.DIRS_CREATED_KEY: [".claude"]})
        assert store.tidy_empty_project(base, _legal(base)) == {
            "dirs_removed": [], "lock_removed": False}
        assert path.is_file() and (base / ".claude").is_dir()

    def test_the_last_one_out_removes_dirs_and_lock(self, base):
        (base / ".claude" / "skills").mkdir(parents=True)
        path = _lock(base, **{store.DIRS_CREATED_KEY: [".claude/skills"],
                              store.SIDECAR_CREATED_KEY: True})
        assert store.tidy_empty_project(base, _legal(base)) == {
            "dirs_removed": [".claude/skills"], "lock_removed": True}
        assert not path.exists()
        assert (base / ".claude").is_dir(), "not recorded, so not boost's"
