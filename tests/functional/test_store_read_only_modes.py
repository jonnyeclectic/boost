# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A skill copied from a read-only source stays removable.

`copytree` copies every directory's mode, so a skill imported from a nix
store path or an extracted tarball (0o555 dirs, 0o444 files) landed in the
store read-only: `boost uninstall` crashed rc 70 with the lock row kept, the
next `sync` reinstalled it, and every reinstall leaked a ``.boost-*.old``
directory that neither `doctor` nor `clean` saw.
"""
from __future__ import annotations

import contextlib
import os
import stat
import sys

import pytest

from boost_cli.core import lockfile, paths, store

pytestmark = [
    pytest.mark.skipif(sys.platform == "win32",
                       reason="POSIX permission semantics"),
    pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0,
                       reason="root ignores the modes under test"),
]


@pytest.fixture
def read_only_skill(tmp_path):
    """``ro/delta``: 0o444 files, a 0o555 ``assets/`` and a 0o555 top dir."""
    top = tmp_path / "ro" / "delta"
    (top / "assets").mkdir(parents=True)
    (top / "SKILL.md").write_text(
        "---\nname: delta\ndescription: read-only source\n---\nbody\n",
        encoding="utf-8")
    (top / "assets" / "a.txt").write_text("a\n", encoding="utf-8")
    for f in (top / "SKILL.md", top / "assets" / "a.txt"):
        f.chmod(0o444)
    for d in (top / "assets", top):
        d.chmod(0o555)
    yield top
    for d in (top, top / "assets"):
        with contextlib.suppress(OSError):
            d.chmod(0o755)


def _mode(p):
    return stat.S_IMODE(os.lstat(p).st_mode)


def test_the_store_copy_s_directories_are_owner_writable(boost,
                                                         read_only_skill):
    boost("import", read_only_skill)
    sdir = store.skill_store_dir("delta")

    assert _mode(sdir) == 0o755
    assert _mode(sdir / "assets") == 0o755
    # Files gain owner write (import --name rewrites SKILL.md in place) and
    # otherwise keep the source's mode, exec bit and all.
    assert _mode(sdir / "SKILL.md") == 0o644
    assert _mode(sdir / "assets" / "a.txt") == 0o644


def test_uninstall_removes_a_copy_installed_read_only(boost, read_only_skill):
    """A copy made before the fix: its dirs are still 0o555 in the store."""
    boost("import", read_only_skill)
    sdir = store.skill_store_dir("delta")
    (sdir / "assets").chmod(0o555)
    sdir.chmod(0o555)

    boost("uninstall", "delta")

    assert not os.path.lexists(sdir)
    assert lockfile.get_skill("delta") is None


def test_reinstall_leaves_no_moved_aside_copy(boost, read_only_skill):
    boost("import", read_only_skill)
    sdir = store.skill_store_dir("delta")
    (sdir / "assets").chmod(0o555)

    boost("reinstall", "delta")
    boost("reinstall", "delta")

    assert sorted(p.name for p in paths.store_dir().iterdir()
                  if p.name.startswith(".boost-")) == []
    assert store.leftover_copies() == []


def test_doctor_names_and_clean_removes_a_leftover_copy(boost, sandbox):
    root = paths.store_dir()
    (root / ".boost-abcd1234.old" / "assets").mkdir(parents=True)
    (root / ".boost-abcd1234.old" / "assets" / "a.txt").write_text(
        "a\n", encoding="utf-8")
    (root / ".boost-abcd1234.old" / "assets").chmod(0o555)
    (root / ".boost-efgh5678.new").mkdir()
    staging = root / ".boost-live0000"     # an install copying right now
    staging.mkdir()
    (root / "notours.old").mkdir()         # a skill's name, not a swap's

    assert [p.name for p in store.leftover_copies()] == [
        ".boost-abcd1234.old", ".boost-efgh5678.new"]
    res = boost("doctor", expect=None)
    assert ("2 leftover skill copies in ~/.agents/skills "
            "(.boost-abcd1234.old, .boost-efgh5678.new)") in " ".join(
                res.out.split())

    res = boost("clean")
    assert "(leftover skill copy)" in res.out
    assert "cleaned 2 item(s)" in res.out
    assert store.leftover_copies() == []
    assert staging.is_dir()
    assert (root / "notours.old").is_dir()

    res = boost("doctor", expect=None)
    assert "leftover skill cop" not in res.out


def test_doctor_says_copy_for_one_leftover(boost, sandbox):
    (paths.store_dir() / ".boost-abcd1234.old").mkdir(parents=True)

    res = boost("doctor", expect=None)

    assert ("1 leftover skill copy in ~/.agents/skills (.boost-abcd1234.old) "
            "— `boost clean` removes it") in " ".join(res.out.split())
