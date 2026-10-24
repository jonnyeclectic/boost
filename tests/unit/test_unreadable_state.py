# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A state file boost cannot *read* is not a corrupt one.

Measured before this fix, with the lock at mode 000: `boost list` called it
"corrupt" and advised `boost replay rollback`, `boost install` named a
`.skill-lock.json.corrupt` that was never written (the copy needs a read
too), and the rollback replaced the intact 5712-byte lock with the 3485-byte
snapshot, losing the newest record. With a directory on the lock's name the
same rollback crashed at exit 70. A config.json at mode 000 read as defaults
with no taps, and the next `boost tap` — doctor's own remedy — moved the
intact file aside and wrote one holding only that tap.

The bytes of an unreadable file may be fine, so every surface names the
permission (or the directory to move aside) and every writer refuses.
"""
from __future__ import annotations

import errno
import json
import os
import shutil
import sys

import pytest

from boost_cli.core import catalog, config, jsonstate, lockfile, mcp, paths, registry
from boost_cli.errors import BoostError

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="chmod 000 does not stop root, and Windows ignores the mode")

LOCK = "~/.agents/skills/.skill-lock.json"
CHMOD_LOCK = "make it readable with `chmod u+r %s`" % LOCK
CFG = "~/.boost/config.json"


def _flat(text: str) -> str:
    return " ".join(text.split())


@pytest.fixture()
def unreadable(sandbox):
    """``unreadable(path)`` sets ``path`` to mode 000; restored at teardown."""
    made = []

    def make(p):
        p.chmod(0)
        made.append(p)
        return p

    yield make
    for p in made:
        if p.exists():
            p.chmod(0o600)


@pytest.fixture()
def tap(sandbox, fixture_tap_src, tmp_path):
    src = tmp_path / "unreadable-state-tap"
    shutil.copytree(fixture_tap_src, src, symlinks=True)
    t = registry.add(str(src))
    catalog.rebuild_tap(t)
    return t


def _two_records():
    lockfile.set_skill("a", {"version": "1"})
    lockfile.set_skill("b", {"version": "1"})
    p = paths.lockfile_path()
    return p, p.read_bytes()


class TestJsonstate:
    def test_a_read_failure_is_unreadable_not_corrupt(self, sandbox,
                                                      unreadable):
        p = paths.state_dir() / "thing.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{}", encoding="utf-8")
        unreadable(p)
        data, err = jsonstate.read_object(p)
        assert data is None
        assert isinstance(err, jsonstate.Unreadable)
        assert err.path == p
        assert err.errno == errno.EACCES
        assert err.reason == "Permission denied"
        assert err == "%s: cannot be read (Permission denied)" % p
        assert jsonstate.read_remedy(err) == (
            "make it readable with `chmod u+r %s`" % p)
        assert jsonstate.is_corrupt(p)       # still not "nothing here"
        _, lerr = jsonstate.read_list(p)
        assert isinstance(lerr, jsonstate.Unreadable)

    def test_a_directory_on_the_name_is_moved_aside(self, sandbox):
        p = paths.state_dir() / "thing.json"
        p.mkdir(parents=True)
        _, err = jsonstate.read_object(p)
        assert isinstance(err, jsonstate.Unreadable)
        assert jsonstate.read_remedy(err, paths.tilde) == (
            "move the directory ~/.boost/state/thing.json aside (it is not "
            "a file)")

    def test_a_parse_failure_is_not_unreadable(self, sandbox):
        p = paths.state_dir() / "thing.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{nope", encoding="utf-8")
        _, err = jsonstate.read_object(p)
        assert err is not None
        assert not isinstance(err, jsonstate.Unreadable)

    def test_save_refuses_over_an_unreadable_file(self, sandbox, unreadable):
        p = paths.state_dir() / "thing.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('{"keep": 1}', encoding="utf-8")
        unreadable(p)
        with pytest.raises(BoostError) as ei:
            jsonstate.save(p, "{}", corrupt=True, show=paths.tilde)
        assert str(ei.value) == (
            "could not read ~/.boost/state/thing.json (Permission denied) — "
            "boost will not write over a file it cannot read")
        assert ei.value.hint == ("make it readable with `chmod u+r "
                                 "~/.boost/state/thing.json`, then re-run")
        p.chmod(0o600)
        assert p.read_text(encoding="utf-8") == '{"keep": 1}'
        assert not p.with_name("thing.json.corrupt").exists()


class TestUnreadableLock:
    def test_read_warns_with_the_chmod_and_keeps_no_backup(self, sandbox,
                                                           unreadable, capsys):
        p, _raw = _two_records()
        unreadable(p)
        assert lockfile.read()["skills"] == {}
        lockfile.read()
        err = _flat(capsys.readouterr().err)
        assert ("the lock file %s cannot be read (Permission denied), so "
                "boost sees nothing installed — %s; boost will not write the "
                "lock until it can read it" % (LOCK, CHMOD_LOCK)) in err
        assert err.count("cannot be read") == 1          # once per process
        assert "corrupt" not in err and "replay" not in err
        assert lockfile.corrupt_backups() == []
        assert lockfile._WARNED_CORRUPT is False

    def test_check_fault_and_remedy(self, sandbox, unreadable):
        p, _raw = _two_records()
        unreadable(p)
        integ = lockfile.check()
        assert integ.ok is False
        assert integ.problem == "unreadable"
        assert isinstance(integ.detail, jsonstate.Unreadable)
        assert integ.version is integ.detail
        assert lockfile.Integrity(False, "schema", 4).detail is None
        assert lockfile.fault(integ) == "cannot be read (Permission denied)"
        assert lockfile.remedy(integ) == CHMOD_LOCK

    def test_fault_and_remedy_without_detail(self):
        integ = lockfile.Integrity(False, "unreadable")
        assert lockfile.fault(integ) == "cannot be read"
        assert lockfile.remedy(integ) == "make it readable"

    def test_a_write_refuses_and_names_no_backup(self, sandbox, unreadable):
        p, raw = _two_records()
        unreadable(p)
        with pytest.raises(BoostError) as ei:
            lockfile.set_skill("c", {"version": "1"})
        assert str(ei.value) == (
            "lock file cannot be read (Permission denied) — boost will not "
            "write over a lock it cannot read")
        assert ei.value.hint == CHMOD_LOCK + ", then re-run"
        assert lockfile.corrupt_backups() == []
        p.chmod(0o600)
        assert p.read_bytes() == raw

    def test_restore_refuses_and_leaves_the_lock(self, sandbox, unreadable):
        p, raw = _two_records()
        [hid] = [h["id"] for h in lockfile.history_list()]
        unreadable(p)
        with pytest.raises(BoostError) as ei:
            lockfile.restore(hid)
        assert str(ei.value) == (
            "the lock file cannot be read (Permission denied) — boost will "
            "not replace a lock it cannot read, which may be intact")
        assert ei.value.hint == CHMOD_LOCK + ", then re-run"
        assert lockfile.corrupt_backups() == []
        p.chmod(0o600)
        assert p.read_bytes() == raw

    def test_restore_refuses_a_directory_on_the_name(self, sandbox):
        p, _raw = _two_records()
        [hid] = [h["id"] for h in lockfile.history_list()]
        p.unlink()
        p.mkdir()
        with pytest.raises(BoostError) as ei:
            lockfile.restore(hid)
        assert ei.value.hint == ("move the directory %s aside (it is not a "
                                 "file), then re-run" % LOCK)
        assert p.is_dir()

    def test_set_aside_refuses(self, sandbox, unreadable):
        p, raw = _two_records()
        unreadable(p)
        with pytest.raises(BoostError) as ei:
            lockfile.set_aside()
        assert str(ei.value) == ("the lock file cannot be read (Permission "
                                 "denied) — boost will not set it aside")
        assert ei.value.hint == CHMOD_LOCK + ", then re-run"
        p.chmod(0o600)
        assert p.read_bytes() == raw

    def test_cli_rollback_refuses_and_doctor_names_the_chmod(
            self, tap, boost, unreadable):
        boost("install", "brainstorming")
        boost("install", "commit-messages")
        boost("install", "jira-integration")
        p = paths.lockfile_path()
        raw = p.read_bytes()
        newest = lockfile.history_list()[-1]["id"]
        unreadable(p)

        res = boost("list")
        assert CHMOD_LOCK in _flat(res.err)
        assert "replay" not in res.err

        res = boost("install", "tdd-workflow", expect=1)
        assert ".corrupt" not in res.err
        assert CHMOD_LOCK in _flat(res.err)

        res = boost("replay", "rollback", newest, expect=1)
        assert "will not replace a lock it cannot read" in _flat(res.err)
        assert "restored" not in res.out

        res = boost("doctor", expect=None)
        assert ("lock file cannot be read (Permission denied) — %s"
                % CHMOD_LOCK) in _flat(res.out)

        res = boost("verify", expect=1)
        assert ("lock file cannot be read (Permission denied) — %s"
                % CHMOD_LOCK) in _flat(res.err)

        assert lockfile.corrupt_backups() == []
        p.chmod(0o600)
        assert p.read_bytes() == raw


class TestCorruptLockBackupRefused:
    """A genuinely corrupt lock whose copy fails names no phantom backup."""

    def _corrupt_and_block(self, monkeypatch):
        p, _ = _two_records()
        p.write_text("{nope", encoding="utf-8")

        def refuse(_p=None):
            raise PermissionError(errno.EACCES, "Permission denied")

        monkeypatch.setattr(lockfile, "keep_copy", refuse)
        return p

    def test_write_refusal_names_no_backup(self, sandbox, monkeypatch):
        self._corrupt_and_block(monkeypatch)
        with pytest.raises(BoostError) as ei:
            lockfile.set_skill("c", {})
        assert str(ei.value) == ("lock file is corrupt — boost will not "
                                 "write over it")
        assert ei.value.hint == (
            "boost could not back it up (Permission denied), and the newest "
            "record is only in it — copy %s somewhere safe before changing "
            "it" % LOCK)

    def test_restore_refuses_without_a_backup(self, sandbox, monkeypatch):
        p = self._corrupt_and_block(monkeypatch)
        hid = lockfile.history_list()[-1]["id"]
        with pytest.raises(BoostError) as ei:
            lockfile.restore(hid)
        assert str(ei.value) == ("the lock file is corrupt — boost will not "
                                 "replace a lock it could not back up")
        assert p.read_text(encoding="utf-8") == "{nope"


class TestUnreadableConfig:
    def _config(self, sandbox):
        paths.ensure_dirs()
        p = paths.config_path()
        p.write_text(json.dumps({"taps": [{"name": "kept", "url": "x"}],
                                 "color": "never"}), encoding="utf-8")
        return p, p.read_bytes()

    def test_reads_warn_with_the_chmod(self, sandbox, unreadable, capsys):
        p, _raw = self._config(sandbox)
        unreadable(p)
        assert config.load()["taps"] == []
        err = _flat(capsys.readouterr().err)
        assert ("reading as empty for this command; boost will not write "
                "config.json until it can read it: make it readable with "
                "`chmod u+r %s`" % CFG) in err
        assert ".corrupt" not in err

    def test_config_set_refuses_and_keeps_the_file(self, sandbox, unreadable):
        p, raw = self._config(sandbox)
        unreadable(p)
        with pytest.raises(BoostError) as ei:
            config.mutate(lambda cfg: cfg.update(color="auto"))
        assert str(ei.value) == (
            "could not read %s (Permission denied) — boost will not write "
            "over a config it cannot read" % CFG)
        assert ei.value.hint == ("make it readable with `chmod u+r %s`, then "
                                 "re-run" % CFG)
        assert not p.with_name("config.json.corrupt").exists()
        p.chmod(0o600)
        assert p.read_bytes() == raw

    def test_save_refuses_too(self, sandbox, unreadable):
        p, _raw = self._config(sandbox)
        unreadable(p)
        with pytest.raises(BoostError):
            config.save({})
        assert not p.with_name("config.json.corrupt").exists()

    def test_tap_refuses_before_cloning(self, sandbox, unreadable,
                                        fixture_tap_src):
        p, raw = self._config(sandbox)
        unreadable(p)
        repos = paths.boost_home() / "repos"
        before = sorted(repos.iterdir()) if repos.exists() else []
        with pytest.raises(BoostError, match="cannot read"):
            registry.add(str(fixture_tap_src))
        with pytest.raises(BoostError, match="cannot read"):
            registry.add_many([str(fixture_tap_src)])
        after = sorted(repos.iterdir()) if repos.exists() else []
        assert after == before
        p.chmod(0o600)
        assert p.read_bytes() == raw

    def test_a_corrupt_config_is_still_moved_aside(self, sandbox):
        paths.ensure_dirs()
        p = paths.config_path()
        p.write_text("{nope", encoding="utf-8")
        config.save({"color": "auto"})
        assert p.with_name("config.json.corrupt").read_text(
            encoding="utf-8") == "{nope"

    def test_mcp_and_doctor_name_the_chmod(self, sandbox, unreadable, boost):
        p, _raw = self._config(sandbox)
        unreadable(p)
        err = config.check()
        assert isinstance(err, jsonstate.Unreadable)
        assert mcp.config_problem(err) == (
            "%s — boost is running on defaults, so the user's taps are not "
            "listed; ask the user to make it readable with `chmod u+r %s` "
            "(run `boost doctor` for details)" % (err, CFG))
        res = boost("doctor", expect=None)
        flat = _flat(res.out)
        assert ("boost is running on defaults, so no taps or settings are "
                "read; make it readable with `chmod u+r %s`. boost will not "
                "write config.json until it can read it" % CFG) in flat
        assert "config.json.corrupt" not in flat
        assert "re-add" not in flat
        res = boost("search", "brainstorming", expect=1)
        assert ("%s: cannot be read (Permission denied) — no taps are read, "
                "so nothing was searched" % p) in _flat(res.err)
        assert "tap --defaults" not in res.err
        assert "make it readable with `chmod u+r %s`" % CFG in _flat(res.err)
        res = boost("heal", expect=None)
        assert ("heal does not change permissions: boost is running on "
                "defaults until you make it readable with `chmod u+r %s`"
                % CFG) in _flat(res.out)


def test_snapshot_names_an_unreadable_archived_lock(sandbox, unreadable,
                                                    tmp_path):
    from boost_cli.core import snapshot
    root = tmp_path / "staged"
    root.mkdir()
    lock = root / snapshot.LOCK_NAME
    lock.write_text('{"version": 3, "skills": {}}', encoding="utf-8")
    unreadable(lock)
    why, integ = snapshot.lock_problem(root)
    assert why == "has a lock file boost cannot read"
    # The archived lock's own path, not the live one.
    assert lockfile.remedy(integ) == ("make it readable with `chmod u+r %s`"
                                      % paths.tilde(lock))


def test_clean_keeps_tap_caches_while_config_is_unreadable(
        sandbox, unreadable, boost):
    # An unreadable config lists no taps, so every tap cache read as stale.
    paths.ensure_dirs()
    p = paths.config_path()
    p.write_text(json.dumps({"taps": [{"name": "kept", "url": "x"}]}),
                 encoding="utf-8")
    cache = paths.cache_dir() / "kept.json"
    cache.write_text("{}", encoding="utf-8")
    unreadable(p)
    res = boost("clean", "-y", expect=0)
    assert cache.is_file()
    assert "left the tap caches alone: %s" % config.check() in _flat(res.err)
    assert "stale tap cache" not in res.out


def test_clean_still_sweeps_a_stale_cache_when_config_reads(sandbox, boost):
    paths.ensure_dirs()
    stale = paths.cache_dir() / "gone.json"
    stale.write_text("{}", encoding="utf-8")
    res = boost("clean", "-y", expect=0)
    assert not stale.exists()
    assert "left the tap caches alone" not in res.err
