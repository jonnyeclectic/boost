"""A braille spinner for indeterminate waits (network calls, AI reranking…).

Deliberately silent — no thread, no output — whenever the stream isn't an
interactive TTY or color is off, so piped output, CI logs and captured test
output stay clean. Usage:

    with spin.Spinner("ranking with Claude"):
        result = slow_network_call()
"""
from __future__ import annotations

import itertools
import sys
import threading
from typing import Optional

from .core import output as out

_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_INTERVAL = 0.08


class Spinner:
    def __init__(self, label: str = "", stream=None):
        self.label = label
        self.stream = stream if stream is not None else sys.stderr
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def active(self) -> bool:
        """Animate only on an interactive, color-capable TTY."""
        s = self.stream
        return (out.color_level(s) > 0
                and hasattr(s, "isatty") and s.isatty())

    def __enter__(self) -> Spinner:
        if self.active():
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        return self

    def _spin(self) -> None:
        for frame in itertools.cycle(_FRAMES):
            if self._stop.is_set():
                break
            self.stream.write("\r" + out.aurora(frame, "cyan") + " " + self.label)
            self.stream.flush()
            self._stop.wait(_INTERVAL)

    def __exit__(self, *exc) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
        if self.active():
            self.stream.write("\r" + " " * (out.visible_len(self.label) + 2) + "\r")
            self.stream.flush()


def bar(current: int, total: int, width: int = 20) -> str:
    """A determinate progress bar (filled ▓ vs light ░) for current/total."""
    total = total if total > 0 else 1
    frac = current / total
    frac = 0.0 if frac < 0 else 1.0 if frac > 1 else frac
    filled = round(frac * width)
    return "▓" * filled + "░" * (width - filled)


def progress(current: int, total: int, label: str = "", stream=None) -> None:
    """Redraw a determinate progress line in place. Silent (no output) unless
    the stream is an interactive, color-capable TTY, so piped/CI/test output
    stays clean. Clears the line once current reaches total.
    """
    s = stream if stream is not None else sys.stderr
    if not (out.color_level(s) > 0 and hasattr(s, "isatty") and s.isatty()):
        return
    line = "%s %d/%d %s" % (out.aurora(bar(current, total), "cyan"),
                            current, total, label)
    s.write("\r" + line)
    if current >= total:
        s.write("\r" + " " * out.visible_len(line) + "\r")
    s.flush()
