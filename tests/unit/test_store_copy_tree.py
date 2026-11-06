# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: ``store._copy_tree`` and the links a skill copy may follow.

``tests/functional/test_install_symlinks.py`` drives the same behaviour end to
end, but the mutation gate runs only ``tests/unit``, so without these every
mutant of ``_copy_tree`` survived and ran its whole covering suite. Each test
here pins one clause of the link test by exact result: the returned lines, and
what is (and is not) in the copy.
"""
from __future__ import annotations

import os
import stat
import sys

import pytest

from boost_cli.core import store

symlinks = pytest.mark.skipif(sys.platform == "win32",
                              reason="symlinks need a privilege on Windows")


def _write(p, text="x\n"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _read(p):
    return p.read_text(encoding="utf-8")


# -- no links ---------------------------------------------------------------

def test_plain_tree_is_copied_and_returns_an_empty_list(tmp_path):
    src = tmp_path / "skill"
    _write(src / "SKILL.md", "body\n")
    _write(src / "a" / "b" / "deep.txt", "deep\n")
    run = _write(src / "run.sh", "#!/bin/sh\n")
    run.chmod(0o750)
    _write(src / ".git" / "HEAD", "ref\n")
    _write(src / "a" / "__pycache__" / "m.pyc", "c\n")
    _write(src / "a" / ".DS_Store", "d\n")
    dst = tmp_path / "out"
    assert store._copy_tree(src, dst, None) == []
    assert _read(dst / "SKILL.md") == "body\n"
    assert _read(dst / "a" / "b" / "deep.txt") == "deep\n"
    if sys.platform != "win32":
        assert stat.S_IMODE((dst / "run.sh").stat().st_mode) == 0o750
    assert not (dst / ".git").exists()
    assert not (dst / "a" / "__pycache__").exists()
    assert not (dst / "a" / ".DS_Store").exists()


def test_an_existing_destination_is_merged_into(tmp_path):
    src = tmp_path / "skill"
    _write(src / "SKILL.md", "new\n")
    dst = tmp_path / "out"
    _write(dst / "SKILL.md", "old\n")
    _write(dst / "keep.txt", "kept\n")
    assert store._copy_tree(src, dst, tmp_path) == []
    assert _read(dst / "SKILL.md") == "new\n"
    assert _read(dst / "keep.txt") == "kept\n"


# -- links ------------------------------------------------------------------

@pytest.fixture
def tap(tmp_path):
    """A tap holding ``skills/s`` and a ``shared`` tree outside the skill."""
    root = tmp_path / "tap"
    src = root / "skills" / "s"
    _write(src / "SKILL.md")
    _write(src / "notes" / "real.txt", "inside\n")
    # Padding: a ``continue`` mutated to ``break`` stops scanning a directory
    # at its first plain file, so give each linked dir plain files to meet.
    for i in range(8):
        _write(src / ("pad%d.md" % i))
    _write(root / "shared" / "helper.py", "print('hi')\n")
    _write(tmp_path / "secret.txt", "not the tap's\n")
    return root, src


@symlinks
def test_a_link_inside_the_skill_stays_a_link(tap, tmp_path):
    root, src = tap
    (src / "alias.txt").symlink_to(os.path.join("notes", "real.txt"))
    (src / "notes" / "up.txt").symlink_to(os.path.join(os.pardir, "SKILL.md"))
    dst = tmp_path / "out"
    assert store._copy_tree(src, dst, root) == []
    assert os.readlink(dst / "alias.txt") == os.path.join("notes", "real.txt")
    assert os.readlink(dst / "notes" / "up.txt") == os.path.join(
        os.pardir, "SKILL.md")
    assert _read(dst / "alias.txt") == "inside\n"


@symlinks
def test_a_link_spelled_through_the_skill_name_is_copied_as_a_file(tap,
                                                                   tmp_path):
    root, src = tap
    (src / "self.txt").symlink_to(
        os.path.join(os.pardir, "s", "notes", "real.txt"))
    dst = tmp_path / "out"
    assert store._copy_tree(src, dst, root) == []
    assert not (dst / "self.txt").is_symlink()
    assert _read(dst / "self.txt") == "inside\n"


@symlinks
def test_an_absolute_link_into_the_skill_is_copied_as_a_file(tap, tmp_path):
    root, src = tap
    (src / "abs.txt").symlink_to(src / "notes" / "real.txt")
    dst = tmp_path / "out"
    assert store._copy_tree(src, dst, root) == []
    assert not (dst / "abs.txt").is_symlink()
    assert _read(dst / "abs.txt") == "inside\n"


@symlinks
def test_a_link_to_a_tap_file_is_copied_as_that_file_with_its_mode(tap,
                                                                   tmp_path):
    root, src = tap
    (root / "shared" / "helper.py").chmod(0o751)
    (src / "helper.py").symlink_to(
        os.path.join(os.pardir, os.pardir, "shared", "helper.py"))
    dst = tmp_path / "out"
    assert store._copy_tree(src, dst, root) == []
    assert not (dst / "helper.py").is_symlink()
    assert _read(dst / "helper.py") == "print('hi')\n"
    assert stat.S_IMODE((dst / "helper.py").stat().st_mode) == 0o751


@symlinks
def test_a_dangling_link_is_skipped_and_named(tap, tmp_path):
    root, src = tap
    (src / "gone.txt").symlink_to("nowhere.txt")
    dst = tmp_path / "out"
    assert store._copy_tree(src, dst, root) == [
        "gone.txt → nowhere.txt leads to nothing"]
    assert not os.path.lexists(dst / "gone.txt")
    assert _read(dst / "notes" / "real.txt") == "inside\n"


@symlinks
def test_a_link_out_of_the_tap_is_skipped_and_named(tap, tmp_path):
    root, src = tap
    secret = tmp_path / "secret.txt"
    (src / "nested").mkdir()
    (src / "nested" / "out.txt").symlink_to(secret)
    dst = tmp_path / "out"
    assert store._copy_tree(src, dst, root) == [
        "nested/out.txt → %s leads outside the tap" % os.readlink(
            src / "nested" / "out.txt")]
    assert not os.path.lexists(dst / "nested" / "out.txt")


@symlinks
def test_without_a_bound_a_link_anywhere_is_copied(tap, tmp_path):
    _root, src = tap
    (src / "out.txt").symlink_to(tmp_path / "secret.txt")
    dst = tmp_path / "out"
    assert store._copy_tree(src, dst, None) == []
    assert not (dst / "out.txt").is_symlink()
    assert _read(dst / "out.txt") == "not the tap's\n"


@symlinks
def test_an_ignored_name_is_left_out_even_as_a_link(tap, tmp_path):
    root, src = tap
    (src / ".DS_Store").symlink_to("nowhere")
    (src / "__pycache__").symlink_to(tmp_path / "secret.txt")
    dst = tmp_path / "out"
    assert store._copy_tree(src, dst, root) == []
    assert not os.path.lexists(dst / ".DS_Store")
    assert not os.path.lexists(dst / "__pycache__")


@symlinks
def test_a_link_to_an_ancestor_loops_back_and_is_skipped(tap, tmp_path):
    root, src = tap
    (src / "up").symlink_to(os.pardir)
    dst = tmp_path / "out"
    assert store._copy_tree(src, dst, root) == [
        "up → .. loops back over the skill"]
    assert not os.path.lexists(dst / "up")


@symlinks
def test_a_link_to_a_tap_dir_is_copied_with_its_own_links_judged(tap,
                                                                  tmp_path):
    root, src = tap
    lib = root / "shared" / "lib"
    _write(lib / "util.py", "X = 1\n")
    (lib / "inner.py").symlink_to("util.py")
    (lib / "bad").symlink_to("nowhere")
    (lib / "esc.txt").symlink_to(tmp_path / "secret.txt")
    (lib / "tapfile.py").symlink_to(os.path.join(os.pardir, "helper.py"))
    # The top-level link is judged before ``sub`` is entered, so its line
    # always comes first however each directory happens to list.
    (src / "gone.txt").symlink_to("nowhere.txt")
    (src / "sub").mkdir()
    (src / "sub" / "lib").symlink_to(
        os.path.join(os.pardir, os.pardir, os.pardir, "shared", "lib"))
    dst = tmp_path / "out"
    got = store._copy_tree(src, dst, root)
    assert got[0] == "gone.txt → nowhere.txt leads to nothing"
    assert sorted(got[1:]) == [
        "sub/lib/bad → nowhere leads to nothing",
        "sub/lib/esc.txt → %s leads outside the tap"
        % os.readlink(lib / "esc.txt"),
    ]
    out = dst / "sub" / "lib"
    assert not out.is_symlink()
    assert _read(out / "util.py") == "X = 1\n"
    assert os.readlink(out / "inner.py") == "util.py"
    assert not (out / "tapfile.py").is_symlink()
    assert _read(out / "tapfile.py") == "print('hi')\n"
    assert not os.path.lexists(out / "bad")
    assert not os.path.lexists(out / "esc.txt")
