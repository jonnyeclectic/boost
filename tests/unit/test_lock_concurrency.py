# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: concurrent boost processes must not lose each other's lock rows.

`set_skill` and friends were a bare read-modify-write of the whole lock file:
two processes overlapping each read the same lock, each added one row, and the
second write replaced the first. Measured: 39 parallel `boost pin` runs all
printed "pinned" and 8 pins were gone. Every mutation now runs under
`util.file_lock` on a sidecar, with the read taken inside the lock.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from boost_cli.core import lockfile, paths, util
from boost_cli.errors import BoostError

# The tree `boost_cli` is imported from, and every child's cwd. Under the
# mutation gate the child's import is mutmut's trampoline, which reads
# `[mutmut]` from the `setup.cfg` in the *current directory* only, so a child
# started in the sandbox dies with "Could not figure out where the code to
# mutate is" (see test_first_run_pointer.py).
ROOT = Path(lockfile.__file__).resolve().parents[2]


def _env() -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _spawn(code: str) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-c", textwrap.dedent(code)],
                            env=_env(), cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)


class TestConcurrentWriters:
    def test_parallel_set_skill_keeps_every_row(self, sandbox):
        n = 16
        # Each child waits on a shared start file so the writes overlap.
        go = sandbox / "go"
        code = """
            import os, sys, time
            from boost_cli.core import lockfile
            while not os.path.exists(%r):
                time.sleep(0.005)
            for i in range(3):
                lockfile.set_skill("s" + sys.argv[1] + "-" + str(i), {"version": "1.0.0"})
        """ % str(go)
        procs = [subprocess.Popen(
            [sys.executable, "-c", textwrap.dedent(code), "%02d" % i],
            env=_env(), cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for i in range(n)]
        go.write_text("", encoding="utf-8")
        for p in procs:
            _out, err = p.communicate(timeout=120)
            assert p.returncode == 0, err
        names = set(lockfile.installed())
        assert names == {"s%02d-%d" % (i, j) for i in range(n) for j in range(3)}

    def test_parallel_pin_keeps_every_pin(self, sandbox):
        n = 12
        for i in range(n):
            lockfile.set_skill("s%02d" % i, {"version": "1.0.0", "pinned": False})
        go = sandbox / "go"
        code = """
            import os, sys, time
            from boost_cli.core import lockfile
            while not os.path.exists(%r):
                time.sleep(0.005)
            name = "s" + sys.argv[1]
            def pin(lock):
                lock["skills"][name]["pinned"] = True
            lockfile.mutate(pin)
        """ % str(go)
        procs = [subprocess.Popen(
            [sys.executable, "-c", textwrap.dedent(code), "%02d" % i],
            env=_env(), cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for i in range(n)]
        go.write_text("", encoding="utf-8")
        for p in procs:
            _out, err = p.communicate(timeout=120)
            assert p.returncode == 0, err
        skills = lockfile.installed()
        assert sorted(k for k, v in skills.items() if v["pinned"]) == \
            ["s%02d" % i for i in range(n)]


class TestHeldElsewhere:
    def test_times_out_with_a_clear_error_and_writes_nothing(self, sandbox,
                                                              monkeypatch):
        lockfile.set_skill("a", {"version": "1.0.0"})
        before = paths.lockfile_path().read_bytes()
        holder = _spawn("""
            import sys, time
            from boost_cli.core import lockfile, util
            with util.file_lock(lockfile.guard_path()):
                print("held", flush=True)
                time.sleep(30)
        """)
        try:
            assert holder.stdout.readline().strip() == "held"
            monkeypatch.setattr(util, "FILE_LOCK_TIMEOUT", 0.2)
            with pytest.raises(BoostError) as ei:
                lockfile.set_skill("b", {"version": "1.0.0"})
        finally:
            holder.kill()
            holder.communicate()
        assert str(ei.value) == \
            "another boost process has held the lock file for over 0.2s"
        assert ei.value.hint == (
            "wait for the other boost command to finish, then retry "
            "(the lock is %s)" % paths.tilde(lockfile.guard_path()))
        assert paths.lockfile_path().read_bytes() == before

    def test_released_when_the_holder_is_killed(self, sandbox, monkeypatch):
        holder = _spawn("""
            import time
            from boost_cli.core import lockfile, util
            with util.file_lock(lockfile.guard_path()):
                print("held", flush=True)
                time.sleep(30)
        """)
        assert holder.stdout.readline().strip() == "held"
        holder.kill()
        holder.communicate()
        monkeypatch.setattr(util, "FILE_LOCK_TIMEOUT", 5.0)
        lockfile.set_skill("a", {"version": "1.0.0"})
        assert list(lockfile.installed()) == ["a"]
        assert lockfile.guard_path().exists()      # the sidecar is never deleted


class TestMutate:
    def test_returns_whether_it_wrote(self, sandbox):
        assert lockfile.mutate(lambda lock: False) is False
        assert not paths.lockfile_path().exists()
        assert lockfile.mutate(lambda lock: None) is True
        assert paths.lockfile_path().exists()

    def test_reads_inside_the_lock(self, sandbox):
        lockfile.set_skill("a", {"version": "1"})
        seen = []
        lockfile.mutate(lambda lock: seen.append(sorted(lock["skills"])))
        assert seen == [["a"]]

    def test_exception_writes_nothing_and_releases(self, sandbox):
        lockfile.set_skill("a", {"version": "1"})
        before = paths.lockfile_path().read_bytes()

        def boom(lock):
            lock["skills"]["b"] = {}
            raise KeyboardInterrupt
        with pytest.raises(KeyboardInterrupt):
            lockfile.mutate(boom)
        assert paths.lockfile_path().read_bytes() == before
        # Released: a second open of the sidecar takes it at once.
        with util.file_lock(lockfile.guard_path(), timeout=0):
            pass
        assert lockfile._depth == 0

    def test_nested_writes_do_not_deadlock(self, sandbox):
        # `write` takes the lock and `mutate` calls `write` under it, so the
        # lock must be re-entrant within one process.
        with lockfile.exclusive():
            assert lockfile._depth == 1
            lockfile.set_skill("a", {"version": "1"})
            assert lockfile._depth == 1
            lockfile.set_skill("b", {"version": "1"})
        assert sorted(lockfile.installed()) == ["a", "b"]
        assert lockfile._depth == 0

    def test_held_while_the_body_runs(self, sandbox):
        def probe(lock):
            with pytest.raises(BoostError), \
                    util.file_lock(lockfile.guard_path(), timeout=0):
                pass
        lockfile.mutate(probe)

    def test_remove_absent_does_not_write(self, sandbox):
        assert lockfile.remove_skill("nope") is False
        assert lockfile.remove_rule("nope") is False
        assert lockfile.remove_workflow("nope") is False
        assert not paths.lockfile_path().exists()

    def test_remove_present_writes(self, sandbox):
        lockfile.set_skill("a", {})
        lockfile.set_rule("r", {})
        lockfile.set_workflow("w", {})
        assert lockfile.remove_skill("a") is True
        assert lockfile.remove_rule("r") is True
        assert lockfile.remove_workflow("w") is True
        lock = lockfile.read()
        assert (lock["skills"], lock["rules"], lock["workflows"]) == ({}, {}, {})

    def test_guard_sits_beside_the_lock(self, sandbox):
        p = paths.lockfile_path()
        assert lockfile.guard_path() == p.with_name(".skill-lock.json.lock")


class TestFileLock:
    def test_strict_raises_when_the_sidecar_cannot_exist(self, tmp_path):
        blocker = tmp_path / "file"
        blocker.write_text("", encoding="utf-8")
        with pytest.raises(OSError), util.file_lock(blocker / "x.lock"):
            pass

    def test_lenient_runs_the_body_unlocked(self, tmp_path):
        blocker = tmp_path / "file"
        blocker.write_text("", encoding="utf-8")
        ran = []
        with util.file_lock(blocker / "x.lock", strict=False):
            ran.append(1)
        assert ran == [1]

    def test_creates_parent_and_waits_its_timeout(self, tmp_path):
        lock = tmp_path / "deep" / "x.lock"
        with util.file_lock(lock, what="the thing"):
            assert lock.exists()
            with pytest.raises(BoostError, match=r"^another boost process has "
                               r"held the thing for over 0s$"), \
                    util.file_lock(lock, timeout=0, what="the thing"):
                pass
        with util.file_lock(lock, timeout=0):
            pass
