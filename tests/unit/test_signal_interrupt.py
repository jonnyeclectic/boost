# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""SIGTERM and SIGHUP run the same rollbacks as Ctrl-C (core.interrupt, cli.main).

Measured before the fix: SIGTERM during an install's lock write exited -15
and left the store copy and its four links with no lock row, which the rerun
refused and `boost sync` adopted as a `local` skill; SIGINT at the same point
rolled back cleanly.
"""
from __future__ import annotations

import itertools
import os
import shutil
import signal
import sys
import time

import pytest

from boost_cli import cli
from boost_cli.core import catalog, interrupt, lockfile, registry, store

_SEQ = itertools.count()

posix_signals = pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX signal delivery")


@pytest.fixture()
def tap(sandbox, fixture_tap_src, tmp_path):
    src = tmp_path / ("signal-interrupt-%d" % next(_SEQ))
    shutil.copytree(fixture_tap_src, src, symlinks=True)
    t = registry.add(str(src))
    catalog.rebuild_tap(t)
    return t


# --------------------------------------------------------------------------
# core.interrupt
# --------------------------------------------------------------------------

class TestTerminated:
    def test_is_a_keyboard_interrupt(self):
        assert issubclass(interrupt.Terminated, KeyboardInterrupt)

    def test_exit_codes(self):
        assert interrupt.exit_code(KeyboardInterrupt()) == 130
        assert interrupt.exit_code(interrupt.Terminated(15)) == 143
        assert interrupt.exit_code(interrupt.Terminated(1)) == 129
        assert interrupt.Terminated(15).signum == 15

    def test_handled_signals(self):
        got = interrupt.handled_signals()
        assert got[0] == signal.SIGTERM
        if hasattr(signal, "SIGHUP"):
            assert got == [signal.SIGTERM, signal.SIGHUP]
        else:
            assert got == [signal.SIGTERM]


@posix_signals
class TestRaisingOnTermination:
    def test_installs_then_restores_the_default(self):
        assert signal.getsignal(signal.SIGTERM) is signal.SIG_DFL
        with interrupt.raising_on_termination() as took:
            assert took == [signal.SIGTERM, signal.SIGHUP]
            assert signal.getsignal(signal.SIGTERM) is interrupt._raise
            with pytest.raises(interrupt.Terminated) as caught:
                os.kill(os.getpid(), signal.SIGTERM)
                time.sleep(1)  # the handler runs at the next bytecode
            assert caught.value.signum == signal.SIGTERM
        assert signal.getsignal(signal.SIGTERM) is signal.SIG_DFL
        assert signal.getsignal(signal.SIGHUP) is signal.SIG_DFL

    def test_leaves_an_ignored_signal_ignored(self):
        old = signal.signal(signal.SIGHUP, signal.SIG_IGN)
        try:
            with interrupt.raising_on_termination() as took:
                assert took == [signal.SIGTERM]
                assert signal.getsignal(signal.SIGHUP) is signal.SIG_IGN
            assert signal.getsignal(signal.SIGHUP) is signal.SIG_IGN
        finally:
            signal.signal(signal.SIGHUP, old)

    def test_off_the_main_thread_installs_nothing(self):
        import threading
        seen: list[list[int]] = []

        def run():
            with interrupt.raising_on_termination() as took:
                seen.append(took)
        t = threading.Thread(target=run)
        t.start()
        t.join()
        assert seen == [[]]
        assert signal.getsignal(signal.SIGTERM) is signal.SIG_DFL


@posix_signals
class TestCliUnderSignal:
    def _kill_at_lock_write(self, monkeypatch, sig):
        real = lockfile.write

        def write(lock):
            os.kill(os.getpid(), sig)
            time.sleep(1)  # interrupted here, before the real write
            return real(lock)
        monkeypatch.setattr(lockfile, "write", write)

    # Windows has no SIGHUP, and the parameter list is built at collection,
    # before any skip can apply, so naming it unconditionally fails the module.
    @pytest.mark.parametrize(("sig", "rc"), [
        (signal.SIGTERM, 143),
        *([(signal.SIGHUP, 129)] if hasattr(signal, "SIGHUP") else [])])
    def test_install_rolls_back_and_exits_128_plus_signum(
            self, tap, monkeypatch, sig, rc):
        self._kill_at_lock_write(monkeypatch, sig)
        assert cli.main(["install", "tdd-workflow"]) == rc
        assert not os.path.lexists(store.skill_store_dir("tdd-workflow"))
        assert store.linked_agents("tdd-workflow") == []
        assert lockfile.get_skill("tdd-workflow") is None
        assert signal.getsignal(signal.SIGTERM) is signal.SIG_DFL
        assert signal.getsignal(signal.SIGHUP) is signal.SIG_DFL

    def test_an_ignored_sigterm_stays_ignored(self, tap, monkeypatch):
        self._kill_at_lock_write(monkeypatch, signal.SIGTERM)
        old = signal.signal(signal.SIGTERM, signal.SIG_IGN)
        try:
            assert cli.main(["install", "tdd-workflow"]) == 0
            assert signal.getsignal(signal.SIGTERM) is signal.SIG_IGN
        finally:
            signal.signal(signal.SIGTERM, old)
        assert lockfile.get_skill("tdd-workflow") is not None

    def test_ctrl_c_still_exits_130(self, tap, monkeypatch, capsys):
        def write(_lock):
            raise KeyboardInterrupt
        monkeypatch.setattr(lockfile, "write", write)
        assert cli.main(["install", "tdd-workflow"]) == 130
        assert capsys.readouterr().out.endswith("\n")
