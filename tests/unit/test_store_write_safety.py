# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Store mutations that cannot finish must change nothing, or finish recorded.

Measured before this: an uninstall under a read-only ``~/.agents/skills``
removed the links and ``SKILL.md``, left the dir at ``d-w-------`` and
crashed at exit 70 with the lock row in place; a lock write that failed
(full disk, immutable file) crashed the same way after the copy was already
deleted; and an upgrade interrupted after its copy left the new content under
the old row, so every later ``update`` held it back as "local edits".
"""
from __future__ import annotations

import errno
import os
import shutil
import stat
import subprocess
import sys

import pytest

from boost_cli import cli
from boost_cli.core import catalog, lockfile, paths, registry, store, util
from boost_cli.errors import BoostError

requires_posix_modes = pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX permission semantics")
requires_unprivileged = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root ignores the read-only mode the test relies on")


@pytest.fixture()
def origin(sandbox, fixture_tap_src, tmp_path):
    """A private copy of the fixture tap, tapped, with brainstorming installed."""
    src = tmp_path / "store-write-safety-tap"
    shutil.copytree(fixture_tap_src, src, symlinks=True)
    catalog.rebuild_tap(registry.add(str(src)))
    store.install(catalog.resolve_one("brainstorming"))
    return src


def _links(name: str) -> list[str]:
    return store.linked_agents(name)


def _enospc(monkeypatch) -> None:
    real = util.atomic_write_text

    def full(p, *a, **k):
        if "skill-lock" in str(p):
            raise OSError(errno.ENOSPC, os.strerror(errno.ENOSPC))
        return real(p, *a, **k)
    monkeypatch.setattr(util, "atomic_write_text", full)


class TestLockWriteRefused:
    def test_a_full_disk_is_a_boost_error_naming_the_lock(
            self, sandbox, monkeypatch):
        _enospc(monkeypatch)
        with pytest.raises(BoostError) as caught:
            lockfile.write(lockfile.read())
        assert str(caught.value) == "could not save %s (%s)" % (
            paths.tilde(paths.lockfile_path()), os.strerror(errno.ENOSPC))
        assert caught.value.hint == ("free space or clear the file's "
                                     "immutable flag, then re-run")

    @requires_posix_modes
    @requires_unprivileged
    def test_a_read_only_store_names_the_dir_and_the_chmod(
            self, sandbox, monkeypatch):
        d = paths.store_dir()
        d.mkdir(parents=True, exist_ok=True)
        d.chmod(0o555)
        try:
            with pytest.raises(BoostError) as caught:
                lockfile.write(lockfile.read())
        finally:
            d.chmod(0o755)
        assert str(caught.value).endswith(
            "): %s is not writable" % paths.tilde(d))
        assert caught.value.hint == "run `chmod u+w %s`, then re-run" % (
            paths.tilde(d))

    def test_uninstall_refused_by_the_lock_deletes_nothing(
            self, origin, monkeypatch, capsys):
        before = lockfile.get_skill("brainstorming")
        linked = _links("brainstorming")
        _enospc(monkeypatch)
        assert cli.main(["uninstall", "brainstorming"]) == 1
        assert "could not save" in capsys.readouterr().err
        assert lockfile.get_skill("brainstorming") == before
        assert (store.skill_store_dir("brainstorming") / "SKILL.md").is_file()
        assert linked and _links("brainstorming") == linked

    def test_a_failed_delete_puts_the_row_back(self, origin, monkeypatch):
        before = lockfile.get_skill("brainstorming")

        def stuck(*_a, **_k):
            raise OSError(errno.EBUSY, "busy")
        monkeypatch.setattr(util, "remove_path", stuck)
        with pytest.raises(OSError, match=r"busy"):
            store.uninstall("brainstorming")
        assert lockfile.get_skill("brainstorming") == before

    def test_a_clean_uninstall_still_drops_the_row(self, origin):
        res = store.uninstall("brainstorming")
        assert res["kind"] == "skill"
        assert lockfile.get_skill("brainstorming") is None
        assert not os.path.lexists(store.skill_store_dir("brainstorming"))
        assert _links("brainstorming") == []


@requires_posix_modes
@requires_unprivileged
class TestReadOnlyStore:
    def test_uninstall_refuses_before_touching_anything(self, origin, capsys):
        before = lockfile.get_skill("brainstorming")
        linked = _links("brainstorming")
        d = paths.store_dir()
        d.chmod(0o555)
        try:
            with pytest.raises(BoostError) as caught:
                store.uninstall("brainstorming")
            skill = store.skill_store_dir("brainstorming")
            mode = stat.S_IMODE(skill.stat().st_mode)
            assert (skill / "SKILL.md").is_file()
        finally:
            d.chmod(0o755)
        assert str(caught.value) == "cannot uninstall brainstorming: %s " \
            "is not writable" % paths.tilde(d)
        assert caught.value.hint == "run `chmod u+w %s`, then re-run" % (
            paths.tilde(d))
        assert mode & 0o700 == 0o700
        assert lockfile.get_skill("brainstorming") == before
        assert linked and _links("brainstorming") == linked
        # ...so the same command finishes once the dir allows it.
        store.uninstall("brainstorming")
        assert lockfile.get_skill("brainstorming") is None

    def test_the_cli_exits_one_not_seventy(self, origin, capsys):
        d = paths.store_dir()
        d.chmod(0o555)
        try:
            rc = cli.main(["uninstall", "brainstorming"])
        finally:
            d.chmod(0o755)
        assert rc == 1
        assert "cannot uninstall brainstorming" in capsys.readouterr().err


def _git(*args, cwd) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class TestInterruptedUpgrade:
    def _bump(self, origin) -> None:
        md = origin / "skills" / "brainstorming" / "SKILL.md"
        md.write_text(md.read_text(encoding="utf-8").replace(
            "version: 1.4.0", "version: 1.5.0") + "\nA new line.\n",
            encoding="utf-8")
        _git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam",
             "bump", cwd=origin)

    def test_the_old_copy_comes_back_and_the_next_update_lands(
            self, origin, monkeypatch, capsys):
        before = lockfile.get_skill("brainstorming")
        dest = store.skill_store_dir("brainstorming")
        assert util.sha256_dir(dest) == before["sha256"]
        self._bump(origin)
        real = store.link_agents

        def boom(*_a, **_k):
            raise KeyboardInterrupt
        monkeypatch.setattr(store, "link_agents", boom)
        assert cli.main(["update"]) == 130
        # The row never moved, so neither did the copy it describes.
        assert lockfile.get_skill("brainstorming") == before
        assert util.sha256_dir(dest) == before["sha256"]
        assert [p.name for p in paths.store_dir().iterdir()
                if p.name.startswith(".brainstorming.")] == []

        monkeypatch.setattr(store, "link_agents", real)
        capsys.readouterr()
        assert cli.main(["update"]) == 0
        out = capsys.readouterr()
        assert "local edits" not in out.out + out.err
        assert "held back" not in out.out + out.err
        row = lockfile.get_skill("brainstorming")
        assert row["version"] == "1.5.0"
        assert row["sha256"] == util.sha256_dir(dest)

    def test_a_recorded_upgrade_keeps_its_new_copy(self, origin, monkeypatch):
        # Interrupted after the row landed: the new copy is what the row
        # describes, so swapping the old one back would be the mismatch.
        self._bump(origin)
        assert cli.main(["update"]) == 0
        real_record = store.record_rebuilt

        def then_boom(name, entry):
            real_record(name, entry)
            raise KeyboardInterrupt
        monkeypatch.setattr(store, "record_rebuilt", then_boom)
        with pytest.raises(KeyboardInterrupt):
            store.install(catalog.resolve_one("brainstorming"), force=True)
        row = lockfile.get_skill("brainstorming")
        dest = store.skill_store_dir("brainstorming")
        assert row["version"] == "1.5.0"
        assert row["sha256"] == util.sha256_dir(dest)
        assert [p.name for p in paths.store_dir().iterdir()
                if p.name.startswith(".brainstorming.")] == []

    def test_restore_moves_the_new_copy_aside_first(self, tmp_path):
        dest = tmp_path / "x"
        dest.mkdir()
        (dest / "new").write_text("n", encoding="utf-8")
        old = tmp_path / ".x.tmpabc.old"
        old.mkdir()
        (old / "old").write_text("o", encoding="utf-8")
        store._restore_old_copy(old, dest)
        assert sorted(p.name for p in tmp_path.iterdir()) == ["x"]
        assert [p.name for p in dest.iterdir()] == ["old"]

    def test_restore_without_a_new_copy_just_renames(self, tmp_path):
        dest = tmp_path / "x"
        old = tmp_path / ".x.tmpabc.old"
        old.mkdir()
        store._restore_old_copy(old, dest)
        assert sorted(p.name for p in tmp_path.iterdir()) == ["x"]

    def test_a_failed_restore_puts_the_new_copy_back(self, tmp_path, monkeypatch):
        dest = tmp_path / "x"
        dest.mkdir()
        (dest / "new").write_text("n", encoding="utf-8")
        old = tmp_path / ".x.tmpabc.old"
        old.mkdir()
        real = os.replace

        def refuse_old(a, b):
            if os.fspath(a) == os.fspath(old):
                raise OSError(errno.EACCES, "denied")
            real(a, b)
        monkeypatch.setattr(store.os, "replace", refuse_old)
        with pytest.raises(OSError):
            store._restore_old_copy(old, dest)
        assert sorted(p.name for p in tmp_path.iterdir()) == [".x.tmpabc.old", "x"]
        assert [p.name for p in dest.iterdir()] == ["new"]
