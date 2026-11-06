# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A corrupt lock file is reported on the terminal and never written over.

Measured before this fix: with the lock file corrupted under an install of
three skills, `boost list` printed "no skills installed" and exit 0 with
nothing on the terminal (the only notice was a line in boost.log), and
`boost install` of a skill not yet in the store printed "lock updated" over a
lock that now held that one skill — every other record gone, and `boost sync`
then re-filed the survivors as `local` skills linked to every agent.
"""
from __future__ import annotations

import json
import os
import shutil

import pytest

from boost_cli.core import catalog, lockfile, paths, registry, store
from boost_cli.errors import BoostError

GARBAGE = '{"skills": {"old": {"version": "1.0"}}, TRAILING GARBAGE'


def _corrupt() -> bytes:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    p.write_text(GARBAGE, encoding="utf-8")
    return p.read_bytes()


def _history() -> list[str]:
    d = paths.lock_history_dir()
    return sorted(f.name for f in d.iterdir()) if d.exists() else []


@pytest.fixture()
def tap(sandbox, fixture_tap_src, tmp_path):
    """A tap with a name no other test module uses."""
    src = tmp_path / "lock-corrupt-guard-tap"
    shutil.copytree(fixture_tap_src, src, symlinks=True)
    t = registry.add(str(src))
    catalog.rebuild_tap(t)
    return t


class TestReadWarns:
    def test_a_corrupt_read_warns_on_stderr_naming_the_backup(self, sandbox,
                                                               capsys):
        _corrupt()
        lockfile.read()
        cap = capsys.readouterr()
        assert cap.out == ""
        assert "lock file" in cap.err and "is corrupt" in cap.err
        assert ".skill-lock.json.corrupt" in cap.err
        # No write ever snapshotted a lock, so there is nothing to roll back to.
        assert ("nothing installed — `boost sync --rebuild-lock` sets it aside "
                "and re-records the store; the newest record is only in "
                "~/.agents/skills/.skill-lock.json.corrupt") in " ".join(
                    cap.err.split())
        assert "replay" not in cap.err

    def test_with_history_the_warning_names_the_rollback(self, sandbox, capsys):
        lockfile.set_skill("a", {"version": "1"})
        lockfile.set_skill("b", {"version": "1"})
        assert lockfile.has_history()
        _corrupt()
        lockfile.read()
        assert ("nothing installed — `boost replay rollback <id>` restores it "
                "as it was before its last change; the newest record is only "
                "in ~/.agents/skills/.skill-lock.json.corrupt") in " ".join(
                    capsys.readouterr().err.split())

    def test_it_warns_once_per_process(self, sandbox, capsys):
        _corrupt()
        lockfile.read()
        lockfile.read()
        lockfile.installed()
        assert capsys.readouterr().err.count("is corrupt") == 1

    def test_a_missing_or_sound_lock_says_nothing(self, sandbox, capsys):
        lockfile.read()
        lockfile.set_skill("a", {"version": "1"})
        lockfile.read()
        assert capsys.readouterr().err == ""
        assert lockfile._WARNED_CORRUPT is False


class TestWriteRefuses:
    def test_write_over_a_corrupt_lock_raises_and_keeps_the_bytes(self,
                                                                   sandbox):
        raw = _corrupt()
        with pytest.raises(BoostError) as ei:
            lockfile.set_skill("new", {"version": "2.0"})
        assert paths.lockfile_path().read_bytes() == raw
        assert str(ei.value) == ("lock file is corrupt — boost will not "
                                 "write over it")
        assert ei.value.hint == (
            "`boost sync --rebuild-lock` sets it aside and re-records the "
            "store; the newest record is only in "
            + paths.tilde(lockfile.corrupt_backup()))
        assert ".skill-lock.json.corrupt" in ei.value.hint
        assert lockfile.corrupt_backup().read_bytes() == raw
        assert _history() == []           # refused before the snapshot

    def test_refuse_corrupt_passes_a_missing_lock(self, sandbox):
        lockfile.refuse_corrupt()
        lockfile.set_skill("new", {"version": "2.0"})
        assert set(lockfile.installed()) == {"new"}

    def test_refuse_corrupt_passes_another_schema(self, sandbox):
        paths.ensure_dirs()
        paths.lockfile_path().write_text('{"version": 2, "skills": {"a": {}}}',
                                         encoding="utf-8")
        lockfile.refuse_corrupt()
        lockfile.set_skill("b", {})
        assert set(lockfile.installed()) == {"a", "b"}
        assert lockfile.check().ok

    def test_refuse_corrupt_raises_on_a_corrupt_lock(self, sandbox):
        _corrupt()
        with pytest.raises(BoostError):
            lockfile.refuse_corrupt()


class TestInstallRefuses:
    def test_a_new_skill_leaves_the_lock_and_the_store_alone(self, tap):
        store.install(catalog.resolve_one("brainstorming"))
        store.install(catalog.resolve_one("commit-messages"))
        raw = _corrupt()
        with pytest.raises(BoostError) as ei:
            store.install(catalog.resolve_one("tdd-workflow"))
        assert "corrupt" in str(ei.value)
        assert paths.lockfile_path().read_bytes() == raw
        assert not store.skill_store_dir("tdd-workflow").exists()

    def test_force_over_an_existing_skill_is_refused_too(self, tap):
        store.install(catalog.resolve_one("brainstorming"))
        raw = _corrupt()
        with pytest.raises(BoostError):
            store.install(catalog.resolve_one("brainstorming"), force=True)
        assert paths.lockfile_path().read_bytes() == raw

    def test_install_from_path_refuses_before_copying(self, sandbox, tmp_path):
        src = tmp_path / "handmade"
        src.mkdir()
        (src / "SKILL.md").write_text(
            "---\nname: handmade\ndescription: d\n---\nbody\n",
            encoding="utf-8")
        raw = _corrupt()
        with pytest.raises(BoostError):
            store.install_from_path(src)
        assert paths.lockfile_path().read_bytes() == raw
        assert not store.skill_store_dir("handmade").exists()


class TestRestore:
    def test_restore_makes_the_snapshot_the_lock(self, sandbox):
        lockfile.set_skill("a", {"version": "1"})
        lockfile.set_skill("b", {"version": "1"})   # snapshots {a}
        [hid] = [h["id"] for h in lockfile.history_list()]
        raw = _corrupt()
        got = lockfile.restore(hid)
        assert set(got["skills"]) == {"a"}
        assert lockfile.check().ok
        assert set(lockfile.installed()) == {"a"}
        assert lockfile.corrupt_backup().read_bytes() == raw
        snap = paths.lock_history_dir() / ("lock-%s.json" % hid)
        assert paths.lockfile_path().read_bytes() == snap.read_bytes()

    def test_restore_of_a_missing_entry_raises_and_writes_nothing(self,
                                                                  sandbox):
        raw = _corrupt()
        with pytest.raises(BoostError):
            lockfile.restore("19990101T000000Z")
        assert paths.lockfile_path().read_bytes() == raw


class TestCli:
    def test_list_warns_install_refuses_and_rollback_restores(self, tap,
                                                              boost):
        for name in ("brainstorming", "commit-messages", "jira-integration"):
            boost("install", name)
        newest = lockfile.history_list()[-1]["id"]      # holds the first two
        raw = _corrupt()

        res = boost("list")
        assert "is corrupt" in res.err and ".corrupt" in res.err
        assert "boost replay" in res.err

        res = boost("install", "tdd-workflow", expect=None)
        assert res.rc != 0
        assert "corrupt" in res.err
        assert paths.lockfile_path().read_bytes() == raw
        assert not store.skill_store_dir("tdd-workflow").exists()

        res = boost("replay", "rollback", newest)
        assert "as it was before the change after it" in res.out
        assert lockfile.check().ok
        assert set(lockfile.installed()) == {"brainstorming", "commit-messages"}
        assert lockfile.corrupt_backup().read_bytes() == raw

        # The rollback lost jira-integration's record, and doctor must not
        # send the user to `boost sync`, which re-files it as `local`.
        res = boost("doctor", expect=None)
        flat = " ".join(res.out.split())
        assert ("1 skill the restored lock file does not record "
                "(jira-integration)") in flat
        assert ".skill-lock.json.corrupt" in flat
        assert "added outside boost" not in flat

    def test_once_a_snapshot_is_newer_doctor_offers_sync_again(self, tap, boost):
        for name in ("brainstorming", "commit-messages"):
            boost("install", name)
        newest = lockfile.history_list()[-1]["id"]
        _corrupt()
        boost("replay", "rollback", newest)
        # Same-second clocks must not decide the test: age the backup.
        backup = lockfile.corrupt_backup()
        os.utime(backup, (1_000_000_000, 1_000_000_000))
        res = boost("doctor", expect=None)
        assert "1 skill added outside boost (commit-messages)" in res.out
        assert "restored lock file" not in res.out

    def test_rollback_json_restores_quietly(self, tap, boost):
        boost("install", "brainstorming")
        boost("install", "commit-messages")
        [hid] = [h["id"] for h in lockfile.history_list()]
        _corrupt()
        res = boost("replay", "rollback", hid, "--json")
        json.loads(res.out)
        assert set(lockfile.installed()) == {"brainstorming"}

    def test_a_declined_rollback_leaves_the_corrupt_lock(self, tap, boost,
                                                         monkeypatch):
        boost("install", "brainstorming")
        boost("install", "commit-messages")
        [hid] = [h["id"] for h in lockfile.history_list()]
        raw = _corrupt()
        monkeypatch.setattr("boost_cli.core.output.confirm",
                            lambda *a, **k: False)
        res = boost("replay", "rollback", hid, expect=1)
        assert "cancelled" in res.out
        assert paths.lockfile_path().read_bytes() == raw


def _snap(name: str, mtime: int):
    d = paths.lock_history_dir()
    d.mkdir(parents=True, exist_ok=True)
    f = d / name
    f.write_text("{}", encoding="utf-8")
    os.utime(f, (mtime, mtime))
    return f


def _backup(mtime: int):
    paths.ensure_dirs()
    b = lockfile.corrupt_backup()
    b.write_text(GARBAGE, encoding="utf-8")
    os.utime(b, (mtime, mtime))
    return b


class TestUnrestoredCorrupt:
    """The backup outranks history only while it is newer than every snapshot."""

    def test_no_backup_is_none(self, sandbox):
        _snap("lock-a.json", 2_000_000_000)
        assert lockfile.unrestored_corrupt() is None

    def test_a_backup_with_no_history_is_returned(self, sandbox):
        b = _backup(1_000_000_000)
        assert str(lockfile.unrestored_corrupt()) == str(b)

    def test_newer_than_every_snapshot_is_returned(self, sandbox):
        _snap("lock-a.json", 1_000_000_000)
        _snap("lock-b.json", 1_500_000_000)
        b = _backup(1_500_000_001)
        assert str(lockfile.unrestored_corrupt()) == str(b)

    def test_older_than_the_newest_snapshot_is_none(self, sandbox):
        _snap("lock-a.json", 1_000_000_000)
        _snap("lock-b.json", 1_500_000_000)
        _backup(1_499_999_999)
        assert lockfile.unrestored_corrupt() is None

    def test_an_equal_mtime_counts_as_newer(self, sandbox):
        _snap("lock-a.json", 1_500_000_000)
        b = _backup(1_500_000_000)
        assert str(lockfile.unrestored_corrupt()) == str(b)

    def test_other_files_in_history_are_ignored(self, sandbox):
        _snap("notes.json", 2_000_000_000)
        b = _backup(1_500_000_000)
        assert str(lockfile.unrestored_corrupt()) == str(b)

    def test_a_write_after_restore_supersedes_it(self, sandbox):
        lockfile.set_skill("a", {"version": "1"})
        lockfile.set_skill("b", {"version": "1"})
        [hid] = [h["id"] for h in lockfile.history_list()]
        _corrupt()
        lockfile.restore(hid)
        os.utime(lockfile.corrupt_backup(), (1_000_000_000, 1_000_000_000))
        lockfile.set_skill("c", {"version": "1"})   # snapshots the restored lock
        assert lockfile.unrestored_corrupt() is None

    def test_the_line_names_the_backup_and_what_sync_would_do(self, sandbox):
        b = lockfile.corrupt_backup()
        assert lockfile.unrestored_line(1, "jira", b) == (
            "1 skill the restored lock file does not record (jira) — its "
            "newest record is only in %s; `boost sync` would re-file it as a "
            "local skill" % paths.tilde(b))
        assert lockfile.unrestored_line(2, "x, y", b) == (
            "2 skills the restored lock file does not record (x, y) — its "
            "newest record is only in %s; `boost sync` would re-file them as "
            "local skills" % paths.tilde(b))


class TestMcpDoctor:
    def test_after_a_rollback_it_is_the_users_not_syncs(self, tap):
        from boost_cli.commands import configuration
        for name in ("brainstorming", "commit-messages"):
            store.install(catalog.resolve_one(name))
        newest = lockfile.history_list()[-1]["id"]
        _corrupt()
        lockfile.restore(newest)
        text, is_error = configuration._tool_doctor({})
        assert ("1 skill the restored lock file does not record "
                "(commit-messages)") in text
        assert "added outside boost" not in text
        assert ("1 issue(s) — 1 is the user's to change, and `boost sync` "
                "leaves it") in text
        assert is_error is True

    def test_once_superseded_sync_records_it_again(self, tap):
        from boost_cli.commands import configuration
        for name in ("brainstorming", "commit-messages"):
            store.install(catalog.resolve_one(name))
        newest = lockfile.history_list()[-1]["id"]
        _corrupt()
        lockfile.restore(newest)
        os.utime(lockfile.corrupt_backup(), (1_000_000_000, 1_000_000_000))
        text, _ = configuration._tool_doctor({})
        assert ("commit-messages was added outside boost — `boost sync` "
                "records it as a local skill and links it") in text
        assert "1 issue(s) — run `boost sync` to fix" in text
