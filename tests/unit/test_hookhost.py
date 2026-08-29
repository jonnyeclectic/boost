# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests for core/hookhost.py — the per-host hook table.

Every claim here was established against Gemini CLI 0.57.0's own bundle
(`@google/gemini-cli/bundle`): its shipped `docs/hooks/*.md`, its
`HookEventName` enum and `EVENT_MAPPING` table in the bundled JS, and an
observed `gemini hooks migrate --from-claude` run. See the module docstring.
"""
from __future__ import annotations

import pytest

from boost_cli.core import hookhost as hh
from boost_cli.errors import BoostError


class TestTable:
    def test_hosts_are_claude_then_gemini(self):
        assert hh.hosts() == ["claude", "gemini"]

    def test_cli_names(self):
        assert hh.cli(hh.CLAUDE) == "claude"
        assert hh.cli(hh.GEMINI) == "gemini"

    def test_labels(self):
        assert hh.label(hh.CLAUDE) == "Claude Code"
        assert hh.label(hh.GEMINI) == "Gemini CLI"

    def test_settings_dirs_differ(self):
        assert hh.settings_dir(hh.CLAUDE) == ".claude"
        assert hh.settings_dir(hh.GEMINI) == ".gemini"

    def test_event_label_keeps_claude_wording(self):
        # `boost hooks add` interpolates this into "not a known %s hook event";
        # "Claude Code hook event" would read wrong for an event namespace.
        assert hh.event_label(hh.CLAUDE) == "Claude"
        assert hh.event_label(hh.GEMINI) == "Gemini"

    def test_unknown_host_raises_boost_error(self):
        for fn in (hh.cli, hh.label, hh.settings_dir, hh.event_label,
                   hh.events, hh.history_prefix):
            with pytest.raises(BoostError):
                fn("emacs")


class TestResolve:
    def test_none_and_auto_mean_every_host(self):
        assert hh.resolve(None) == hh.hosts()
        assert hh.resolve("auto") == hh.hosts()
        assert hh.resolve("") == hh.hosts()

    def test_named_host_selects_one(self):
        assert hh.resolve("gemini") == ["gemini"]

    def test_unknown_host_raises(self):
        with pytest.raises(BoostError):
            hh.resolve("emacs")


class TestTimeout:
    def test_claude_timeout_is_seconds_verbatim(self):
        # Claude Code's hook `timeout` field is seconds; boost's --timeout is
        # seconds, so the conversion is the identity and must stay so — the
        # existing settings.json bytes depend on it.
        assert hh.timeout(hh.CLAUDE, 10) == 10
        assert hh.timeout(hh.CLAUDE, 1) == 1

    def test_gemini_timeout_is_milliseconds(self):
        # bundle chunk-S3MXVTTY.js: `DEFAULT_HOOK_TIMEOUT = 6e4` and
        # `setTimeout(... , timeout)` rejecting with "Hook timed out after
        # ${timeout}ms". A verbatim 10 would be ten milliseconds.
        assert hh.timeout(hh.GEMINI, 10) == 10_000
        assert hh.timeout(hh.GEMINI, 1) == 1000

    def test_timeout_unit_names_the_units(self):
        assert hh.timeout_unit(hh.CLAUDE) == "seconds"
        assert hh.timeout_unit(hh.GEMINI) == "milliseconds"

    def test_unknown_host_timeout_raises(self):
        with pytest.raises(BoostError):
            hh.timeout("emacs", 10)


class TestEvents:
    def test_claude_events_include_the_lifecycle_set(self):
        for ev in ("SessionStart", "PreToolUse", "PostToolUse", "PreCompact"):
            assert ev in hh.events(hh.CLAUDE)

    def test_gemini_events_match_the_bundled_enum(self):
        # bundle chunk-S3MXVTTY.js, `var HookEventName` — all eleven, verbatim.
        assert set(hh.events(hh.GEMINI)) == {
            "BeforeTool", "AfterTool", "BeforeAgent", "Notification",
            "AfterAgent", "SessionStart", "SessionEnd", "PreCompress",
            "BeforeModel", "AfterModel", "BeforeToolSelection",
        }

    def test_gemini_has_no_claude_only_event_names(self):
        for ev in ("PreToolUse", "PostToolUse", "UserPromptSubmit", "Stop",
                   "PreCompact"):
            assert ev not in hh.events(hh.GEMINI)


class TestEventMapping:
    def test_every_claude_event_is_mapped_explicitly(self):
        # The point of the table: no Claude event may fall through unnoticed.
        assert set(hh.CLAUDE_TO_GEMINI) == set(hh.events(hh.CLAUDE))

    def test_mapping_matches_gemini_own_migrate_table(self):
        assert hh.CLAUDE_TO_GEMINI["PreToolUse"] == "BeforeTool"
        assert hh.CLAUDE_TO_GEMINI["PostToolUse"] == "AfterTool"
        assert hh.CLAUDE_TO_GEMINI["UserPromptSubmit"] == "BeforeAgent"
        assert hh.CLAUDE_TO_GEMINI["Stop"] == "AfterAgent"
        assert hh.CLAUDE_TO_GEMINI["PreCompact"] == "PreCompress"
        assert hh.CLAUDE_TO_GEMINI["SessionStart"] == "SessionStart"
        assert hh.CLAUDE_TO_GEMINI["SessionEnd"] == "SessionEnd"
        assert hh.CLAUDE_TO_GEMINI["Notification"] == "Notification"

    def test_subagent_events_have_no_counterpart(self):
        # Gemini has no sub-agents. Upstream's own EVENT_MAPPING keys
        # "SubAgentStop" (capital A), which Claude Code never emits, so
        # `gemini hooks migrate` writes the unmapped "SubagentStop" straight
        # into settings.json — an event the CLI can never fire. boost says no.
        assert hh.CLAUDE_TO_GEMINI["SubagentStop"] is None
        assert hh.CLAUDE_TO_GEMINI["SubagentStart"] is None

    def test_every_mapped_target_is_a_real_gemini_event(self):
        for target in hh.CLAUDE_TO_GEMINI.values():
            if target is not None:
                assert target in hh.events(hh.GEMINI)


class TestTranslate:
    def test_claude_is_the_identity(self):
        assert hh.translate(hh.CLAUDE, "PreToolUse") == "PreToolUse"
        assert hh.translate(hh.CLAUDE, "SubagentStop") == "SubagentStop"

    def test_gemini_native_names_pass_through(self):
        assert hh.translate(hh.GEMINI, "BeforeTool") == "BeforeTool"
        assert hh.translate(hh.GEMINI, "BeforeToolSelection") == "BeforeToolSelection"

    def test_gemini_translates_claude_names(self):
        assert hh.translate(hh.GEMINI, "PreToolUse") == "BeforeTool"
        assert hh.translate(hh.GEMINI, "PreCompact") == "PreCompress"

    def test_gemini_returns_none_for_an_unbridgeable_event(self):
        assert hh.translate(hh.GEMINI, "SubagentStop") is None

    def test_an_unrecognised_name_passes_through_unchanged(self):
        # Not our job to reject it — the command layer warns and adds anyway,
        # exactly as it always has for Claude.
        assert hh.translate(hh.GEMINI, "Frobnicate") == "Frobnicate"
        assert hh.translate(hh.CLAUDE, "Frobnicate") == "Frobnicate"

    def test_unknown_host_raises(self):
        with pytest.raises(BoostError):
            hh.translate("emacs", "SessionStart")


class TestHookEntry:
    def test_claude_entry_shape_is_unchanged(self):
        e = hh.hook_entry(hh.CLAUDE, "cmd # boost:n", 10, name="n")
        assert e == {"type": "command", "command": "cmd # boost:n", "timeout": 10}
        assert list(e) == ["type", "command", "timeout"]   # key order matters

    def test_gemini_entry_converts_timeout_and_names_the_hook(self):
        e = hh.hook_entry(hh.GEMINI, "cmd # boost:n", 10, name="n")
        assert e["timeout"] == 10_000
        assert e["type"] == "command"
        # Gemini's optional `name` field is what `/hooks enable <name>` and the
        # `/hooks panel` display use; Claude Code has no such field.
        assert e["name"] == "boost:n"

    def test_gemini_entry_without_a_name_omits_the_field(self):
        assert "name" not in hh.hook_entry(hh.GEMINI, "cmd", 5)

    def test_history_prefixes_keep_the_two_hosts_apart(self):
        # claude_settings.save() snapshots to "<prefix><scope>-<stamp>.json";
        # Claude's filenames predate this and must not move.
        assert hh.history_prefix(hh.CLAUDE) == ""
        assert hh.history_prefix(hh.GEMINI) == "gemini-"
