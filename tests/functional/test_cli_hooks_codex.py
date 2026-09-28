# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests for `boost hooks --host codex` (in-process CLI).

`test_cli_hooks.py` pins the Claude wording and `test_cli_hooks_gemini.py`
Gemini's; both must keep passing untouched. What is Codex's alone at this
layer is the *refusals* — the command layer is where a user finds out that a
hook cannot exist, and Codex has two different ways to reach that, which used
to share one hardcoded sentence about sub-agents that is Gemini's gap and not
Codex's.
"""
from __future__ import annotations

import json

from boost_cli.core import claude_settings as cs
from boost_cli.core import hookhost as hh


class TestCodexAdd:
    def test_add_list_remove_global(self, boost, sandbox):
        r = boost("hooks", "add", "SessionStart", "--host", "codex",
                  "-c", "boost bmad orient", "-n", "bmad", "-s", "global")
        assert "added SessionStart hook 'bmad' (codex/global)" in r.out
        assert (sandbox / ".codex" / "hooks.json").exists()
        assert not (sandbox / ".claude").exists()

        r = boost("hooks", "list")
        assert "codex" in r.out and "bmad" in r.out

        r = boost("hooks", "remove", "--host", "codex", "-n", "bmad",
                  "-s", "global")
        assert "removed 1 hook(s) named 'bmad' (codex/global)" in r.out
        assert not cs.has_hook("global", "SessionStart", "bmad", host=hh.CODEX)

    def test_the_settings_line_names_hooks_json(self, boost, sandbox):
        r = boost("hooks", "add", "SessionStart", "--host", "codex",
                  "-c", "echo x", "-n", "t", "-s", "global")
        assert "hooks.json" in r.out
        assert "settings.json" not in r.out

    def test_timeout_is_written_in_seconds(self, boost, sandbox):
        boost("hooks", "add", "PreToolUse", "--host", "codex", "-c", "echo x",
              "-n", "t", "-s", "global", "--timeout", "3")
        data = json.loads(
            (sandbox / ".codex" / "hooks.json").read_text(encoding="utf-8"))
        assert data["hooks"]["PreToolUse"][0]["hooks"][0]["timeout"] == 3

    def test_project_scope_writes_dot_codex_in_cwd(self, boost, sandbox,
                                                   tmp_path, monkeypatch):
        proj = tmp_path / "proj"
        proj.mkdir()
        monkeypatch.chdir(proj)
        boost("hooks", "add", "SessionStart", "--host", "codex",
              "-c", "echo hi", "-n", "t")
        assert (proj / ".codex" / "hooks.json").exists()
        assert not (proj / ".claude").exists()


class TestTheTrustNoticeIsPrinted:
    """Codex will not run a hook it was not granted trust for.

    "added" and nothing else is true and useless: the hook sits in the file
    doing nothing until the user answers a prompt they have not been told to
    expect.
    """

    def test_a_user_hook_says_codex_will_ask(self, boost, sandbox):
        r = boost("hooks", "add", "SessionStart", "--host", "codex",
                  "-c", "echo x", "-n", "t", "-s", "global")
        assert "trust" in r.out

    def test_a_project_hook_also_says_the_repo_must_be_trusted(self, boost,
                                                               sandbox,
                                                               tmp_path,
                                                               monkeypatch):
        proj = tmp_path / "proj"
        proj.mkdir()
        monkeypatch.chdir(proj)
        r = boost("hooks", "add", "SessionStart", "--host", "codex",
                  "-c", "echo x", "-n", "t")
        assert "trust_level" in r.out

    def test_the_other_hosts_say_nothing_of_the_kind(self, boost, sandbox):
        for host in (hh.CLAUDE, hh.GEMINI):
            r = boost("hooks", "add", "SessionStart", "--host", host,
                      "-c", "echo x", "-n", "t", "-s", "global")
            assert "trust" not in r.out, host


class TestTheTwoRefusalsReadDifferently:
    def test_notification_is_refused_as_a_missing_counterpart(self, boost,
                                                              sandbox):
        r = boost("hooks", "add", "Notification", "--host", "codex",
                  "-c", "echo x", "-n", "n", "-s", "global", expect=None)
        assert r.rc != 0
        err = r.out + r.err
        assert "no Codex CLI counterpart" in err
        assert "no notification event" in err
        # Gemini's gap, hardcoded into this hint before Codex existed.
        assert "sub-agents" not in err

    def test_sub_agent_events_are_fine_on_codex(self, boost, sandbox):
        # The same events Gemini refuses. Codex has both.
        for event in ("SubagentStart", "SubagentStop"):
            boost("hooks", "add", event, "--host", "codex", "-c", "echo x",
                  "-n", event.lower(), "-s", "global")
            assert cs.has_hook("global", event, event.lower(), host=hh.CODEX)

    def test_an_unknown_event_is_refused_rather_than_added(self, boost,
                                                           sandbox):
        """The warn-but-add fallthrough is wrong here: Codex drops it silently."""
        r = boost("hooks", "add", "NotARealEvent", "--host", "codex",
                  "-c", "echo x", "-n", "n", "-s", "global", expect=None)
        assert r.rc != 0
        assert "not a known Codex hook event" in (r.out + r.err)
        assert not (sandbox / ".codex" / "hooks.json").exists()

    def test_a_wrong_case_event_is_refused_too(self, boost, sandbox):
        r = boost("hooks", "add", "sessionstart", "--host", "codex",
                  "-c", "echo x", "-n", "n", "-s", "global", expect=None)
        assert r.rc != 0
        assert not (sandbox / ".codex" / "hooks.json").exists()

    def test_gemini_still_warns_and_adds(self, boost, sandbox):
        # The permissive path survives for the host it was written for.
        r = boost("hooks", "add", "NotARealEvent", "--host", "gemini",
                  "-c", "echo x", "-n", "n", "-s", "global")
        assert "adding anyway" in (r.out + r.err)
        assert cs.has_hook("global", "NotARealEvent", "n", host=hh.GEMINI)


class TestARelocatedCodexHome:
    def test_the_write_is_refused_and_says_why(self, boost, sandbox,
                                               monkeypatch, tmp_path):
        elsewhere = tmp_path / "real-codex"
        monkeypatch.setenv("CODEX_HOME", str(elsewhere))
        r = boost("hooks", "add", "SessionStart", "--host", "codex",
                  "-c", "echo x", "-n", "t", "-s", "global", expect=None)
        assert r.rc != 0
        assert "CODEX_HOME" in (r.out + r.err)
        assert not elsewhere.exists()

    def test_force_writes_it(self, boost, sandbox, monkeypatch, tmp_path):
        elsewhere = tmp_path / "real-codex"
        monkeypatch.setenv("CODEX_HOME", str(elsewhere))
        boost("hooks", "add", "SessionStart", "--host", "codex", "--force",
              "-c", "echo x", "-n", "t", "-s", "global")
        assert (elsewhere / "hooks.json").exists()

    def test_force_removes_it_again(self, boost, sandbox, monkeypatch,
                                    tmp_path):
        elsewhere = tmp_path / "real-codex"
        monkeypatch.setenv("CODEX_HOME", str(elsewhere))
        boost("hooks", "add", "SessionStart", "--host", "codex", "--force",
              "-c", "echo x", "-n", "t", "-s", "global")
        r = boost("hooks", "remove", "--host", "codex", "--force", "-n", "t",
                  "-s", "global")
        assert "removed 1 hook(s)" in r.out
