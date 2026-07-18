"""Unit tests: boost_cli/spin.Spinner — the TTY-guarded braille spinner."""
from __future__ import annotations

import io

import pytest

from boost_cli import spin


class FakeStream(io.StringIO):
    def __init__(self, tty):
        super().__init__()
        self._tty = tty

    def isatty(self):
        return self._tty


@pytest.fixture(autouse=True)
def force_color(monkeypatch):
    # color on, so `active()` hinges purely on the TTY check
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("CLICOLOR_FORCE", "1")


def test_silent_on_non_tty():
    s = FakeStream(tty=False)
    with spin.Spinner("working", stream=s) as sp:
        pass
    assert sp.active() is False
    assert s.getvalue() == ""            # nothing written, no thread started
    assert sp._thread is None


def test_no_color_is_silent(monkeypatch):
    monkeypatch.delenv("CLICOLOR_FORCE", raising=False)
    monkeypatch.setenv("NO_COLOR", "1")
    s = FakeStream(tty=True)             # a TTY, but color is off
    with spin.Spinner("working", stream=s):
        pass
    assert s.getvalue() == ""


def test_active_on_color_tty():
    assert spin.Spinner("x", stream=FakeStream(tty=True)).active() is True


def test_frames_are_braille():
    assert spin._FRAMES == "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def test_context_manager_returns_self():
    s = FakeStream(tty=False)
    sp = spin.Spinner("x", stream=s)
    assert sp.__enter__() is sp
    assert sp.__exit__(None, None, None) is None   # doesn't suppress exceptions


def test_tty_run_writes_and_clears():
    # exercise the animated path: wait (bounded) for the thread's first frame
    import time
    s = FakeStream(tty=True)
    with spin.Spinner("go", stream=s):
        for _ in range(50):
            if s.getvalue():
                break
            time.sleep(0.02)
    out = s.getvalue()
    assert "\r" in out                   # in-place redraw
    assert "go" in out                   # the label was shown
