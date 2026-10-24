# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Same-second history ids order by their names, whatever the mtimes say.

Every history writer names a file by a second-resolution stamp and gives a
same-second successor ``-2``, ``-3``, ... . Sorting on ``(mtime, name)`` broke
exactly there: on a 1-second-resolution filesystem those entries tie on mtime,
and by name ``X-2.json`` sorts before ``X.json`` and ``X-10`` before ``X-2`` —
so `replay` showed the older lock as newest and prune deleted the newer one.
"""
from __future__ import annotations

import json
import os

from boost_cli.commands import pkg
from boost_cli.core import claude_settings, lockfile, paths, util

_T = 1_700_000_000          # one instant every file is stamped with


def _tie(*files):
    for f in files:
        os.utime(f, (_T, _T))


def _write(d, names, body="{}"):
    d.mkdir(parents=True, exist_ok=True)
    out = []
    for n in names:
        (d / n).write_text(body, encoding="utf-8")
        out.append(d / n)
    _tie(*out)
    return out


class TestHistoryKey:
    def test_base_then_serials_numerically(self, tmp_path):
        files = _write(tmp_path, ["lock-20261024T060813Z-10.json",
                                  "lock-20261024T060813Z.json",
                                  "lock-20261024T060813Z-2.json"])
        assert [p.name for p in util.sorted_history(files)] == [
            "lock-20261024T060813Z.json",
            "lock-20261024T060813Z-2.json",
            "lock-20261024T060813Z-10.json"]

    def test_newest_first_reverses(self, tmp_path):
        files = _write(tmp_path, ["snap-20261024-060839.tar.gz",
                                  "snap-20261024-060839-2.tar.gz"])
        assert [p.name for p in util.sorted_history(files, newest_first=True)] \
            == ["snap-20261024-060839-2.tar.gz", "snap-20261024-060839.tar.gz"]

    def test_stamp_outranks_mtime(self, tmp_path):
        # An earlier stamp with a later mtime (a clock stepped back, or a
        # copy that reset mtimes) is still the older entry.
        old, new = _write(tmp_path, ["lock-20260101T000000Z.json",
                                     "lock-20260102T000000Z.json"])
        os.utime(old, (_T + 99, _T + 99))
        assert util.sorted_history([new, old]) == [old, new]

    def test_parsed_key_values(self, tmp_path):
        (f,) = _write(tmp_path, ["gemini-project-20261024T060813Z-3.json"])
        assert util.history_key(f) == ("20261024060813", 3, _T * 10**9, f.name)
        (s,) = _write(tmp_path, ["snap-20261024-060839.tar.gz"])
        assert util.history_key(s) == ("20261024060839", 1, _T * 10**9, s.name)

    def test_unstamped_names_sort_first_by_mtime_then_name(self, tmp_path):
        b, a, real = _write(tmp_path, ["lock-b.json", "lock-a.json",
                                       "lock-20260101T000000Z.json"])
        os.utime(b, (_T - 5, _T - 5))
        assert util.history_key(a) == ("", 0, _T * 10**9, "lock-a.json")
        assert util.sorted_history([real, a, b]) == [b, a, real]

    def test_vanished_file_still_gets_a_key(self, tmp_path):
        gone = tmp_path / "lock-20260101T000000Z-4.json"
        assert util.history_key(gone) == ("20260101000000", 4, 0, gone.name)


class TestLockHistory:
    NAMES = ("lock-20261024T060813Z.json", "lock-20261024T060813Z-2.json",
             "lock-20261024T060813Z-10.json")

    def test_history_list_is_creation_order(self, sandbox):
        _write(paths.lock_history_dir(), reversed(self.NAMES))
        assert [h["id"] for h in lockfile.history_list()] == [
            "20261024T060813Z", "20261024T060813Z-2", "20261024T060813Z-10"]

    def test_prune_keeps_the_newest(self, sandbox, monkeypatch):
        monkeypatch.setattr(lockfile, "HISTORY_KEEP", 2)
        _write(paths.lock_history_dir(), self.NAMES)
        lockfile._prune_history()
        left = {p.name for p in paths.lock_history_dir().glob("lock-*.json")}
        assert left == {"lock-20261024T060813Z-2.json",
                        "lock-20261024T060813Z-10.json"}


class TestSettingsHistory:
    def test_prune_keeps_the_newest(self, sandbox, monkeypatch):
        monkeypatch.setattr(claude_settings, "HISTORY_KEEP", 2)
        d = claude_settings._history_dir()
        _write(d, ["user-20261024T060813Z.json", "user-20261024T060813Z-2.json",
                   "user-20261024T060813Z-10.json"])
        claude_settings._prune_history()
        assert sorted(p.name for p in d.glob("*.json")) == [
            "user-20261024T060813Z-10.json", "user-20261024T060813Z-2.json"]


class TestSnapshotList:
    def test_newest_first_with_tied_mtimes(self, sandbox, capsys):
        paths.ensure_dirs()
        _write(paths.snapshots_dir(), ["snap-20261024-060839.tar.gz",
                                       "snap-20261024-060839-10.tar.gz",
                                       "snap-20261024-060839-2.tar.gz"], body="x")
        assert pkg._snapshot_list(True) == 0
        assert [s["id"] for s in json.loads(capsys.readouterr().out)] == [
            "snap-20261024-060839-10", "snap-20261024-060839-2",
            "snap-20261024-060839"]


class TestDeepClean:
    def test_names_the_older_same_second_snapshot(self, sandbox, capsys):
        # `clean --deep` keeps the newest 50 by the same order prune uses;
        # by bare name it called the newer `-2` of a pair "old".
        from boost_cli.commands import configuration
        names = ["lock-20250101T000000Z.json", "lock-20250101T000000Z-2.json"]
        names += ["lock-20260101T0000%02dZ.json" % i for i in range(49)]
        _write(paths.lock_history_dir(), names)
        assert configuration.cmd_clean(["--deep", "--dry-run", "--json"]) == 0
        old = [i["path"] for i in json.loads(capsys.readouterr().out)["items"]
               if i["kind"] == "old lock history"]
        assert [os.path.basename(p) for p in old] == [names[0]]
