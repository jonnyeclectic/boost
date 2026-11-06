# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""SIGTERM and SIGHUP as an interrupt, so boost's rollbacks run for them too.

Every multi-step write in boost (install, ``_copy_skill``, uninstall,
quarantine, import) undoes itself under ``except BaseException``. Python
turns only SIGINT into an exception, though: SIGTERM and SIGHUP kill the
process at their default disposition, and nothing in a ``finally`` or an
``except`` runs. So Ctrl-C rolled an install back cleanly while ``timeout``,
a cancelled CI job or a closed terminal left a store copy and its links with
no lock row, which the next install refused and ``boost sync`` adopted as a
local skill with no tap.

:class:`Terminated` subclasses ``KeyboardInterrupt`` so every existing
handler treats the two signals exactly as it treats Ctrl-C, with nothing
changed at any call site. Only the exit code differs: ``128 + signum``, the
shell's convention, rather than SIGINT's 130.
"""
from __future__ import annotations

import contextlib
import signal
from collections.abc import Iterator

#: The exit status of a run Ctrl-C stopped: 128 + SIGINT.
SIGINT_EXIT = 130


class Terminated(KeyboardInterrupt):
    """A SIGTERM or SIGHUP, raised where the process was when it arrived."""

    def __init__(self, signum: int):
        """Carry ``signum``, the signal that arrived."""
        super().__init__(signum)
        self.signum = signum

    @property
    def exit_code(self) -> int:
        """The shell's status for death by this signal: 128 + signum."""
        return 128 + self.signum


def exit_code(exc: KeyboardInterrupt) -> int:
    """The exit status for an interrupt: 143 for SIGTERM, 129 for SIGHUP,
    130 for Ctrl-C."""
    return exc.exit_code if isinstance(exc, Terminated) else SIGINT_EXIT


def handled_signals() -> list[int]:
    """The signals :func:`raising_on_termination` takes over on this platform.

    Windows has no SIGHUP, and its SIGTERM is never delivered by another
    process, so there it is SIGTERM alone and changes nothing in practice.
    """
    found: list[int] = [signal.SIGTERM]
    hup = getattr(signal, "SIGHUP", None)
    if hup is not None:
        found.append(hup)
    return found


def _raise(signum: int, _frame) -> None:
    """The handler: raise where the main thread is, so its rollbacks run."""
    raise Terminated(signum)


@contextlib.contextmanager
def raising_on_termination() -> Iterator[list[int]]:
    """Raise :class:`Terminated` on SIGTERM/SIGHUP for the duration.

    Only a signal at its default disposition is taken over: one the caller
    set to ignore (``nohup boost update &``) or handles itself stays as it
    was, or a run that survived a hangup today would die of one. Off the
    main thread ``signal.signal`` refuses, and nothing is installed. The
    previous handlers are put back on exit, so an in-process caller (the
    test suite, an embedding host) is left as it was found. Yields the
    signals actually taken over.
    """
    installed: list[int] = []
    for sig in handled_signals():
        try:
            if signal.getsignal(sig) is not signal.SIG_DFL:
                continue
            signal.signal(sig, _raise)
        except (ValueError, OSError):
            continue
        installed.append(sig)
    try:
        yield installed
    finally:
        for sig in installed:
            with contextlib.suppress(ValueError, OSError):
                signal.signal(sig, signal.SIG_DFL)
