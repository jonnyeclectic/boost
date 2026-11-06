# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Interrupts in uninstall, quarantine, and rule and workflow installs.

Measured before these fixes, against a fixture tap:

* An uninstall killed at the store removal left the store dir under the
  skill's own name with no row; doctor called it "added outside boost" and
  `boost sync` adopted it as a local skill linked into every agent.
* Ctrl-C during uninstall or quarantine restored the lock row but not the
  links already removed, so `list` and `verify` claimed links that were gone.
* A rule or workflow install interrupted at its lock write (or refused it)
  left every agent's file on disk with no row; uninstall said "not installed".
"""
from __future__ import annotations

import errno
import itertools
import os
import shutil
import sys
import time
from pathlib import Path

import pytest

from boost_cli.core import catalog, lockfile, paths, registry, store, util

_SEQ = itertools.count()

@pytest.fixture()
def tap(sandbox, fixture_tap_src, tmp_path):
    src = tmp_path / ("interrupt-safety-%d" % next(_SEQ))
    shutil.copytree(fixture_tap_src, src, symlinks=True)
    t = registry.add(str(src))
    catalog.rebuild_tap(t)
    return t


def _raise_on_call(monkeypatch, module, attr, nth=1, exc=KeyboardInterrupt):
    """Make ``module.attr`` raise ``exc`` on its ``nth`` call, pass through
    otherwise; returns the list of call counts seen."""
    real = getattr(module, attr)
    calls: list[int] = []

    def wrapped(*a, **k):
        calls.append(len(calls) + 1)
        if len(calls) == nth:
            raise exc() if isinstance(exc, type) else exc
        return real(*a, **k)
    monkeypatch.setattr(module, attr, wrapped)
    return calls


# --------------------------------------------------------------------------
# uninstall
# --------------------------------------------------------------------------

@pytest.fixture()
def installed(tap):
    store.install(catalog.resolve_one("brainstorming"))
    linked = store.linked_agents("brainstorming")
    assert linked
    return lockfile.get_skill("brainstorming"), linked


def _staging_dirs():
    return sorted(p.name for p in paths.store_dir().iterdir()
                  if store._temp_token(p.name, ""))


class TestUninstallStaging:
    def test_the_copy_is_staged_before_the_row_goes(
            self, installed, monkeypatch):
        seen: list[tuple[bool, int]] = []
        real = lockfile.remove_skill

        def spy(name):
            seen.append((os.path.lexists(store.skill_store_dir(name)),
                         len(_staging_dirs())))
            return real(name)
        monkeypatch.setattr(lockfile, "remove_skill", spy)
        store.uninstall("brainstorming")
        assert seen == [(False, 1)]
        assert _staging_dirs() == []
        assert not os.path.lexists(store.skill_store_dir("brainstorming"))

    def test_a_killed_uninstall_leaves_nothing_sync_adopts(self, installed):
        # The state a kill after the row went leaves: staged, row gone.
        staged = store._stage_for_removal(store.skill_store_dir("brainstorming"))
        assert staged is not None
        lockfile.remove_skill("brainstorming")
        store.unlink_agents("brainstorming")
        assert store.unrecorded_store_dirs(lockfile.read()["skills"]) == []
        assert store.stale_temps(now=time.time() + store.STALE_TEMP_AGE + 1) == [
            (staged, "stale staging dir")]
        assert (staged / "SKILL.md").is_file()

    def test_stage_of_nothing_is_none(self, sandbox):
        assert store._stage_for_removal(paths.store_dir() / "absent") is None

    def test_unstage_puts_it_back_only_when_dest_is_free(self, installed):
        dest = store.skill_store_dir("brainstorming")
        staged = store._stage_for_removal(dest)
        assert staged is not None
        assert not os.path.lexists(dest)
        store._unstage(staged, dest)
        assert (dest / "SKILL.md").is_file()
        assert not os.path.lexists(staged)
        store._unstage(None, dest)
        store._unstage(staged, dest)  # gone: nothing to do
        assert (dest / "SKILL.md").is_file()

    def test_a_refused_row_write_renames_the_copy_back(
            self, installed, monkeypatch):
        entry, linked = installed
        _raise_on_call(monkeypatch, lockfile, "remove_skill",
                       exc=OSError(errno.ENOSPC, "No space left on device"))
        with pytest.raises(OSError, match="No space"):
            store.uninstall("brainstorming")
        assert (store.skill_store_dir("brainstorming") / "SKILL.md").is_file()
        assert _staging_dirs() == []
        assert lockfile.get_skill("brainstorming") == entry
        assert store.linked_agents("brainstorming") == linked


class TestUninstallRelinks:
    @pytest.mark.parametrize("step", [(util, "remove_path"),
                                      (lockfile, "remove_skill")])
    def test_ctrl_c_restores_row_copy_and_links(self, installed, monkeypatch,
                                                step):
        entry, linked = installed
        _raise_on_call(monkeypatch, *step)
        with pytest.raises(KeyboardInterrupt):
            store.uninstall("brainstorming")
        assert lockfile.get_skill("brainstorming") == entry
        assert (store.skill_store_dir("brainstorming") / "SKILL.md").is_file()
        assert _staging_dirs() == []
        assert store.linked_agents("brainstorming") == linked
        assert sorted(linked) == sorted(entry["agents"])

    def test_interrupt_part_way_through_unlinking_relinks_those_gone(
            self, installed, monkeypatch):
        entry, linked = installed
        # The second link removal is interrupted, after the first went.
        real_unlink = os.unlink
        calls: list[str] = []

        def unlink(path, *a, **k):
            if os.path.islink(path):  # noqa: FURB146
                calls.append(str(path))
                if len(calls) == 2:
                    raise KeyboardInterrupt
            return real_unlink(path, *a, **k)
        monkeypatch.setattr(os, "unlink", unlink)
        with pytest.raises(KeyboardInterrupt):
            store.uninstall("brainstorming")
        monkeypatch.setattr(os, "unlink", real_unlink)
        assert len(calls) == 2
        assert lockfile.get_skill("brainstorming") == entry
        assert store.linked_agents("brainstorming") == linked

    def test_unlink_agents_fills_into_as_it_goes(self, installed):
        _entry, linked = installed
        got: list[str] = []
        assert store.unlink_agents("brainstorming", into=got) is got
        assert got == linked

    def test_relink_removed_of_nothing_links_nothing(self, installed):
        _entry, linked = installed
        store.unlink_agents("brainstorming")
        assert store.relink_removed("brainstorming", []) == []
        assert store.linked_agents("brainstorming") == []
        assert store.relink_removed("brainstorming", linked[:1]) == linked[:1]
        assert store.linked_agents("brainstorming") == linked[:1]

    def test_relink_removed_swallows_a_failure(self, installed, monkeypatch):
        def boom(*_a, **_k):
            raise RuntimeError("disk on fire")
        monkeypatch.setattr(store, "link_agents", boom)
        assert store.relink_removed("brainstorming", ["cursor"]) == []


class TestQuarantineRelinks:
    @pytest.mark.parametrize("step", [(lockfile, "write"),
                                      (store, "hold_store_copy")])
    def test_ctrl_c_restores_copy_and_links(self, installed, monkeypatch,
                                            step):
        entry, linked = installed
        _raise_on_call(monkeypatch, *step)
        with pytest.raises(KeyboardInterrupt):
            store.quarantine_skill("brainstorming", dict(entry))
        row = lockfile.get_skill("brainstorming")
        assert row == entry
        assert not row.get("quarantined")
        assert (store.skill_store_dir("brainstorming") / "SKILL.md").is_file()
        assert store.linked_agents("brainstorming") == linked

    def test_a_clean_quarantine_still_unlinks(self, installed):
        entry, linked = installed
        removed, blocked = store.quarantine_skill("brainstorming", dict(entry))
        assert removed == linked
        assert blocked == {}
        assert store.linked_agents("brainstorming") == []
        assert lockfile.get_skill("brainstorming")["quarantined"] is True


# --------------------------------------------------------------------------
# rule and workflow installs
# --------------------------------------------------------------------------

RULE = "---\nname: house-style\n---\n\nAlways %s.\n"
WORKFLOW = ("---\nname: ship-it\ndescription: Ship the current branch.\n---\n\n"
            "Run the release %s.\n")


def _rule(tap, says="test first"):
    rel = "rules/house-style.mdc"
    src = tap.path / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(RULE % says, encoding="utf-8")
    return {"name": "house-style", "kind": "rule", "tap": tap.name,
            "version": "1.0.0", "rel_dir": "rules", "skill_md": rel,
            "description": "", "curated": False,
            "meta": {"name": "house-style"}}


def _workflow(tap, says="checklist"):
    rel = "commands/ship-it.md"
    src = tap.path / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(WORKFLOW % says, encoding="utf-8")
    return {"name": "ship-it", "kind": "workflow", "tap": tap.name,
            "version": "1.0.0", "rel_dir": "commands", "skill_md": rel,
            "description": "Ship the current branch.", "curated": False,
            "meta": {"name": "ship-it"}}


def _paths(kind, name):
    get = lockfile.get_rule if kind == "rule" else lockfile.get_workflow
    return [m["path"] for m in get(name)["materializations"]]


def _snapshot():
    """Every file under the sandbox HOME, as {relative path: bytes}, outside
    boost's own state and the tap clones."""
    home = paths.home()
    found = {}
    for root, dirs, files in os.walk(home):
        dirs[:] = [d for d in dirs if d not in (".boost", ".git")]
        for f in files:
            if f.startswith(".skill-lock") or f.startswith(util.TEMP_PREFIX):
                continue
            p = Path(root, f)
            found[p.relative_to(home).as_posix()] = p.read_bytes()
    return found


class TestRuleRollback:
    @pytest.mark.parametrize("exc", [
        KeyboardInterrupt, OSError(errno.ENOSPC, "No space left on device")])
    def test_a_failed_lock_write_removes_every_file(self, tap, monkeypatch,
                                                    exc):
        entry = _rule(tap)
        claude_md = paths.home() / ".claude" / "CLAUDE.md"
        claude_md.parent.mkdir(parents=True, exist_ok=True)
        claude_md.write_bytes(b"# mine\r\nkeep this\r\n")
        before = _snapshot()
        _raise_on_call(monkeypatch, lockfile, "write", exc=exc)
        with pytest.raises((KeyboardInterrupt, OSError)):
            store.install(entry)
        assert lockfile.get_rule("house-style") is None
        assert _snapshot() == before
        assert claude_md.read_bytes() == b"# mine\r\nkeep this\r\n"

    def test_the_files_written_are_the_ones_rolled_back(self, tap,
                                                        monkeypatch):
        # Pins that the rollback above had something to undo.
        store.install(_rule(tap))
        written = _paths("rule", "house-style")
        assert len(written) >= 3
        assert all(os.path.isfile(p) for p in written)

    def test_an_interrupted_upgrade_restores_the_old_text(self, tap,
                                                          monkeypatch):
        store.install(_rule(tap, "test first"))
        before = _snapshot()
        row = lockfile.get_rule("house-style")
        entry = _rule(tap, "write docs")
        _raise_on_call(monkeypatch, lockfile, "write")
        with pytest.raises(KeyboardInterrupt):
            store.install(entry, force=True)
        assert lockfile.get_rule("house-style") == row
        assert _snapshot() == before

    def test_an_interrupt_after_the_row_landed_keeps_the_files(
            self, tap, monkeypatch):
        entry = _rule(tap)
        _raise_on_call(monkeypatch, store.journal, "log")
        with pytest.raises(KeyboardInterrupt):
            store.install(entry)
        assert lockfile.get_rule("house-style") is not None
        assert all(os.path.isfile(p) for p in _paths("rule", "house-style"))


class TestWorkflowRollback:
    @pytest.mark.parametrize("exc", [
        KeyboardInterrupt, OSError(errno.ENOSPC, "No space left on device")])
    def test_a_failed_lock_write_removes_files_and_store_copy(
            self, tap, monkeypatch, exc):
        entry = _workflow(tap)
        before = _snapshot()
        _raise_on_call(monkeypatch, lockfile, "write", exc=exc)
        with pytest.raises((KeyboardInterrupt, OSError)):
            store.install(entry)
        assert lockfile.get_workflow("ship-it") is None
        assert not os.path.lexists(store.skill_store_dir("ship-it"))
        assert _snapshot() == before

    def test_the_files_written_include_a_store_copy(self, tap):
        store.install(_workflow(tap))
        written = _paths("workflow", "ship-it")
        assert str(store.skill_store_dir("ship-it") / "SKILL.md") in written
        assert len(written) >= 3

    def test_an_interrupted_upgrade_restores_files_and_copy(
            self, tap, monkeypatch):
        store.install(_workflow(tap, "checklist"))
        before = _snapshot()
        row = lockfile.get_workflow("ship-it")
        entry = _workflow(tap, "playbook")
        _raise_on_call(monkeypatch, lockfile, "write")
        with pytest.raises(KeyboardInterrupt):
            store.install(entry, force=True)
        assert lockfile.get_workflow("ship-it") == row
        assert _snapshot() == before
        assert (store.skill_store_dir("ship-it") / "SKILL.md").is_file()


class TestUndoHelpers:
    def test_note_prior_records_text_or_absence(self, sandbox, tmp_path):
        undo: list = []
        there = tmp_path / "there.md"
        there.write_bytes(b"a\r\nb\r\n")
        store._note_prior(undo, there)
        store._note_prior(undo, tmp_path / "absent.md", user_file=True)
        assert undo == [(there, "a\r\nb\r\n", False),
                        (tmp_path / "absent.md", None, True)]

    def test_note_prior_skips_what_it_cannot_read(self, sandbox, tmp_path):
        undo: list = []
        bad = tmp_path / "bad.md"
        bad.write_bytes(b"\xff\xfe\xfa")
        store._note_prior(undo, bad)
        store._note_prior(undo, tmp_path)  # a directory
        assert undo == []

    def test_undo_writes_newest_first(self, sandbox, tmp_path):
        f = tmp_path / "shared.md"
        f.write_text("orig", encoding="utf-8")
        undo: list = []
        store._note_prior(undo, f)
        f.write_text("first", encoding="utf-8")
        store._note_prior(undo, f)
        f.write_text("second", encoding="utf-8")
        new = tmp_path / "new.md"
        store._note_prior(undo, new)
        new.write_text("x", encoding="utf-8")
        store._undo_writes(undo)
        assert f.read_text(encoding="utf-8") == "orig"
        assert not new.exists()

    def test_undo_writes_leaves_an_unchanged_file_alone(self, sandbox,
                                                        tmp_path):
        f = tmp_path / "same.md"
        f.write_text("same", encoding="utf-8")
        f.chmod(0o644)
        undo = [(f, "same", False)]
        store._undo_writes(undo)
        if sys.platform != "win32":
            assert f.stat().st_mode & 0o777 == 0o644

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlinks")
    def test_undo_writes_restores_a_user_file_through_its_link(
            self, sandbox, tmp_path):
        real = tmp_path / "dotfiles" / "CLAUDE.md"
        real.parent.mkdir()
        real.write_text("mine", encoding="utf-8")
        link = tmp_path / "CLAUDE.md"
        link.symlink_to(real)
        undo: list = []
        store._note_prior(undo, link, user_file=True)
        util.write_user_file(link, "mine + block")
        store._undo_writes(undo)
        assert link.is_symlink()
        assert real.read_text(encoding="utf-8") == "mine"

    def test_row_landed(self, sandbox):
        assert store._row_landed(lambda n: {"a": 1}, "x", {"a": 1}) is True
        assert store._row_landed(lambda n: {"a": 2}, "x", {"a": 1}) is False
        assert store._row_landed(lambda n: {"a": 1}, "x", None) is False

        def boom(_n):
            raise ValueError("corrupt")
        assert store._row_landed(boom, "x", {"a": 1}) is False
