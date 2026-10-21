# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: ``store.copy_view_sha`` and ``store.skill_source_sha``.

The lock records the hash of the store *copy*, so the tap side of every
"did this skill move?" comparison must hash what ``_copy_tree`` would put
there, not the raw tree. These live in the unit tier so the mutation gate
(which runs ``tests/unit`` only) sees them.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from boost_cli.core import registry, store, util

pytestmark = pytest.mark.skipif(sys.platform == "win32",
                                reason="symlinks need a privilege on Windows")


def _tap(root):
    skill = root / "skills" / "s"
    (skill / "notes").mkdir(parents=True)
    (skill / "SKILL.md").write_text("x\n", encoding="utf-8")
    (skill / "notes" / "n.txt").write_text("n\n", encoding="utf-8")
    (root / "shared").mkdir()
    (root / "shared" / "h.py").write_text("h\n", encoding="utf-8")
    return skill


def _copied(src, within, dst):
    store._copy_tree(src, dst, within)
    return util.sha256_dir(dst)


class TestCopyViewSha:
    def test_no_link_hashes_in_place(self, sandbox, tmp_path, monkeypatch):
        skill = _tap(tmp_path / "t")
        monkeypatch.setattr(store, "_copy_tree", None)
        assert store.copy_view_sha(skill, tmp_path / "t") == \
            util.sha256_dir(skill)

    def test_a_link_out_of_the_bound_is_left_out(self, sandbox, tmp_path):
        root = tmp_path / "t"
        skill = _tap(root)
        (tmp_path / "secret").write_text("s\n", encoding="utf-8")
        (skill / "out.txt").symlink_to(tmp_path / "secret")
        got = store.copy_view_sha(skill, root)
        assert got != util.sha256_dir(skill)
        assert got == _copied(skill, root, tmp_path / "c")
        (skill / "out.txt").unlink()
        assert got == util.sha256_dir(skill)

    def test_a_link_in_a_subdir_is_seen(self, sandbox, tmp_path):
        root = tmp_path / "t"
        skill = _tap(root)
        (tmp_path / "secret").write_text("s\n", encoding="utf-8")
        (skill / "notes" / "out.txt").symlink_to(tmp_path / "secret")
        assert store.copy_view_sha(skill, root) == \
            _copied(skill, root, tmp_path / "c")

    def test_a_lone_dir_link_is_staged(self, sandbox, tmp_path):
        root = tmp_path / "t"
        skill = _tap(root)
        (skill / "lib").symlink_to("../../shared")
        got = store.copy_view_sha(skill, root)
        assert got != util.sha256_dir(skill)
        assert got == _copied(skill, root, tmp_path / "c")

    def test_the_bound_is_the_one_passed(self, sandbox, tmp_path):
        """With no bound a link out of the tap is copied as its target."""
        root = tmp_path / "t"
        skill = _tap(root)
        (tmp_path / "secret").write_text("s\n", encoding="utf-8")
        (skill / "out.txt").symlink_to(tmp_path / "secret")
        assert store.copy_view_sha(skill, None) == util.sha256_dir(skill)
        assert store.copy_view_sha(skill, None) != \
            store.copy_view_sha(skill, root)

    def test_the_staging_dir_is_removed(self, sandbox, tmp_path, monkeypatch):
        root = tmp_path / "t"
        skill = _tap(root)
        (skill / "lib").symlink_to("../../shared")
        tmp = tmp_path / "tmp"
        tmp.mkdir()
        monkeypatch.setenv("TMPDIR", str(tmp))
        monkeypatch.setattr("tempfile.tempdir", None)
        store.copy_view_sha(skill, root)
        assert list(tmp.iterdir()) == []


class TestSkillSourceSha:
    def test_bounded_by_the_tap_clone(self, sandbox, tmp_path, monkeypatch):
        root = tmp_path / "t"
        skill = _tap(root)
        (tmp_path / "secret").write_text("s\n", encoding="utf-8")
        (skill / "out.txt").symlink_to(tmp_path / "secret")
        seen = []
        monkeypatch.setattr(store, "source_dir_for",
                            lambda e: seen.append(e) or skill)
        monkeypatch.setattr(registry, "get",
                            lambda name: SimpleNamespace(path=root)
                            if name == "tp" else pytest.fail(name))
        entry = {"name": "s", "tap": "tp", "rel_dir": "skills/s"}
        assert store.skill_source_sha(entry) == \
            _copied(skill, root, tmp_path / "c")
        assert seen == [entry]

    def test_private_wrapper_returns_none_on_boost_error(self, sandbox,
                                                         monkeypatch):
        from boost_cli.errors import BoostError

        def boom(_e):
            raise BoostError("gone")
        monkeypatch.setattr(store, "source_dir_for", boom)
        assert store._skill_source_sha({"name": "s", "tap": "tp"}) is None
