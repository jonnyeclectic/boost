# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: one directory, two spellings.

A skills dir reached two ways — ``~/.cursor/skills -> ../.claude/skills``, an
agent dir set to the real path behind its default symlink, or one ``$HOME``
spelled ``/tmp/...`` and ``/private/tmp/...`` — is one directory. Swept as
two, doctor counted every broken link in it twice and heal crashed (rc 70)
unlinking one it had just removed. Judged by spelling alone, a link made under
one spelling of the store was foreign under the other, so uninstall left every
agent link dangling.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from boost_cli.core import agents, config, paths, store

pytestmark = pytest.mark.skipif(
    not hasattr(os, "symlink") or os.name == "nt",
    reason="symlinked directories need POSIX symlinks")


def _set_dir(agent, d):
    cfg = config.load()
    cfg["agents"][agent]["dir"] = str(d)
    config.save(cfg)


@pytest.fixture()
def aliased_store(sandbox, monkeypatch):
    """The real store dir, and ``store_dir()`` spelled through an alias."""
    real = paths.store_dir()
    real.mkdir(parents=True)
    alias_home = sandbox.parent / "alias-home"
    alias_home.symlink_to(sandbox)
    nominal = alias_home / ".agents" / "skills"
    monkeypatch.setattr(store.paths, "store_dir", lambda: nominal)
    return real, nominal


class TestPointsIntoStoreThroughAnAlias:
    def test_a_dangling_link_in_the_real_spelling_is_boost_s(
            self, aliased_store, tmp_path):
        real, _nominal = aliased_store
        link = tmp_path / "link"
        link.symlink_to(real / "gone")
        assert store.points_into_store(link) is True
        assert store.is_boost_link(link) is True

    def test_a_live_link_in_the_alias_spelling_is_boost_s(
            self, aliased_store, tmp_path, monkeypatch):
        real, nominal = aliased_store
        (real / "x").mkdir()
        link = tmp_path / "link"
        link.symlink_to(nominal / "x")
        # ... and judged with the store spelled the real way round.
        monkeypatch.setattr(store.paths, "store_dir", lambda: real)
        assert store.is_boost_link(link) is True

    def test_a_link_outside_the_store_is_not_boost_s(
            self, aliased_store, tmp_path):
        real, nominal = aliased_store
        (real.parent / "skills-backup").mkdir()
        for target in (real.parent / "skills-backup" / "x",
                       nominal.parent / "skills-backup" / "x",
                       tmp_path / "elsewhere" / "x"):
            link = tmp_path / "link"
            link.symlink_to(target)
            assert store.points_into_store(link) is False, target
            assert store.is_boost_link(link) is False, target
            link.unlink()

    def test_a_link_to_another_agent_s_link_is_not_boost_s(
            self, aliased_store, tmp_path):
        # One hop into someone else's dir. `points_into_store` gates
        # deletion, so it must not follow the target's own last component
        # even where that is a live link into the store.
        real, _nominal = aliased_store
        (real / "x").mkdir()
        other = tmp_path / "other"
        other.mkdir()
        (other / "x").symlink_to(real / "x")
        link = tmp_path / "link"
        link.symlink_to(other / "x")
        assert store.points_into_store(link) is False
        assert store.resolves_into_store(link) is True   # the other question


class TestDirIdentity:
    def test_an_alias_and_its_target_are_one_dir(self, tmp_path):
        real = tmp_path / "real"
        real.mkdir()
        alias = tmp_path / "alias"
        alias.symlink_to(real)
        assert agents.dir_identity(alias) == agents.dir_identity(real)
        assert agents.dir_identity(tmp_path) != agents.dir_identity(real)

    def test_a_missing_dir_compares_by_where_it_would_be(self, tmp_path):
        real = tmp_path / "real"
        real.mkdir()
        alias = tmp_path / "alias"
        alias.symlink_to(real)
        assert (agents.dir_identity(alias / "nope")
                == agents.dir_identity(real / "nope")
                == os.path.normcase(os.path.realpath(real / "nope")))
        assert (agents.dir_identity(real / "nope")
                != agents.dir_identity(real / "other"))

    @staticmethod
    def _fake_stat(monkeypatch, table):
        real_stat = Path.stat

        def fake(self, *a, **kw):
            st = real_stat(self, *a, **kw)
            dev, ino = table.get(self.name, (st.st_dev, st.st_ino))
            vals = list(st)
            vals[1], vals[2] = ino, dev   # st_ino, st_dev
            return os.stat_result(vals)
        monkeypatch.setattr(Path, "stat", fake)

    def test_same_inode_on_two_devices_is_two_dirs(self, tmp_path,
                                                   monkeypatch):
        a, b = tmp_path / "a", tmp_path / "b"
        a.mkdir()
        b.mkdir()
        self._fake_stat(monkeypatch, {"a": (1, 42), "b": (2, 42)})
        assert agents.dir_identity(a) == (1, 42)
        assert agents.dir_identity(a) != agents.dir_identity(b)

    def test_a_zero_inode_falls_back_to_the_real_path(self, tmp_path,
                                                      monkeypatch):
        # Windows on FAT/exFAT: st_ino is 0 for every dir on the volume.
        a, b = tmp_path / "a", tmp_path / "b"
        a.mkdir()
        b.mkdir()
        self._fake_stat(monkeypatch, {"a": (7, 0), "b": (7, 0)})
        assert agents.dir_identity(a) == os.path.normcase(os.path.realpath(a))
        assert agents.unique_dirs([a, b]) == [a, b]

    def test_unique_dirs_keeps_the_first_spelling_in_order(self, tmp_path):
        a, b = tmp_path / "a", tmp_path / "b"
        a.mkdir()
        b.mkdir()
        alias = tmp_path / "alias"
        alias.symlink_to(a)
        assert agents.unique_dirs([a, b, alias, a, b]) == [a, b]
        assert agents.unique_dirs([alias, a]) == [alias]
        assert agents.unique_dirs([]) == []


class TestSweepDirsCountsEachDirOnce:
    def test_two_agents_sharing_one_dir(self, sandbox):
        claude = sandbox / ".claude" / "skills"
        claude.mkdir(parents=True)
        (sandbox / ".cursor").mkdir()
        (sandbox / ".cursor" / "skills").symlink_to(
            os.path.join("..", ".claude", "skills"))
        dirs = agents.sweep_dirs()
        assert claude in dirs
        assert sandbox / ".cursor" / "skills" not in dirs
        assert len(dirs) == len(agents.unique_dirs(dirs))
        assert len(dirs) == len(agents.unlinking_agents()) - 1

    def test_a_configured_dir_that_is_the_default_s_real_path(self, sandbox):
        real = sandbox / "dotfiles" / "claude-skills"
        real.mkdir(parents=True)
        (sandbox / ".claude").mkdir()
        (sandbox / ".claude" / "skills").symlink_to(real)
        _set_dir("claude-code", real)
        assert agents.former_link_dirs() == []
        assert agents.sweep_dirs() == list(agents.unlinking_agents().values())

    def test_a_remembered_dir_in_another_spelling(self, sandbox):
        claude = sandbox / ".claude" / "skills"
        claude.mkdir(parents=True)
        alias = sandbox.parent / "alias-home"
        alias.symlink_to(sandbox)
        agents.remember_link_dir("claude-code", alias / ".claude" / "skills")
        assert agents.former_link_dirs() == []
        assert agents.sweep_dirs().count(claude) == 1

    def test_a_genuinely_former_dir_is_still_swept(self, sandbox):
        old = sandbox / "old-cursor"
        old.mkdir()
        agents.remember_link_dir("cursor", old)
        assert agents.former_link_dirs() == [("cursor", old)]
        assert agents.sweep_dirs()[-1] == old

    def test_one_dir_remembered_twice_is_former_once(self, sandbox):
        old = sandbox / "old-cursor"
        old.mkdir()
        alias = sandbox / "old-alias"
        alias.symlink_to(old)
        agents.remember_link_dir("cursor", old)
        agents.remember_link_dir("windsurf", alias)
        assert agents.former_link_dirs() == [("cursor", old)]
