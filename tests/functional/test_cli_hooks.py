# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests for `boost hooks` (in-process CLI)."""
from __future__ import annotations

import re

import pytest

from boost_cli.commands import bmad
from boost_cli.core import claude_settings as cs


class TestHooksAdd:
    def test_add_list_remove_global(self, boost, sandbox):
        r = boost("hooks", "add", "SessionStart",
                  "-c", "boost bmad orient", "-n", "bmad", "-s", "global",
                  "-m", "startup|resume")
        assert "added SessionStart hook 'bmad' (global)" in r.out
        assert (sandbox / ".claude" / "settings.json").exists()

        r = boost("hooks", "list")
        assert "bmad" in r.out and "SessionStart" in r.out

        r = boost("hooks", "remove", "-n", "bmad", "-s", "global")
        assert "removed 1 hook(s) named 'bmad' (global)" in r.out
        assert not cs.has_hook("global", "SessionStart", "bmad")

    def test_project_scope_writes_cwd(self, boost, sandbox, tmp_path, monkeypatch):
        proj = tmp_path / "proj"
        proj.mkdir()
        monkeypatch.chdir(proj)
        boost("hooks", "add", "SessionStart", "-c", "echo hi", "-n", "t")
        assert (proj / ".claude" / "settings.json").exists()

    def test_unknown_event_warns_but_adds(self, boost, sandbox):
        r = boost("hooks", "add", "Frobnicate",
                  "-c", "x", "-n", "z", "-s", "global")
        assert "not a known Claude hook event" in r.out
        assert cs.has_hook("global", "Frobnicate", "z")

    def test_first_add_prints_no_backup_line(self, boost, sandbox):
        r = boost("hooks", "add", "SessionStart",
                  "-c", "cmd", "-n", "bmad", "-s", "global")
        assert "backup:" not in r.out

    def test_second_add_prints_the_settings_snapshot_path(self, boost, sandbox):
        boost("hooks", "add", "SessionStart",
             "-c", "cmd-v1", "-n", "bmad", "-s", "global")
        r = boost("hooks", "add", "SessionStart",
                 "-c", "cmd-v2", "-n", "bmad", "-s", "global")
        assert "backup:" in r.out
        assert "claude-settings-history" in r.out

    def test_corrupt_settings_warns_but_add_still_succeeds(self, boost, sandbox):
        # A trailing-comma-style corrupt settings.json used to be silently
        # read as {} and then, on this very write, replaced outright —
        # dropping any `permissions`/`model` keys it held with no warning.
        p = cs.settings_path("global")
        p.parent.mkdir(parents=True)
        p.write_text('{"permissions": {"allow": ["Bash"]},', encoding="utf-8")
        r = boost("hooks", "add", "SessionStart",
                  "-c", "cmd", "-n", "bmad", "-s", "global")
        assert "invalid JSON" in r.err
        assert cs.has_hook("global", "SessionStart", "bmad")
        assert "backup:" in r.out

    def test_remove_absent_warns(self, boost, sandbox):
        r = boost("hooks", "remove", "-n", "nope", "-s", "global", expect=1)
        assert "no boost hook named 'nope'" in r.out

    def test_remove_unknown_event_hook_by_name(self, boost, sandbox):
        # `add` accepts an unrecognized event name with just a warning; a
        # by-name `remove` (no --event) must still find it, since it is not
        # among hookhost.events(host) and would otherwise be reported as
        # missing even though boost itself wrote it.
        boost("hooks", "add", "Bogus", "-c", "echo bogus", "-n", "b1",
              "-s", "global")
        r = boost("hooks", "remove", "-n", "b1", "-s", "global")
        assert "removed 1 hook(s) named 'b1'" in r.out
        assert not cs.has_hook("global", "Bogus", "b1")

    def test_list_filters_by_event(self, boost, sandbox):
        # `hooks list EVENT` used to silently ignore the extra word and show
        # every hook regardless.
        boost("hooks", "add", "SessionStart", "-c", "echo a", "-n", "a",
              "-s", "global")
        boost("hooks", "add", "SessionEnd", "-c", "echo b", "-n", "b",
              "-s", "global")
        r = boost("hooks", "list", "SessionStart")
        assert "a" in r.out and "SessionStart" in r.out
        assert "SessionEnd" not in r.out

        r = boost("hooks", "list", "NoSuchEvent")
        assert "no boost-managed hooks for event 'NoSuchEvent'" in r.out

    def test_remove_by_name_with_embedded_marker_in_command(self, boost, sandbox):
        # A command that itself contains the literal "# boost:" text (e.g.
        # quoting another hook's tagged command) must not corrupt name lookup
        # for the *outer* boost-added tag, which is always the last marker.
        boost("hooks", "add", "PostToolUse",
              "-c", "echo x # boost:zzz", "-n", "h9", "-s", "global")
        rows = cs.list_hooks("global")
        row = next(r for r in rows if r["name"] == "h9")
        assert row["command"] == "echo x # boost:zzz"
        r = boost("hooks", "remove", "-n", "h9", "-s", "global")
        assert "removed 1 hook(s) named 'h9'" in r.out
        assert not cs.has_hook("global", "PostToolUse", "h9")


class TestHooksErrors:
    def test_add_missing_command(self, boost, sandbox):
        r = boost("hooks", "add", "SessionStart", "-n", "x",
                  "-s", "global", expect=1)
        assert "needs --command" in r.err

    def test_add_missing_event(self, boost, sandbox):
        r = boost("hooks", "add", "-c", "x", "-n", "y",
                  "-s", "global", expect=1)
        assert "needs an EVENT" in r.err

    def test_add_missing_name(self, boost, sandbox):
        r = boost("hooks", "add", "SessionStart", "-c", "x",
                  "-s", "global", expect=1)
        assert "needs --name" in r.err

    def test_list_fits_the_pane_with_a_long_name_and_command(
            self, boost, sandbox, monkeypatch):
        # `command` is the one protected column. Protecting `name` as well
        # left a remainder nothing could drop: name + command alone outgrew an
        # 80-column pane and the row printed past it, the very overflow the
        # fitter exists to prevent. These are the names `boost bmad
        # autopilot` installs.
        cmd = ("boost check --strict --json | jq -r '.issues[] | .msg'"
               " | head -20 | sort")          # 72 cells: name + command > 80
        boost("hooks", "add", "SessionStart", "-s", "global", "-n", "bmad",
              "-c", "boost bmad orient --quiet --and-then-report-status-to-the-user",
              "-m", "startup|resume|clear")
        boost("hooks", "add", "PreToolUse", "-s", "global", "-n", "bmad-route",
              "-c", cmd, "-m", "Bash")
        monkeypatch.setenv("COLUMNS", "80")
        r = boost("hooks", "list")
        lines = [ln for ln in r.out.splitlines() if ln.strip()]
        assert lines and max(len(ln) for ln in lines) <= 80, r.out
        assert cmd in r.out   # protected: whole, never clipped

    def test_list_empty(self, boost, sandbox):
        r = boost("hooks", "list")
        assert "no boost-managed hooks" in r.out

    def test_timeout_must_be_positive_int(self, boost, sandbox):
        # --timeout -5 used to write a negative timeout straight into
        # settings.json; --timeout 0 is no better (Gemini's is milliseconds,
        # fed to setTimeout — a hook that expires before it runs).
        r = boost("hooks", "add", "SessionStart", "-c", "x", "-n", "y",
                  "-s", "global", "--timeout", "-5", expect=2)
        assert "must be >= 1" in r.err
        r = boost("hooks", "add", "SessionStart", "-c", "x", "-n", "y",
                  "-s", "global", "--timeout", "0", expect=2)
        assert "must be >= 1" in r.err


_ANSI = re.compile(r"\x1b\[[0-9;]*m")
# 72 cells: wider than every pane below 72, so the protected command is the
# whole row there and the sweep reaches the width where it is all that is left.
_LONG_CMD = ("boost check --strict --json | jq -r '.issues[] | .msg'"
             " | head -20 | sort")


def _add_autopilot_hooks(boost, long_command=False):
    """The two hooks `boost bmad on` installs, by its own names and matcher,
    and optionally a third whose command outgrows a narrow pane."""
    boost("hooks", "add", "SessionStart", "-s", "global", "-n", bmad.HOOK_NAME,
          "-c", "boost bmad orient --scope global || true",
          "-m", bmad.HOOK_MATCHER)
    boost("hooks", "add", "UserPromptSubmit", "-s", "global",
          "-n", bmad.ROUTE_HOOK_NAME,
          "-c", "boost bmad route --scope global || true")
    if long_command:
        boost("hooks", "add", "PreToolUse", "-s", "global", "-n", "lint-gate",
              "-c", _LONG_CMD, "-m", "Bash")


def _header(printed: str) -> list[str]:
    return _ANSI.sub("", printed).splitlines()[0].replace("│", " ").split()


def _widest(printed: str) -> int:
    return max(len(line) for line in _ANSI.sub("", printed).splitlines())


class TestListColumnOrder:
    """`name` is what `boost hooks remove -n` takes, and `out.table` drops
    columns right to left. With `name` fourth, a narrow pane dropped it second
    — after `matcher` — while `host`, the same word on every row, survived:
    COLUMNS=65 printed `host scope event command` for the autopilot's hooks.
    """

    def test_name_is_the_first_column(self, boost, sandbox, monkeypatch):
        # No COLUMNS and no TTY: nothing is fitted, every column prints.
        monkeypatch.delenv("COLUMNS", raising=False)
        _add_autopilot_hooks(boost)
        r = boost("hooks", "list")
        assert _header(r.out) == ["name", "host", "scope", "event", "matcher",
                                  "command"]
        assert r.out.splitlines()[1].startswith(bmad.HOOK_NAME + " ")

    def test_the_measured_pane_keeps_the_name(self, boost, sandbox,
                                              monkeypatch):
        monkeypatch.setenv("COLUMNS", "65")
        _add_autopilot_hooks(boost)
        r = boost("hooks", "list")
        header = _header(r.out)
        assert header[0] == "name" and header[-1] == "command", r.out
        assert _widest(r.out) <= 65, r.out

    @pytest.mark.parametrize("color", [False, True], ids=["piped", "colour"])
    def test_name_outlasts_every_other_droppable_column(
            self, boost, sandbox, monkeypatch, color):
        # `command` is protected (`keep=`), so below its own 72 cells it is
        # the whole row and overflows by design. Everywhere else the row fits,
        # and whenever anything besides `command` survives, `name` does.
        monkeypatch.setenv("BOOST_COLOR", "always" if color else "never")
        _add_autopilot_hooks(boost, long_command=True)
        name_and_command_only = []
        for cols in range(40, 101):
            monkeypatch.setenv("COLUMNS", str(cols))
            r = boost("hooks", "list")
            header = _header(r.out)
            assert _LONG_CMD in r.out, (cols, r.out)
            if header == ["command"]:
                continue
            assert header[0] == "name", (cols, r.out)
            assert _widest(r.out) <= cols, (cols, r.out)
            if header == ["name", "command"]:
                name_and_command_only.append(cols)
        # The band where one column fits beside the command is the one that
        # printed `host` alone before.
        assert name_and_command_only, "name never survived alone"
