# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`store._own_dirs`: a store copy's directories are always owner-rwx."""
from __future__ import annotations

import contextlib
import os
import stat
import sys

import pytest

from boost_cli.core import store

pytestmark = [
    pytest.mark.skipif(sys.platform == "win32",
                       reason="POSIX permission semantics"),
    pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0,
                       reason="root ignores the modes under test"),
]


def _mode(p):
    return stat.S_IMODE(os.lstat(p).st_mode)


@pytest.fixture
def unseal(tmp_path):
    yield
    for here, dirs, _names in os.walk(tmp_path):
        for d in dirs:
            with contextlib.suppress(OSError):
                os.chmod(os.path.join(here, d), 0o700)


def test_bits_are_ored_in_and_nested_dirs_are_reached(tmp_path, unseal):
    top = tmp_path / "copy"
    deep = top / "a" / "b"
    deep.mkdir(parents=True)
    (deep / "f.sh").write_text("x", encoding="utf-8")
    (deep / "f.sh").chmod(0o555)
    deep.chmod(0o500)
    (top / "a").chmod(0o550)
    top.chmod(0o505)

    store._own_dirs(top)

    assert _mode(top) == 0o705
    assert _mode(top / "a") == 0o750
    assert _mode(deep) == 0o700
    assert _mode(deep / "f.sh") == 0o555     # files are the skill's


def test_a_linked_directory_s_target_is_left_alone(tmp_path, unseal):
    outside = tmp_path / "outside"
    outside.mkdir()
    outside.chmod(0o555)
    top = tmp_path / "copy"
    top.mkdir()
    (top / "shared").symlink_to(outside, target_is_directory=True)

    store._own_dirs(top)

    assert _mode(outside) == 0o555


def test_import_copy_of_a_read_only_tree_is_owner_rwx(sandbox, tmp_path,
                                                      unseal):
    src = tmp_path / "src"
    (src / "assets").mkdir(parents=True)
    (src / "assets").chmod(0o555)
    dst = tmp_path / "dst"

    store._copy_tree(src, dst, None)

    assert _mode(dst / "assets") == 0o755
