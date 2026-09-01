# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests for `boost hooks` (in-process CLI)."""
from __future__ import annotations

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

    def test_list_empty(self, boost, sandbox):
        r = boost("hooks", "list")
        assert "no boost-managed hooks" in r.out
