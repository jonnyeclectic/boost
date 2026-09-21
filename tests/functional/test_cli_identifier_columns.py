# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""An identifier column is shown whole or not at all, at every pane width.

Swept piped at COLUMNS 40..100, the range the finding measured. Before
`out.table` took `whole=`, the fitter squeezed the widest shrinkable column
before dropping one, and in these tables that was the identifier:
`boost hooks list` printed `bmad-r…` for `bmad-route`, and `boost list`
printed `brainstorm…`. Neither is an argument any command accepts.
"""
from __future__ import annotations

import re

import pytest

from boost_cli.commands import bmad

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
PANES = range(40, 101)


def _cells(printed: str, column: str) -> list[list[str]] | None:
    """The first cell of every body row under each table led by `column`,
    or None when no such table was printed (the column was dropped)."""
    lines = _ANSI.sub("", printed).replace("│", " ").splitlines()
    tables = []
    for i, line in enumerate(lines):
        if line.split()[:1] != [column]:
            continue
        body = []
        for row in lines[i + 1:]:
            if not row.strip() or row.startswith("  "):
                break
            body.append(row.split()[0])
        tables.append(body)
    return tables or None


@pytest.mark.parametrize("color", [False, True], ids=["piped", "colour"])
def test_hooks_list_never_clips_a_hook_name(boost, sandbox, monkeypatch,
                                            color):
    monkeypatch.setenv("BOOST_COLOR", "always" if color else "never")
    names = [bmad.HOOK_NAME, bmad.ROUTE_HOOK_NAME, "lint-on-edit"]
    boost("hooks", "add", "SessionStart", "-s", "global", "-n", names[0],
          "-c", "boost bmad orient --scope global || true",
          "-m", bmad.HOOK_MATCHER)
    boost("hooks", "add", "UserPromptSubmit", "-s", "global", "-n", names[1],
          "-c", "boost bmad route --scope global || true")
    boost("hooks", "add", "PreToolUse", "-s", "global", "-n", names[2],
          "-c", "ruff check .", "-m", "Edit|Write")
    shown = 0
    for cols in PANES:
        monkeypatch.setenv("COLUMNS", str(cols))
        tables = _cells(boost("hooks", "list").out, "name")
        if tables is None:
            continue
        shown += 1
        assert tables == [names], (cols, tables)
    assert shown, "name never survived — the sweep proved nothing"


def test_list_never_clips_a_skill_name(boost, tapped, monkeypatch):
    names = ["brainstorming", "commit-messages", "jira-integration",
             "tdd-workflow"]
    for name in names:
        boost("install", name)
    for cols in PANES:
        monkeypatch.setenv("COLUMNS", str(cols))
        assert _cells(boost("list").out, "NAME") == [names], cols


def test_browse_fallback_never_clips_a_skill_name(boost, tapped, monkeypatch):
    # `boost browse` off a TTY prints the plain catalog, whose footer tells
    # the reader to `boost install <name>` with the name in this column.
    monkeypatch.delenv("COLUMNS", raising=False)
    names = _cells(boost("browse").out, "name")
    assert names and all("…" not in n for n in names[0])
    for cols in PANES:
        monkeypatch.setenv("COLUMNS", str(cols))
        assert _cells(boost("browse").out, "name") == names, cols


# The other tables whose leading column is the handle a later command takes.
# The cohort and tag fixtures make the identifier the widest text column on
# purpose: the old fitter shrank the widest column first, so a short one would
# never have been clipped and the case could not fail. Each case below does
# fail with `whole=` removed from its call site.
_SKILLS = ["brainstorming", "commit-messages", "jira-integration",
           "tdd-workflow"]


def _install_all(boost):
    for name in _SKILLS:
        boost("install", name)


def _two_cohorts(boost):
    for name in ("platform-early-adopters-pilot", "security-review-canary"):
        boost("cohort", "create", name, "--skills", "tdd-workflow",
              "--percent", "50")


def _two_tags(boost):
    boost("install", "brainstorming")
    boost("tag", "brainstorming", "+needs-security-review-first",
          "+frontend-platform-team")


@pytest.mark.parametrize("setup, argv, column", [
    pytest.param(_install_all, ("attest",), "NAME", id="attest"),
    pytest.param(_two_cohorts, ("cohort", "list"), "COHORT", id="cohort"),
    pytest.param(_two_tags, ("tag", "--list"), "TAG", id="tag-list"),
    pytest.param(None, ("tap", "--catalog", "--dry-run"), "NAME",
                 id="tap-catalog-dry-run"),
])
def test_leading_identifier_is_never_clipped(boost, tapped, monkeypatch,
                                             setup, argv, column):
    if setup:
        setup(boost)
    # With no pane nothing is fitted, so this is every identifier in full.
    monkeypatch.delenv("COLUMNS", raising=False)
    whole = _cells(boost(*argv).out, column)
    assert whole and all("…" not in c for t in whole for c in t), whole
    # No kept neighbour, so the identifier is the last column standing and
    # is never dropped: every width must show all of it, whole.
    for cols in PANES:
        monkeypatch.setenv("COLUMNS", str(cols))
        assert _cells(boost(*argv).out, column) == whole, cols
