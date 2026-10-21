# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A lock boost cannot use is refused, kept, and given a remedy that works.

Measured before this fix: a lock stamped ``"version": 4`` was refused by
`verify`, `sync` and `heal` (each sending the user to `boost replay`), while
`pin`, `tag` and `install` rewrote it as v3 with a green tick. A lock whose
``rules`` was ``[]`` or whose row was a string crashed doctor, heal, list,
sync, outdated and update at exit 70. The one ``.corrupt`` backup was
overwritten by the next corrupt read. And after the first install there is no
history at all, so every "restore with `boost replay`" named a command that
answered "no lock history yet".
"""
from __future__ import annotations

import json

import pytest

from boost_cli.core import lockfile, paths
from boost_cli.errors import BoostError

REBUILD = "rebuild it from the store with `boost sync --rebuild-lock`"


def _put(raw) -> bytes:
    paths.ensure_dirs()
    p = paths.lockfile_path()
    p.write_text(raw if isinstance(raw, str) else json.dumps(raw),
                 encoding="utf-8")
    return p.read_bytes()


def _backups() -> list[str]:
    return [b.name for b in lockfile.corrupt_backups()]


class TestNewerSchema:
    def test_write_over_a_newer_lock_raises_and_keeps_every_byte(self, sandbox):
        raw = _put({"version": 4, "skills": {"a": {}}, "future": {"k": 1}})
        with pytest.raises(BoostError) as ei:
            lockfile.write({"skills": {}})
        assert ei.value.message == ("lock file is schema v4, newer than this "
                                    "boost's v3 — boost will not write over it")
        assert ei.value.hint == ("upgrade boost with `boost self-update`; this "
                                 "boost would drop what v4 records")
        assert paths.lockfile_path().read_bytes() == raw
        assert list(paths.lock_history_dir().iterdir()) == []  # refused first

    def test_pin_and_tag_refuse_it(self, sandbox):
        raw = _put({"version": 4, "skills": {"a": {"tags": []}}})
        with pytest.raises(BoostError):
            lockfile.update_skill("a", lambda r: r.update(pinned=True))
        with pytest.raises(BoostError):
            lockfile.set_skill("b", {})
        assert paths.lockfile_path().read_bytes() == raw

    def test_it_is_still_read_as_it_is(self, sandbox):
        _put({"version": 4, "skills": {"a": {"tap": "t"}}})
        assert lockfile.installed() == {"a": {"tap": "t"}}
        assert _backups() == []

    def test_the_remedy_is_an_upgrade_whatever_the_history(self, sandbox):
        lockfile.set_skill("a", {})
        lockfile.set_skill("b", {})
        assert lockfile.has_history()
        _put({"version": 7})
        integ = lockfile.check()
        assert integ == (False, "schema", 7)
        assert lockfile.remedy(integ) == "upgrade boost with `boost self-update`"

    def test_a_non_integer_schema_is_not_newer(self, sandbox):
        _put({"version": "4"})
        integ = lockfile.check()
        assert lockfile.newer(integ) is False
        assert lockfile.remedy(integ) == REBUILD
        with pytest.raises(BoostError) as ei:
            lockfile.write({})
        assert ei.value.message == ("lock file is schema v4, not v3 — boost "
                                    "will not write over it")
        assert ei.value.hint.startswith("`boost sync --rebuild-lock` sets it")

    def test_an_older_schema_still_migrates(self, sandbox):
        _put({"version": 2, "skills": {"a": {}}})
        lockfile.set_skill("b", {})
        assert json.loads(paths.lockfile_path().read_text(
            encoding="utf-8"))["version"] == 3


class TestRemedy:
    def test_without_history_it_is_the_rebuild(self, sandbox):
        _put("{oops")
        assert lockfile.has_history() is False
        assert lockfile.remedy(lockfile.check()) == REBUILD

    def test_with_history_it_is_replay(self, sandbox):
        lockfile.set_skill("a", {})
        lockfile.set_skill("b", {})
        _put("{oops")
        assert lockfile.has_history() is True
        assert lockfile.remedy(lockfile.check()) == (
            "restore it with `boost replay`")

    def test_an_unreadable_snapshot_is_no_history(self, sandbox):
        d = paths.lock_history_dir()
        d.mkdir(parents=True)
        (d / "lock-20260101T000000Z.json").write_text("{x", encoding="utf-8")
        assert lockfile.has_history() is False


class TestShape:
    @pytest.mark.parametrize("raw", [
        {"version": 3, "rules": []},
        {"version": 3, "skills": {"tdd": "oops"}},
        {"skills": {"a": {}}, "workflows": {"w": 1}}])
    def test_read_hands_on_a_skeleton_and_keeps_the_bytes(self, sandbox,
                                                          capsys, raw):
        data = _put(raw)
        lock = lockfile.read()
        assert (lock["skills"], lock["rules"], lock["workflows"]) == ({}, {}, {})
        assert lock["version"] == 3
        assert lockfile.corrupt_backup().read_bytes() == data
        assert "is corrupt" in capsys.readouterr().err

    def test_every_accessor_survives_it(self, sandbox):
        _put({"version": 3, "skills": {"tdd": "oops"}, "rules": []})
        assert lockfile.installed() == {}
        assert lockfile.installed_rules() == {}
        assert lockfile.find_any("tdd") is None
        assert lockfile.get_skill("tdd") is None

    def test_write_refuses_it(self, sandbox):
        raw = _put({"version": 3, "rules": []})
        with pytest.raises(BoostError) as ei:
            lockfile.set_skill("a", {})
        assert ei.value.message == ("lock file is corrupt — boost will not "
                                    "write over it")
        assert paths.lockfile_path().read_bytes() == raw

    def test_a_newer_schema_with_another_shape_is_not_backed_up(self, sandbox):
        _put({"version": 4, "skills": []})
        assert lockfile.read()["skills"] == {}
        assert _backups() == []

    def test_shape_error_names_the_first_bad_section(self):
        assert lockfile.shape_error({"skills": {}, "rules": []}) == (
            "'rules' is a list, not an object")
        assert lockfile.shape_error({"skills": {"a": "x"}}) == (
            "'skills' entry 'a' is a str, not an object")
        assert lockfile.shape_error({"skills": {"a": {}}, "extra": []}) is None


class TestBackups:
    def test_two_different_corruptions_keep_both(self, sandbox):
        first = _put('{"skills": {"cowboy-coding": {}}, trunc')
        lockfile.read()
        second = _put('{"skills": {')
        lockfile.read()
        assert _backups() == [".skill-lock.json.corrupt",
                              ".skill-lock.json.corrupt.2"]
        old, new = lockfile.corrupt_backups()
        assert (old.read_bytes(), new.read_bytes()) == (first, second)
        assert lockfile.corrupt_backup() == new

    def test_the_same_bytes_are_kept_once(self, sandbox):
        _put("{same")
        for _ in range(3):
            lockfile.read()
            lockfile.keep_copy()
        assert _backups() == [".skill-lock.json.corrupt"]

    def test_the_warning_names_the_backup_holding_the_record(self, sandbox,
                                                             capsys):
        _put("{one")
        lockfile.read()
        lockfile._WARNED_CORRUPT = False
        _put("{two")
        lockfile.read()
        err = " ".join(capsys.readouterr().err.split())
        assert err.count("is corrupt") == 2
        assert err.endswith("the newest record is only in "
                            "~/.agents/skills/.skill-lock.json.corrupt.2")

    def test_a_returning_state_names_its_own_backup(self, sandbox):
        a = _put("{a")
        lockfile.keep_copy()
        _put("{b")
        lockfile.keep_copy()
        _put("{a")
        assert lockfile.keep_copy().read_bytes() == a
        assert lockfile.corrupt_backup().name == ".skill-lock.json.corrupt"
        assert len(_backups()) == 2

    def test_the_next_name_is_one_past_the_highest(self, sandbox):
        _put("{x")
        d = paths.lockfile_path().parent
        (d / ".skill-lock.json.corrupt").write_text("a", encoding="utf-8")
        (d / ".skill-lock.json.corrupt.5").write_text("b", encoding="utf-8")
        (d / ".skill-lock.json.corrupted").write_text("c", encoding="utf-8")
        (d / ".skill-lock.json.corrupt.x").write_text("d", encoding="utf-8")
        assert lockfile.keep_copy().name == ".skill-lock.json.corrupt.6"
        assert _backups() == [".skill-lock.json.corrupt",
                              ".skill-lock.json.corrupt.5",
                              ".skill-lock.json.corrupt.6"]

    def test_a_non_ascii_digit_suffix_is_not_a_backup(self, sandbox):
        # "²".isdigit() is True and int("²") raises: one stray name crashed
        # every reader of a corrupt lock.
        _put("{x")
        d = paths.lockfile_path().parent
        (d / ".skill-lock.json.corrupt.²").write_text("a", encoding="utf-8")
        (d / ".skill-lock.json.corrupt.٣").write_text("b", encoding="utf-8")
        assert lockfile.corrupt_backups() == []
        assert lockfile.keep_copy().name == ".skill-lock.json.corrupt"

    def test_with_no_backup_it_names_where_the_first_goes(self, sandbox):
        _put("{x")
        assert lockfile.corrupt_backups() == []
        assert lockfile.corrupt_backup() == paths.lockfile_path().with_name(
            ".skill-lock.json.corrupt")

    def test_with_a_sound_lock_it_names_the_newest(self, sandbox):
        _put("{x")
        lockfile.keep_copy()
        _put("{y")
        lockfile.keep_copy()
        _put({"version": 3})
        assert lockfile.corrupt_backup().name == ".skill-lock.json.corrupt.2"

    def test_restore_keeps_a_new_state_beside_the_old(self, sandbox):
        lockfile.set_skill("a", {})
        lockfile.set_skill("b", {})
        [hid] = [h["id"] for h in lockfile.history_list()]
        first = _put("{first")
        lockfile.read()
        second = _put("{second")
        lockfile.restore(hid)
        assert [b.read_bytes() for b in lockfile.corrupt_backups()] == [
            first, second]
        assert lockfile.check().ok

    def test_unrestored_corrupt_reads_the_newest(self, sandbox):
        assert lockfile.unrestored_corrupt() is None
        _put("{x")
        lockfile.keep_copy()
        _put("{y")
        newest = lockfile.keep_copy()
        assert lockfile.unrestored_corrupt() == newest


class TestRefusalNamesTheRightBackup:
    def test_a_new_state_is_kept_before_it_is_named(self, sandbox):
        _put("{first")
        lockfile.keep_copy()
        second = _put("{second")
        # No read() first: install calls refuse_corrupt before anything else.
        with pytest.raises(BoostError) as ei:
            lockfile.refuse_corrupt()
        assert ei.value.hint.endswith(
            "the newest record is only in "
            "~/.agents/skills/.skill-lock.json.corrupt.2")
        assert lockfile.corrupt_backups()[-1].read_bytes() == second


class TestSetAside:
    def test_a_corrupt_lock_is_kept_and_removed(self, sandbox):
        raw = _put("{oops")
        backup = lockfile.set_aside()
        assert backup.read_bytes() == raw
        assert not paths.lockfile_path().exists()
        assert lockfile.check() == (False, "missing", None)

    def test_a_malformed_one_too(self, sandbox):
        raw = _put({"version": 3, "rules": []})
        assert lockfile.set_aside().read_bytes() == raw
        assert not paths.lockfile_path().exists()

    @pytest.mark.parametrize("raw", [{"version": 3}, {"version": 2}])
    def test_a_readable_lock_is_refused(self, sandbox, raw):
        data = _put(raw)
        with pytest.raises(BoostError) as ei:
            lockfile.set_aside()
        assert ei.value.message == ("the lock file is readable — there is "
                                    "nothing to rebuild")
        assert ei.value.hint == "run `boost sync`"
        assert paths.lockfile_path().read_bytes() == data

    def test_a_missing_lock_is_refused(self, sandbox):
        with pytest.raises(BoostError, match="nothing to rebuild"):
            lockfile.set_aside()

    def test_a_newer_lock_is_refused(self, sandbox):
        data = _put({"version": 4})
        with pytest.raises(BoostError) as ei:
            lockfile.set_aside()
        assert ei.value.message == ("the lock file is schema v4, newer than "
                                    "this boost's v3 — boost will not set it "
                                    "aside")
        assert ei.value.hint == "upgrade boost with `boost self-update`"
        assert paths.lockfile_path().read_bytes() == data
        assert _backups() == []


class TestCli:
    def test_pin_and_tag_over_a_newer_lock_exit_1_and_leave_it(self, boost,
                                                               installed):
        p = paths.lockfile_path()
        data = json.loads(p.read_text(encoding="utf-8"))
        p.write_text(json.dumps(data | {"version": 4}), encoding="utf-8")
        raw = p.read_bytes()
        for argv in (("pin", installed), ("tag", installed, "+x")):
            r = boost(*argv, expect=1)
            assert "newer than this boost's v3" in r.err
            assert "boost self-update" in r.err
        assert p.read_bytes() == raw

    def test_doctor_names_the_upgrade(self, boost, installed):
        p = paths.lockfile_path()
        data = json.loads(p.read_text(encoding="utf-8"))
        p.write_text(json.dumps(data | {"version": 4}), encoding="utf-8")
        r = boost("doctor", expect=1)
        assert ("lock file is schema v4, newer than this boost's v3 — upgrade "
                "boost with `boost self-update`") in " ".join(r.out.split())
        assert "replay" not in r.out

    @pytest.mark.parametrize("mangle", [
        lambda d: d | {"rules": []},
        lambda d: d | {"skills": d["skills"] | {"brainstorming": "oops"}}])
    def test_a_malformed_lock_is_a_fault_not_a_crash(self, boost, installed,
                                                     mangle):
        p = paths.lockfile_path()
        p.write_text(json.dumps(mangle(json.loads(p.read_text(
            encoding="utf-8")))), encoding="utf-8")
        r = boost("doctor", expect=1)
        assert ("lock file is corrupt — %s" % REBUILD) in " ".join(r.out.split())
        boost("list")
        r = boost("sync", expect=1)
        assert "Traceback" not in r.out + r.err
        # Each of these exited 70 on an AttributeError before the fix.
        for argv in (("heal",), ("outdated",), ("update",)):
            r = boost(*argv, expect=None)
            assert r.rc in (0, 1), (argv, r.rc, r.err)
            assert "Traceback" not in r.out + r.err

    def test_rebuild_lock_re_records_the_store(self, boost, installed):
        p = paths.lockfile_path()
        raw = p.read_bytes()[:-40]
        p.write_bytes(raw)
        r = boost("sync", "--rebuild-lock")
        assert ("set the unreadable lock file aside — its bytes are in "
                "~/.agents/skills/.skill-lock.json.corrupt; re-recording the "
                "store") in " ".join(r.out.split())
        assert "re-recorded brainstorming" in r.out
        assert lockfile.check().ok
        assert set(lockfile.installed()) == {"brainstorming"}
        assert lockfile.corrupt_backup().read_bytes() == raw

    def test_rebuild_lock_refuses_diff(self, boost, installed):
        r = boost("sync", "--rebuild-lock", "--diff", expect=2)
        assert "--rebuild-lock replaces the lock file; drop --diff" in r.err

    def test_rebuild_lock_over_a_sound_lock_exits_1(self, boost, installed):
        r = boost("sync", "--rebuild-lock", expect=1)
        assert "nothing to rebuild" in r.err
        assert lockfile.check().ok


class TestRollback:
    def test_an_unknown_non_integer_schema_is_restored_not_refused(self, boost,
                                                                  tapped):
        boost("install", "brainstorming")
        boost("install", "tdd-workflow")        # snapshots {brainstorming}
        hid = lockfile.history_list()[-1]["id"]
        raw = _put({"version": "3", "skills": {}})
        r = boost("replay", "rollback", hid, "-y")
        assert "Error" not in r.err
        assert lockfile.check().ok
        assert set(lockfile.installed()) == {"brainstorming"}
        assert lockfile.corrupt_backup().read_bytes() == raw

    def test_a_newer_schema_is_not_rolled_back(self, boost, tapped):
        boost("install", "brainstorming")
        boost("install", "tdd-workflow")
        hid = lockfile.history_list()[-1]["id"]
        raw = _put({"version": 4, "skills": {}})
        r = boost("replay", "rollback", hid, "-y", expect=1)
        assert "boost self-update" in r.err
        assert paths.lockfile_path().read_bytes() == raw
