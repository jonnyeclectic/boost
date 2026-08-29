# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: the smoke suite's `--help` sweep covers every command.

``tests/smoke.sh`` ends with a loop asserting that every command answers
``--help`` without crashing. It is the only tier that runs the real ``./boost``
shim end to end, so it is the only place a command whose module fails to import,
or whose parser is malformed, is caught at all.

The list is a hand-maintained heredoc, and it had fallen **five commands
behind** ``cli.COMMANDS`` — ``bmad``, ``chat``, ``hooks``, ``run`` and
``trust``. All five happened to answer ``--help`` fine, so nothing was broken;
what was broken is the guarantee. The suite reported "every command answers
--help" while asking 73 of 78, and the gap grows silently every time someone
adds a row to ``COMMANDS`` — which this repo does often, since that is the
documented way to add a command.

A hand-maintained mirror of a generated list is drift waiting to happen, so
mirror it from the source instead of trusting it to be updated. This is the
same treatment ``docs/commands.html`` already gets from
``build_command_reference.py --check``: the artifact may be written by hand, but
it may not disagree with ``COMMANDS``.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from boost_cli import cli

SMOKE = Path(__file__).resolve().parents[2] / "tests" / "smoke.sh"

pytestmark = pytest.mark.skipif(
    not SMOKE.exists(), reason="tests/smoke.sh not reachable")


def listed_commands() -> list[str]:
    """The commands smoke.sh feeds to its `--help` loop."""
    text = SMOKE.read_text(encoding="utf-8")
    m = re.search(r"<<'CMDS'\n(.*?)\nCMDS\n", text, re.S)
    assert m, "could not find the CMDS heredoc in smoke.sh"
    return [line.strip() for line in m.group(1).splitlines() if line.strip()]


class TestTheGuardCanActuallySee:
    def test_the_heredoc_is_found_and_populated(self):
        # Without this the comparison below passes vacuously the moment the
        # heredoc is renamed or reformatted.
        assert len(listed_commands()) > 50, listed_commands()

    def test_a_known_command_is_present(self):
        assert "install" in listed_commands()


class TestEveryCommandIsSmokeTested:
    def test_no_command_is_missing_from_the_sweep(self):
        missing = sorted({name for name, *_ in cli.COMMANDS}
                         - set(listed_commands()))
        assert not missing, (
            "smoke.sh claims 'every command answers --help' but never asks "
            "these: %s. Add them to the CMDS heredoc." % ", ".join(missing))

    def test_the_sweep_lists_no_command_that_no_longer_exists(self):
        # A stale entry fails the suite with an unhelpful "unknown command"
        # rather than pointing at this list.
        stale = sorted(set(listed_commands())
                       - {name for name, *_ in cli.COMMANDS})
        assert not stale, stale

    def test_no_command_is_listed_twice(self):
        listed = listed_commands()
        dupes = sorted({c for c in listed if listed.count(c) > 1})
        assert not dupes, dupes
