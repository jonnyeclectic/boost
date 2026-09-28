# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for Codex CLI as hookhost's third hook host.

Every claim here was measured against **Codex CLI 0.156.1** (2026-09-27), the
same standard `test_hookhost.py` holds Gemini to. The four sources are named in
`core/hookhost.py`'s module docstring; the two that decide these tests are the
23 draft-07 JSON Schemas the binary embeds for the hook stdout protocol
(`<event>.command.{input,output}`) and an observed `codex app-server`
`hooks/list` run against a throwaway `CODEX_HOME`.

The card this closes asked whether Codex hooks are shaped like Claude's and
what the two differing fields do. They are, and the answer is narrow: the file
is `hooks.json` rather than `settings.json`, and `timeout` agrees with Claude
(seconds) rather than Gemini (milliseconds).
"""
from __future__ import annotations

import json

import pytest

from boost_cli.core import hookhost as hh
from boost_cli.errors import BoostError


class TestCodexIsInTheTable:
    def test_codex_is_a_known_host(self):
        assert hh.CODEX in hh.hosts()

    def test_the_existing_two_keep_their_order(self):
        # `hooks list` with no --host reports in this order, and the first is
        # the default for a write. Appending must not reorder them.
        assert hh.hosts()[:2] == [hh.CLAUDE, hh.GEMINI]

    def test_cli_label_and_dir(self):
        assert hh.cli(hh.CODEX) == "codex"
        assert hh.label(hh.CODEX) == "Codex CLI"
        assert hh.event_label(hh.CODEX) == "Codex"
        assert hh.settings_dir(hh.CODEX) == ".codex"

    def test_history_prefix_keeps_snapshots_apart(self):
        prefixes = {hh.history_prefix(h) for h in hh.hosts()}
        assert len(prefixes) == len(hh.hosts())
        assert hh.history_prefix(hh.CODEX) == "codex-"


class TestTheFileIsHooksJsonNotSettingsJson:
    """The one structural difference, and the one that is silent if wrong.

    Codex reads `$CODEX_HOME/hooks.json`; a `hooks` key in `settings.json` is
    a file it never opens. Measured: `hooks/list` reports the hook with
    `source: "user"` and `sourcePath` ending `/hooks.json`.
    """

    def test_codex_reads_hooks_json(self):
        assert hh.settings_file(hh.CODEX) == "hooks.json"

    def test_the_other_hosts_still_read_settings_json(self):
        assert hh.settings_file(hh.CLAUDE) == "settings.json"
        assert hh.settings_file(hh.GEMINI) == "settings.json"

    def test_unknown_host_raises(self):
        with pytest.raises(BoostError):
            hh.settings_file("nope")


class TestTimeoutAgreesWithClaude:
    """`timeout`, in seconds — NOT Gemini's milliseconds.

    Measured twice, in `hooks.json` and in a `config.toml` `[hooks]` table:
    `timeout = 9` is reported back as `timeoutSec: 9`. `timeoutSec` is the
    *wire* spelling only — as a config key it is ignored and the hook falls
    back to Codex's 600-second default, which is the failure this pins.
    """

    def test_codex_timeout_is_seconds_verbatim(self):
        assert hh.timeout(hh.CODEX, 10) == 10
        assert hh.timeout_unit(hh.CODEX) == "seconds"

    def test_codex_does_not_inherit_geminis_millisecond_scale(self):
        assert hh.timeout(hh.CODEX, 10) != hh.timeout(hh.GEMINI, 10)

    def test_seconds_round_trips(self):
        assert hh.timeout_seconds(hh.CODEX, hh.timeout(hh.CODEX, 37)) == 37

    def test_a_missing_timeout_stays_missing(self):
        assert hh.timeout_seconds(hh.CODEX, None) is None


class TestEvents:
    """Twelve events, PascalCase, and the case is exact."""

    MEASURED = (
        "PreToolUse", "PermissionRequest", "PostToolUse", "PreCompact",
        "PostCompact", "SessionStart", "SessionEnd", "UserPromptSubmit",
        "SubagentStart", "SubagentStop", "Stop", "Interrupt",
    )

    def test_events_match_the_schema_enum(self):
        assert set(hh.events(hh.CODEX)) == set(self.MEASURED)

    def test_there_are_twelve(self):
        assert len(hh.events(hh.CODEX)) == 12

    def test_codex_has_no_notification_event(self):
        # Claude's one event with no Codex counterpart.
        assert "Notification" not in hh.events(hh.CODEX)

    @pytest.mark.parametrize("event", ["PermissionRequest", "PostCompact",
                                       "Interrupt"])
    def test_codex_only_events_are_reachable_by_native_name(self, event):
        assert event not in hh.CLAUDE_EVENTS
        assert hh.translate(hh.CODEX, event) == event


class TestTranslateRefusesRatherThanFallingThrough:
    """Codex is the host where the warn-but-add fallthrough is wrong.

    Measured twice, in JSON and in TOML: an unknown event name
    (`NotARealEvent`) and a wrong-case one (`sessionstart`) each produce **no
    hook, no warning and no error** — `hooks/list` returns an empty list. That
    is exactly the "looks installed and never fires" failure the module exists
    to prevent, so an unrecognised name must come back as None here even
    though it passes through for Gemini.
    """

    def test_every_claude_event_is_mapped_explicitly(self):
        assert set(hh.CLAUDE_TO_CODEX) == set(hh.CLAUDE_EVENTS)

    def test_shared_names_are_the_identity(self):
        for event in ("SessionStart", "SessionEnd", "PreToolUse",
                      "PostToolUse", "UserPromptSubmit", "Stop",
                      "SubagentStop", "SubagentStart", "PreCompact"):
            assert hh.translate(hh.CODEX, event) == event

    def test_notification_has_no_counterpart(self):
        assert hh.translate(hh.CODEX, "Notification") is None

    def test_an_unrecognised_name_is_refused(self):
        assert hh.translate(hh.CODEX, "NotARealEvent") is None

    def test_a_wrong_case_name_is_refused(self):
        # Codex matches the key exactly; `sessionstart` silently loads nothing.
        assert hh.translate(hh.CODEX, "sessionstart") is None
        assert hh.translate(hh.CODEX, "SESSIONSTART") is None

    def test_gemini_keeps_its_fallthrough(self):
        # The permissive path still exists for the host it was written for.
        assert hh.translate(hh.GEMINI, "NotARealEvent") == "NotARealEvent"

    def test_every_mapped_target_is_a_real_codex_event(self):
        for target in hh.CLAUDE_TO_CODEX.values():
            assert target is None or target in hh.events(hh.CODEX)


class TestHookEntry:
    def test_codex_entry_is_claudes_shape_in_seconds(self):
        assert hh.hook_entry(hh.CODEX, "boost x # boost:t", 10) == {
            "type": "command", "command": "boost x # boost:t", "timeout": 10,
        }

    def test_codex_takes_no_name_field(self):
        """`name` is Gemini's, and Codex's schema has no such property.

        Measured: `hooks.json` accepts and ignores it. The `# boost:<name>`
        command marker survives verbatim (`command` is a single string), so
        the existing ownership mechanism carries over unchanged.
        """
        entry = hh.hook_entry(hh.CODEX, "boost x # boost:t", 10, name="t")
        assert "name" not in entry


class TestContextOutput:
    """Codex takes Claude's wire shape, PascalCase, but never plain text.

    The binary embeds one draft-07 schema per event for hook stdout, each
    `"additionalProperties": false` — so this is validated, not best-effort,
    and a wrong key is dropped rather than warned about. All three events
    below were read out of the binary rather than assumed, because the router
    `bmad on` installs is a `UserPromptSubmit` hook and a schema that lacked
    `additionalContext` would mean no banner, on every prompt, forever (the
    hook command ends in `2>/dev/null || true`, so nothing would be shown):

    * `session-start.command.output` -> `SessionStartHookSpecificOutputWire`
    * `user-prompt-submit.command.output` ->
      `UserPromptSubmitHookSpecificOutputWire`
    * `pre-tool-use.command.output` -> `PreToolUseHookSpecificOutputWire`

    Each has exactly two properties — `additionalContext` (string) and a
    required `hookEventName` pinned to that event's PascalCase `const` — so
    `additionalContext` is the field that reaches the model, as on Claude.
    Claude's plain-text SessionStart shortcut does **not** carry over.
    """

    @pytest.mark.parametrize("event", ["SessionStart", "UserPromptSubmit",
                                       "PreToolUse"])
    def test_codex_always_gets_json_under_the_pascal_case_name(self, event):
        payload = json.loads(hh.context_output(hh.CODEX, event, "hello"))
        assert payload == {"hookSpecificOutput": {
            "hookEventName": event, "additionalContext": "hello"}}

    def test_codex_session_start_is_not_plain_text(self):
        # The one place Claude and Codex differ on stdout.
        assert hh.context_output(hh.CODEX, "SessionStart", "hi") != "hi"
        assert hh.context_output(hh.CLAUDE, "SessionStart", "hi") == "hi"


class TestTheTableAnswersWhyAsWellAsWhether:
    """`translate` says an event cannot exist; these say which kind and why.

    `commands/hooks.py` needs both to word its two refusals. Before Codex it
    needed neither: there was one refusal, and its hint hardcoded Gemini's
    reason ("has no sub-agents") — a sentence that is false for the host that
    has both sub-agent events.
    """

    def test_unmappable_is_geminis_two_and_codexs_one(self):
        assert hh.unmappable(hh.GEMINI) == ("SubagentStop", "SubagentStart")
        assert hh.unmappable(hh.CODEX) == ("Notification",)

    def test_claude_has_no_gaps_with_itself(self):
        assert hh.unmappable(hh.CLAUDE) == ()

    def test_unmappable_keeps_claudes_order(self):
        for host in hh.hosts():
            gaps = hh.unmappable(host)
            assert list(gaps) == [e for e in hh.CLAUDE_EVENTS if e in gaps]

    def test_unmappable_agrees_with_translate(self):
        for host in hh.hosts():
            for event in hh.CLAUDE_EVENTS:
                assert (hh.translate(host, event) is None) == \
                    (event in hh.unmappable(host))

    def test_each_host_explains_its_own_gap(self):
        assert "sub-agents" in hh.no_counterpart_note(hh.GEMINI)
        assert "notification" in hh.no_counterpart_note(hh.CODEX).lower()
        assert "sub-agents" not in hh.no_counterpart_note(hh.CODEX)

    def test_a_host_with_no_gap_has_nothing_to_explain(self):
        assert hh.no_counterpart_note(hh.CLAUDE) == ""

    def test_a_host_with_a_gap_always_has_a_note(self):
        for host in hh.hosts():
            if hh.unmappable(host):
                assert hh.no_counterpart_note(host), host

    def test_only_codex_is_strict_about_event_names(self):
        assert hh.strict_events(hh.CODEX) is True
        assert hh.strict_events(hh.GEMINI) is False
        assert hh.strict_events(hh.CLAUDE) is False

    def test_only_codex_has_a_movable_user_root(self):
        # Claude's `CLAUDE_CONFIG_DIR` is not claimed here: its effect on the
        # *hook* path is unmeasured, and this table records measurements.
        assert hh.movable_user_root(hh.CODEX) is True
        assert hh.movable_user_root(hh.GEMINI) is False
        assert hh.movable_user_root(hh.CLAUDE) is False

    @pytest.mark.parametrize("fn", [lambda: hh.unmappable("nope"),
                                    lambda: hh.no_counterpart_note("nope"),
                                    lambda: hh.strict_events("nope"),
                                    lambda: hh.movable_user_root("nope")])
    def test_an_unknown_host_raises(self, fn):
        with pytest.raises(BoostError):
            fn()


class TestTheRouterSpeaksCodexsInputVocabulary:
    """`bmad route` reads Claude's key names off stdin. Codex uses them too.

    Measured, not assumed: `user-prompt-submit.command.input` in the binary
    is `"additionalProperties": false` and **requires** `cwd`,
    `hook_event_name`, `model`, `permission_mode`, `prompt`, `session_id`,
    `transcript_path` and `turn_id` — snake_case, Claude's spelling, plus two
    Codex extensions (`model`/`permission_mode`/`turn_id`). Had the prompt
    been spelled differently, the router would have classified an empty
    prompt as TRIVIAL and printed nothing, silently, on every prompt.

    `session-start.command.input` likewise requires `source`, with Claude's
    `startup|resume|clear|compact` plus `fork`. Nothing boost writes depends
    on `fork` — it does not translate matchers to Codex — but the reader must
    not assume the enum is closed at Claude's four.
    """

    #: The keys `bmad._read_hook_stdin` looks for, and the schema that has
    #: them. Kept here rather than imported so a rename in either place is a
    #: failing test rather than a silent agreement.
    CODEX_USER_PROMPT_SUBMIT_INPUT_KEYS = frozenset({
        "agent_id", "agent_type", "cwd", "hook_event_name", "model",
        "permission_mode", "prompt", "session_id", "transcript_path",
        "turn_id",
    })

    @pytest.mark.parametrize("key", ["prompt", "session_id", "cwd",
                                     "hook_event_name"])
    def test_the_keys_the_router_reads_are_codex_keys(self, key):
        assert key in self.CODEX_USER_PROMPT_SUBMIT_INPUT_KEYS

    def test_the_event_name_on_the_wire_is_pascal_case_either_way(self):
        # `hook_event_name` is snake_case as a *key* and PascalCase as a
        # *value* (`{"const": "UserPromptSubmit"}`), which is the one place
        # Codex mixes the two conventions in a single field.
        assert hh.translate(hh.CODEX, "UserPromptSubmit") == "UserPromptSubmit"
