# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: the "nothing to show" screens fit a narrow pane.

BOOST-D27 moved these screens from hand-rolled ``out.info("no X — do Y")``
lines onto ``out.empty_state``, the one affordance the rest of the CLI already
used, and gave ``out.dim`` a real margin so its indented hints could wrap.
Several of the old lines ran past a 60-column pane, measured in display
columns (`boost trending` at 68, `recommend` at 66, `log --crashes` at 62,
`schedule status` at 61); each case
below renders at 60 and asserts every line fits, that the screen uses the
standard marker, and that any command in the hint survives whole.
"""
import sys

import pytest

COLS = 60

# (argv, the remedy command that must appear whole, or None)
UNTAPPED = [
    (("taps",), "`boost tap --defaults`"),
    (("update",), "`boost tap --defaults`"),
    (("snapshot", "list"), "`boost snapshot save`"),
    (("profile", "list"), "`boost profile save daily`"),
    (("focus",), "`boost focus SKILL...`"),
    (("context", "status"), "`boost context map 'feature/*' skill1,skill2`"),
    (("log", "--crashes"), None),
    (("log",), None),
    (("tag", "--list"), None),
    (("quarantine", "--list"), None),
    (("hooks", "list"), None),
    (("attest",), None),
    (("test",), None),
    (("decay",), None),
    (("impact",), None),
]


def _fits(out: str, data: str = "") -> None:
    """Every line fits, except one carrying ``data`` — a path is data and
    overflows whole by design (CLAUDE.md: only chrome may be wrapped)."""
    for ln in out.split("\n"):
        assert len(ln) <= COLS or (data and data in ln), ln


@pytest.mark.parametrize(("argv", "cmd"), UNTAPPED,
                         ids=[" ".join(a) for a, _ in UNTAPPED])
def test_empty_screen_fits_and_uses_the_standard_marker(
        boost, sandbox, monkeypatch, argv, cmd):
    monkeypatch.setenv("COLUMNS", str(COLS))
    r = boost(*argv)
    _fits(r.out)
    assert "  ○ " in r.out
    if cmd:
        assert cmd in r.out


@pytest.mark.parametrize(("argv", "cmd"), [
    (("trending",), "`boost tap --defaults`"),
    (("recommend", "--path", "{empty}"), "`boost search <keyword>`"),
], ids=["trending", "recommend"])
def test_tapped_empty_screen_fits(boost, tapped, tmp_path, monkeypatch,
                                  argv, cmd):
    empty = tmp_path / "empty-proj"
    empty.mkdir()
    monkeypatch.setenv("COLUMNS", str(COLS))
    r = boost(*[a.format(empty=empty) for a in argv])
    _fits(r.out, data=empty.name)
    assert "  ○ " in r.out
    assert cmd in r.out


def test_schedule_status_hint_wraps_under_its_margin(boost, sandbox,
                                                     monkeypatch):
    # The launchd branch, as TestScheduleDarwin does: CI also runs on Linux.
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setenv("COLUMNS", str(COLS))
    r = boost("schedule", "status")
    _fits(r.out)
    assert "  `boost schedule enable --interval 6h|12h|daily`" in r.out
