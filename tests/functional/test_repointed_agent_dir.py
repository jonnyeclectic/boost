# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""An agent whose dir is repointed keeps the links made under the old one.

The lock records a skill's agents by name, and every removal and broken-link
sweep walked each agent's *current* dir. After `config set agents.cursor.dir`
the link in `~/.cursor/skills` was reachable by nothing: uninstall reported
cursor unlinked over it, and doctor, heal, sync and clean saw no broken link.
"""
from __future__ import annotations

import os

from boost_cli.core import agents, paths


def _old_link():
    return paths.home() / ".cursor" / "skills" / "brainstorming"


def _repoint(boost):
    boost("config", "set", "agents.cursor.dir", "~/.cursor2/skills")


def test_uninstall_removes_the_link_in_the_old_dir(boost, installed):
    _repoint(boost)
    boost("sync")
    new = paths.home() / ".cursor2" / "skills" / "brainstorming"
    assert os.path.islink(_old_link()) and os.path.islink(new)

    boost("uninstall", "brainstorming")

    assert not os.path.lexists(_old_link())
    assert not os.path.lexists(new)


def test_the_old_dir_is_a_former_dir_once_repointed(boost, installed):
    old = paths.home() / ".cursor" / "skills"
    assert ("cursor", old) not in agents.former_link_dirs()
    _repoint(boost)
    assert ("cursor", old) in agents.former_link_dirs()
    assert old in agents.sweep_dirs()


def test_doctor_counts_and_heal_removes_a_dangling_old_link(boost, installed):
    _repoint(boost)
    # A link boost made under the old dir, into a store dir that is gone.
    os.unlink(_old_link())
    os.symlink(paths.store_dir() / "gone-skill", _old_link())

    out = boost("doctor", expect=1).out
    assert "1 broken symlink in agent dirs" in out

    boost("heal")
    assert not os.path.lexists(_old_link())


def test_sync_sweeps_a_stale_old_link(boost, installed):
    _repoint(boost)
    os.unlink(_old_link())
    os.symlink(paths.store_dir() / "gone-skill", _old_link())
    boost("sync")
    assert not os.path.lexists(_old_link())
