# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for core/claude_settings.py — the settings.json / hook primitive."""
from __future__ import annotations

import json

import pytest

from boost_cli.core import claude_settings as cs
from boost_cli.core import paths
from boost_cli.errors import BoostError

# ------------------------------------------------------------------ scope paths

class TestScopePaths:
    def test_global_path_under_home(self, sandbox):
        assert cs.settings_path("global") == sandbox / ".claude" / "settings.json"

    def test_project_path_under_cwd(self, sandbox, tmp_path):
        proj = tmp_path / "proj"
        assert cs.settings_path("project", proj) == proj / ".claude" / "settings.json"

    def test_unknown_scope_raises(self, sandbox):
        with pytest.raises(BoostError):
            cs.settings_path("bogus")


# ------------------------------------------------------------------ load / save

class TestLoadSave:
    def test_missing_file_is_empty(self, sandbox):
        assert cs.load("global") == {}

    def test_corrupt_file_is_empty(self, sandbox):
        p = cs.settings_path("global")
        p.parent.mkdir(parents=True)
        p.write_text("{not json", encoding="utf-8")
        assert cs.load("global") == {}

    def test_save_round_trips(self, sandbox):
        cs.save("global", {"model": "opus"})
        assert cs.load("global") == {"model": "opus"}
        # valid, pretty-printed JSON on disk
        raw = cs.settings_path("global").read_text(encoding="utf-8")
        assert json.loads(raw)["model"] == "opus"

    def test_save_snapshots_prior_version(self, sandbox):
        cs.save("global", {"v": 1})
        cs.save("global", {"v": 2})
        hist = list((paths.state_dir() / "claude-settings-history").glob("global-*.json"))
        assert len(hist) == 1
        assert json.loads(hist[0].read_text(encoding="utf-8")) == {"v": 1}


# -------------------------------------------------------------------- hook CRUD

class TestHooks:
    def test_add_then_has_and_list(self, sandbox):
        cs.add_hook("global", "SessionStart", "bmad", "boost bmad orient",
                    matcher="startup|resume")
        assert cs.has_hook("global", "SessionStart", "bmad")
        rows = cs.list_hooks("global")
        assert rows == [{
            "scope": "global", "event": "SessionStart", "name": "bmad",
            "command": "boost bmad orient", "matcher": "startup|resume",
        }]

    def test_marker_embedded_in_command(self, sandbox):
        cs.add_hook("global", "SessionStart", "bmad", "boost bmad orient")
        data = cs.load("global")
        cmd = data["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        assert cmd == "boost bmad orient # boost:bmad"

    def test_add_is_idempotent(self, sandbox):
        cs.add_hook("global", "SessionStart", "bmad", "cmd-v1")
        cs.add_hook("global", "SessionStart", "bmad", "cmd-v2")
        rows = cs.list_hooks("global")
        assert len(rows) == 1
        assert rows[0]["command"] == "cmd-v2"

    def test_remove_returns_count_and_clears(self, sandbox):
        cs.add_hook("global", "SessionStart", "bmad", "cmd")
        assert cs.remove_hook("global", "SessionStart", "bmad") == 1
        assert not cs.has_hook("global", "SessionStart", "bmad")
        # empty hooks/event pruned entirely
        assert cs.load("global") == {}

    def test_remove_absent_is_zero(self, sandbox):
        assert cs.remove_hook("global", "SessionStart", "bmad") == 0

    def test_hook_name_uses_last_marker_not_first(self, sandbox):
        # A command that itself contains the literal "# boost:" text (e.g.
        # quoting another hook's tagged command) must not be mistaken for
        # boost's own trailing tag, which is always the *last* marker.
        cs.add_hook("global", "SessionStart", "h9", "echo x # boost:zzz")
        rows = cs.list_hooks("global")
        assert rows == [{
            "scope": "global", "event": "SessionStart", "name": "h9",
            "command": "echo x # boost:zzz", "matcher": "",
        }]
        assert cs.has_hook("global", "SessionStart", "h9")
        assert cs.remove_hook("global", "SessionStart", "h9") == 1

    def test_remove_by_name_scans_events_actually_present(self, sandbox):
        # remove_hook_by_name with event=None must find a hook filed under an
        # event outside the known-event table (add_hook accepts any event
        # name; only the CLI layer warns).
        cs.add_hook("global", "Bogus", "b1", "echo bogus")
        assert cs.remove_hook_by_name("global", "b1") == 1
        assert not cs.has_hook("global", "Bogus", "b1")

    def test_remove_by_name_with_explicit_event_is_scoped(self, sandbox):
        cs.add_hook("global", "SessionStart", "n", "echo a")
        cs.add_hook("global", "Stop", "n", "echo b")
        assert cs.remove_hook_by_name("global", "n", event="Stop") == 1
        assert not cs.has_hook("global", "Stop", "n")
        assert cs.has_hook("global", "SessionStart", "n")

    def test_remove_by_name_absent_is_zero(self, sandbox):
        assert cs.remove_hook_by_name("global", "nope") == 0

    def test_remove_by_name_no_hooks_key_is_zero(self, sandbox):
        cs.save("global", {"model": "opus"})
        assert cs.remove_hook_by_name("global", "nope") == 0

    def test_never_clobbers_user_hooks(self, sandbox):
        # A pre-existing, non-boost user hook must survive add + remove.
        user_block = {"matcher": "Bash",
                      "hooks": [{"type": "command", "command": "my-guard.sh"}]}
        cs.save("global", {"hooks": {"SessionStart": [user_block]},
                           "model": "opus"})
        cs.add_hook("global", "SessionStart", "bmad", "boost bmad orient")
        cs.remove_hook("global", "SessionStart", "bmad")
        data = cs.load("global")
        # user's hook + unrelated setting intact; ours gone
        assert data["model"] == "opus"
        assert data["hooks"]["SessionStart"] == [user_block]
        assert cs.list_hooks("global") == []

    def test_same_name_prefix_not_confused(self, sandbox):
        # 'bmad' and 'bmad-extra' are distinct despite the shared prefix.
        cs.add_hook("global", "SessionStart", "bmad", "a")
        cs.add_hook("global", "SessionStart", "bmad-extra", "b")
        assert cs.remove_hook("global", "SessionStart", "bmad") == 1
        assert cs.has_hook("global", "SessionStart", "bmad-extra")
        assert not cs.has_hook("global", "SessionStart", "bmad")

    def test_list_all_scopes(self, sandbox, tmp_path):
        proj = tmp_path / "proj"
        cs.add_hook("global", "SessionStart", "bmad", "g")
        cs.add_hook("project", "SessionStart", "bmad", "p", project_dir=proj)
        rows = cs.list_hooks(project_dir=proj)
        scopes = sorted(r["scope"] for r in rows)
        assert scopes == ["global", "project"]

    def test_add_without_matcher_omits_key(self, sandbox):
        cs.add_hook("global", "SessionStart", "bmad", "cmd")
        block = cs.load("global")["hooks"]["SessionStart"][0]
        assert "matcher" not in block
