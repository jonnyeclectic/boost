# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests for `boost hooks --host gemini` (in-process CLI).

`tests/functional/test_cli_hooks.py` pins the Claude wording and must keep
passing untouched.
"""
from __future__ import annotations

import json

from boost_cli.core import claude_settings as cs
from boost_cli.core import hookhost as hh


class TestGeminiAdd:
    def test_add_list_remove_global(self, boost, sandbox):
        r = boost("hooks", "add", "SessionStart", "--host", "gemini",
                  "-c", "boost bmad orient", "-n", "bmad", "-s", "global",
                  "-m", "startup")
        assert "added SessionStart hook 'bmad' (gemini/global)" in r.out
        assert (sandbox / ".gemini" / "settings.json").exists()
        assert not (sandbox / ".claude").exists()

        r = boost("hooks", "list")
        assert "gemini" in r.out and "bmad" in r.out

        r = boost("hooks", "remove", "--host", "gemini", "-n", "bmad",
                  "-s", "global")
        assert "removed 1 hook(s) named 'bmad' (gemini/global)" in r.out
        assert not cs.has_hook("global", "SessionStart", "bmad", host=hh.GEMINI)

    def test_timeout_is_written_in_milliseconds(self, boost, sandbox):
        boost("hooks", "add", "BeforeTool", "--host", "gemini", "-c", "echo x",
              "-n", "t", "-s", "global", "--timeout", "3")
        data = json.loads(
            (sandbox / ".gemini" / "settings.json").read_text(encoding="utf-8"))
        assert data["hooks"]["BeforeTool"][0]["hooks"][0]["timeout"] == 3000

    def test_project_scope_writes_dot_gemini_in_cwd(self, boost, sandbox,
                                                    tmp_path, monkeypatch):
        proj = tmp_path / "proj"
        proj.mkdir()
        monkeypatch.chdir(proj)
        boost("hooks", "add", "SessionStart", "--host", "gemini",
              "-c", "echo hi", "-n", "t")
        assert (proj / ".gemini" / "settings.json").exists()
        assert not (proj / ".claude").exists()


class TestEventTranslation:
    def test_a_claude_event_name_is_translated_and_said_out_loud(self, boost,
                                                                 sandbox):
        r = boost("hooks", "add", "PreToolUse", "--host", "gemini",
                  "-c", "echo x", "-n", "n", "-s", "global")
        assert "Claude's 'PreToolUse' is Gemini's 'BeforeTool'" in r.out
        assert "added BeforeTool hook 'n' (gemini/global)" in r.out
        assert cs.has_hook("global", "BeforeTool", "n", host=hh.GEMINI)

    def test_an_event_with_no_counterpart_is_refused_not_dropped(self, boost,
                                                                 sandbox):
        r = boost("hooks", "add", "SubagentStop", "--host", "gemini",
                  "-c", "echo x", "-n", "n", "-s", "global", expect=1)
        assert "no Gemini CLI counterpart" in r.err
        assert not (sandbox / ".gemini").exists()

    def test_unknown_event_warns_but_adds(self, boost, sandbox):
        r = boost("hooks", "add", "Frobnicate", "--host", "gemini",
                  "-c", "x", "-n", "z", "-s", "global")
        assert "not a known Gemini hook event" in r.out
        assert cs.has_hook("global", "Frobnicate", "z", host=hh.GEMINI)

    def test_remove_without_an_event_sweeps_gemini_events(self, boost, sandbox):
        boost("hooks", "add", "PreCompact", "--host", "gemini", "-c", "x",
              "-n", "sweep", "-s", "global")
        r = boost("hooks", "remove", "--host", "gemini", "-n", "sweep",
                  "-s", "global")
        assert "removed 1 hook(s)" in r.out


class TestListAcrossHosts:
    def test_list_shows_both_hosts_by_default(self, boost, sandbox):
        boost("hooks", "add", "SessionStart", "-c", "c", "-n", "cc", "-s", "global")
        boost("hooks", "add", "SessionStart", "--host", "gemini", "-c", "g",
              "-n", "gg", "-s", "global")
        r = boost("hooks", "list")
        assert "cc" in r.out and "gg" in r.out
        assert "claude" in r.out and "gemini" in r.out

    def test_list_can_be_filtered_to_one_host(self, boost, sandbox):
        boost("hooks", "add", "SessionStart", "-c", "c", "-n", "cc", "-s", "global")
        boost("hooks", "add", "SessionStart", "--host", "gemini", "-c", "g",
              "-n", "gg", "-s", "global")
        r = boost("hooks", "list", "--host", "gemini")
        assert "gg" in r.out and "cc" not in r.out

    def test_empty_message_names_the_host(self, boost, sandbox):
        r = boost("hooks", "list", "--host", "gemini")
        assert "no boost-managed hooks" in r.out


class TestErrors:
    def test_unknown_host_is_rejected(self, boost, sandbox):
        r = boost("hooks", "list", "--host", "emacs", expect=2)
        assert "emacs" in r.err
