# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests for the host-aware side of core/claude_settings.py.

`tests/unit/test_claude_settings.py` pins the Claude behaviour and must keep
passing untouched; this file pins what changes when `host="gemini"` is passed.
Everything runs against the `sandbox` fixture's throwaway $HOME, so the real
~/.gemini is never opened.
"""
from __future__ import annotations

import json

import pytest

from boost_cli.core import claude_settings as cs
from boost_cli.core import hookhost as hh
from boost_cli.core import paths
from boost_cli.errors import BoostError


class TestScopePaths:
    def test_gemini_global_is_under_dot_gemini(self, sandbox):
        assert cs.settings_path("global", host=hh.GEMINI) == \
            sandbox / ".gemini" / "settings.json"

    def test_gemini_project_is_under_cwd_dot_gemini(self, sandbox, tmp_path):
        proj = tmp_path / "proj"
        assert cs.settings_path("project", proj, host=hh.GEMINI) == \
            proj / ".gemini" / "settings.json"

    def test_claude_remains_the_default(self, sandbox):
        assert cs.settings_path("global") == sandbox / ".claude" / "settings.json"

    def test_unknown_host_raises(self, sandbox):
        with pytest.raises(BoostError):
            cs.settings_path("global", host="emacs")


class TestGeminiHookCrud:
    def test_add_writes_the_gemini_block_shape(self, sandbox):
        cs.add_hook("global", "BeforeTool", "guard", "boost check",
                    matcher="run_shell_command", timeout=10, host=hh.GEMINI)
        data = json.loads(
            (sandbox / ".gemini" / "settings.json").read_text(encoding="utf-8"))
        block = data["hooks"]["BeforeTool"][0]
        assert block["matcher"] == "run_shell_command"
        entry = block["hooks"][0]
        assert entry["type"] == "command"
        assert entry["command"] == "boost check # boost:guard"
        assert entry["timeout"] == 10_000      # seconds in, milliseconds out
        assert entry["name"] == "boost:guard"

    def test_the_two_hosts_do_not_see_each_others_hooks(self, sandbox):
        cs.add_hook("global", "SessionStart", "a", "echo c", host=hh.CLAUDE)
        cs.add_hook("global", "SessionStart", "b", "echo g", host=hh.GEMINI)
        assert cs.has_hook("global", "SessionStart", "a", host=hh.CLAUDE)
        assert not cs.has_hook("global", "SessionStart", "b", host=hh.CLAUDE)
        assert cs.has_hook("global", "SessionStart", "b", host=hh.GEMINI)
        assert not cs.has_hook("global", "SessionStart", "a", host=hh.GEMINI)

    def test_adding_a_gemini_hook_never_touches_claude_settings(self, sandbox):
        cs.add_hook("global", "SessionStart", "g", "echo g", host=hh.GEMINI)
        assert not (sandbox / ".claude").exists()

    def test_remove_is_scoped_to_its_host(self, sandbox):
        cs.add_hook("global", "SessionStart", "n", "echo x", host=hh.CLAUDE)
        cs.add_hook("global", "SessionStart", "n", "echo x", host=hh.GEMINI)
        assert cs.remove_hook("global", "SessionStart", "n", host=hh.GEMINI) == 1
        assert not cs.has_hook("global", "SessionStart", "n", host=hh.GEMINI)
        assert cs.has_hook("global", "SessionStart", "n", host=hh.CLAUDE)

    def test_add_is_idempotent(self, sandbox):
        for _ in range(3):
            cs.add_hook("global", "SessionStart", "g", "echo g", host=hh.GEMINI)
        data = cs.load("global", host=hh.GEMINI)
        assert len(data["hooks"]["SessionStart"]) == 1

    def test_a_users_own_gemini_hook_survives(self, sandbox):
        p = sandbox / ".gemini"
        p.mkdir()
        (p / "settings.json").write_text(json.dumps({
            "mcpServers": {"x": {}},
            "hooks": {"BeforeTool": [
                {"hooks": [{"type": "command", "command": "mine.sh"}]}]},
        }), encoding="utf-8")
        cs.add_hook("global", "BeforeTool", "g", "echo g", host=hh.GEMINI)
        cs.remove_hook("global", "BeforeTool", "g", host=hh.GEMINI)
        data = cs.load("global", host=hh.GEMINI)
        assert data["mcpServers"] == {"x": {}}
        assert data["hooks"]["BeforeTool"][0]["hooks"][0]["command"] == "mine.sh"


class TestListHooks:
    def test_rows_carry_their_host(self, sandbox):
        cs.add_hook("global", "SessionStart", "c", "echo c", host=hh.CLAUDE)
        cs.add_hook("global", "BeforeTool", "g", "echo g", host=hh.GEMINI)
        rows = cs.list_all_hooks(host=hh.GEMINI)
        assert [(r["host"], r["event"], r["name"]) for r in rows] == \
            [("gemini", "BeforeTool", "g")]

    def test_claude_rows_report_their_host_too(self, sandbox):
        cs.add_hook("global", "SessionStart", "c", "echo c")
        assert cs.list_all_hooks()[0]["host"] == "claude"
        # list_hooks keeps its original single-host row shape.
        assert "host" not in cs.list_hooks()[0]


class TestHistorySnapshots:
    def test_gemini_snapshots_do_not_collide_with_claude(self, sandbox):
        cs.save("global", {"a": 1}, host=hh.CLAUDE)
        cs.save("global", {"a": 2}, host=hh.CLAUDE)     # snapshots the first
        cs.save("global", {"b": 1}, host=hh.GEMINI)
        cs.save("global", {"b": 2}, host=hh.GEMINI)     # snapshots the first
        hist = paths.state_dir() / "claude-settings-history"
        names = sorted(f.name.split("-")[0] for f in hist.glob("*.json"))
        assert names == ["gemini", "global"]
        gem = next(hist.glob("gemini-global-*.json"))
        assert json.loads(gem.read_text(encoding="utf-8")) == {"b": 1}
