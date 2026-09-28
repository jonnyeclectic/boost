# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Which agent CLIs can boost install *hooks* into, and how they differ.

``boost hooks`` used to speak Claude Code and nothing else. Gemini CLI grew a
hook system, then Codex CLI grew one, and — like the MCP grammars in
:mod:`boost_cli.core.mcphost` — they agree on the *concept* while disagreeing
on details that are silent when you get them wrong. A hook written to the wrong
schema is worse than no hook: it looks installed and never fires. So this is
the table of those differences, kept pure and I/O-free (like :mod:`mcphost`) so
every branch is unit testable and reachable by the mutation gate; the command
layer does the file work through :mod:`boost_cli.core.claude_settings`.

Everything below was established against **Gemini CLI 0.57.0**, three ways that
agree — the bundle at ``@google/gemini-cli/bundle`` ships its own docs, and the
bundled JS is the code that actually reads the file:

* ``bundle/docs/hooks/{index,reference}.md`` — the configuration schema table.
* ``bundle/chunk-S3MXVTTY.js`` — ``var HookEventName`` (the eleven events),
  ``DEFAULT_HOOK_TIMEOUT = 6e4``, and ``Storage.getGlobalGeminiDir()``.
* ``bundle/gemini-OYYGXMHL.js`` — ``EVENT_MAPPING`` in
  ``packages/cli/src/commands/hooks/migrate.ts``, upstream's own Claude→Gemini
  event table.
* An observed ``gemini hooks migrate --from-claude`` run against a throwaway
  ``HOME`` and cwd, which confirmed the written bytes.

The four ways the two hosts differ, all of them load-bearing:

* **Where the file lives.** ``~/.claude/settings.json`` versus
  ``~/.gemini/settings.json``; project scope is ``.claude/`` versus
  ``.gemini/`` under the cwd. The ``hooks`` key and the
  ``{matcher, hooks: [{type, command, timeout}]}`` block shape are otherwise
  identical, which is exactly why the difference is easy to miss.
* **Timeout units.** Claude's ``timeout`` is **seconds**; Gemini's is
  **milliseconds** (``setTimeout(…, timeout)``, rejecting with "Hook timed out
  after ${timeout}ms", default 60000). boost's ``--timeout`` is seconds, so a
  verbatim copy would give a Gemini hook ten *milliseconds* to run. Upstream's
  own ``migrate`` does copy it verbatim; boost converts.
* **Event names.** Only ``SessionStart``, ``SessionEnd`` and ``Notification``
  are spelled the same. See :data:`CLAUDE_TO_GEMINI`.
* **The ``name`` field.** Gemini's hook config takes an optional ``name``,
  which is what ``/hooks panel`` displays and ``/hooks enable <name>`` targets.
  Claude Code has no such field, so boost's ``# boost:<name>`` command marker
  stays the ownership mechanism for both hosts and ``name`` is added on top for
  Gemini rather than replacing it.

Matchers are deliberately **not** translated. Upstream's ``migrate`` rewrites
Claude tool names inside a matcher (``Bash`` → ``run_shell_command``) because it
is porting an existing config; ``boost hooks add`` is not porting anything, so a
matcher is passed through host-native — a Gemini tool matcher is a regex over
Gemini's tool names, and a lifecycle matcher is an exact string.

Codex CLI is the third host, established against **0.156.1** (2026-09-27), four
sources that agree — none of them a guess, by the same standard the Gemini
section above is held to:

* ``codex app-server generate-json-schema`` — the generated protocol schema
  (643 definitions, 23 of them hook types: ``HookEventName``,
  ``ConfiguredHookHandler``, ``HookTrustStatus``, ``HookSource``,
  ``ManagedHooksRequirements``).
* ``strings -a -n 5 /Applications/ChatGPT.app/Contents/Resources/codex`` — the
  ``hooks/src/**`` module names, the verbatim skip warnings and
  ``tui/src/startup_hooks_review.rs``'s trust prompt.
* Observed ``codex app-server`` runs over stdio JSON-RPC (``initialize`` ->
  ``initialized`` -> ``hooks/list``) against throwaway ``CODEX_HOME``s, which
  is what measured every "silently drops" claim below.
* The **23 draft-07 JSON Schemas the binary embeds** for hook stdout, titled
  ``<event>.command.{input,output}`` and loaded by
  ``hooks/src/engine/schema_loader.rs``.

Codex agrees with Claude on the two things Gemini disagrees about and disagrees
about two of its own:

* **The filename.** ``$CODEX_HOME/hooks.json``, not ``settings.json`` — hence
  :data:`HOSTS`'s ``file`` key. A ``hooks`` key written into a Codex
  ``settings.json`` is a file the CLI never opens. (A ``[hooks]`` table in
  ``config.toml`` is an equivalent representation; Codex loads both when both
  exist and warns "prefer a single representation for this layer", so boost
  writes exactly one of them.)
* **The user-scope root moves.** ``$CODEX_HOME`` relocates it, resolved by
  :func:`boost_cli.core.mcphost.config_home` — the same grammar the MCP host
  already measured, including that a *relative* value is honoured against the
  cwd. The **project** root is the literal ``<project>/.codex`` whatever
  ``CODEX_HOME`` says. Hence ``movable_user_root``.
* **Timeout is seconds**, like Claude and unlike Gemini. ``timeoutSec`` is the
  wire spelling only: as a config key it is ignored and the hook silently falls
  back to Codex's 600-second default.
* **Event names are Claude's, PascalCase, matched exactly** — plus
  ``PermissionRequest``, ``PostCompact`` and ``Interrupt``, minus
  ``Notification``. There is **no warn-but-add path here**: an unknown name
  (``NotARealEvent``) and a wrong-case one (``sessionstart``) each produce no
  hook, no warning and no error, measured in both JSON and TOML. That is the
  "looks installed and never fires" failure this module exists to prevent, so
  ``strict_events`` makes :func:`translate` refuse instead of falling through.

Two Codex facts shape the *writer* rather than this table, and are stated here
because the next person will look for them here first. A hook's identity is
``<sourcePath>:<snake_case_event>:<group_index>:<handler_index>`` — **position
is identity** — so a re-add must replace its block in place; removing and
appending re-keys every later hook and voids the user's trust grant on each
(measured: an untouched neighbour moved ``:0:0`` -> ``:1:0``). And an untrusted
hook does not run, but it is not silent: Codex prompts at startup ("Hooks need
review", "Trust all and continue"), and a project-scope hook additionally needs
the repo marked ``trust_level = "trusted"`` or ``hooks/list`` returns an empty
list with no warning at all.
"""
from __future__ import annotations

import json

from ..errors import BoostError

CLAUDE = "claude"
GEMINI = "gemini"
CODEX = "codex"

# Claude Code's hook events. Permissive by design — an unrecognised name is
# warned about and added anyway, so a new upstream event is usable the day it
# ships rather than the day boost notices.
CLAUDE_EVENTS = (
    "SessionStart", "SessionEnd", "UserPromptSubmit", "PreToolUse", "PostToolUse",
    "Stop", "SubagentStop", "SubagentStart", "PreCompact", "Notification",
)

# Gemini CLI's hook events — `var HookEventName` in the bundle, verbatim.
GEMINI_EVENTS = (
    "BeforeTool", "AfterTool", "BeforeAgent", "Notification", "AfterAgent",
    "SessionStart", "SessionEnd", "PreCompress", "BeforeModel", "AfterModel",
    "BeforeToolSelection",
)

#: Claude event -> Gemini event, or ``None`` where there is no counterpart.
#:
#: Every entry of :data:`CLAUDE_EVENTS` appears here explicitly — a Claude
#: event that fell through unnoticed is the failure this table exists to
#: prevent, and ``tests/unit/test_hookhost.py`` fails the build if one does.
#:
#: The ``None``s are Claude's sub-agent lifecycle, which Gemini has no concept
#: of. Upstream's own ``EVENT_MAPPING`` tries to fold it into ``AfterAgent``,
#: but keys it ``"SubAgentStop"`` — a spelling Claude Code never emits — so
#: ``gemini hooks migrate`` copies the real ``SubagentStop`` through unmapped
#: and writes an event the CLI can never fire. Observed, not inferred. boost
#: refuses the hook and says why instead.
CLAUDE_TO_GEMINI: dict[str, str | None] = {
    "SessionStart": "SessionStart",
    "SessionEnd": "SessionEnd",
    "UserPromptSubmit": "BeforeAgent",
    "PreToolUse": "BeforeTool",
    "PostToolUse": "AfterTool",
    "Stop": "AfterAgent",
    "SubagentStop": None,
    "SubagentStart": None,
    "PreCompact": "PreCompress",
    "Notification": "Notification",
}

# Codex CLI's hook events — the `HookEventName` enum in the generated protocol
# schema, verbatim. Nine are spelled exactly as Claude spells them; the three
# that are not (`PermissionRequest`, `PostCompact`, `Interrupt`) have no Claude
# counterpart and are reachable only by their own name.
#
# `ManagedHooksRequirements` lists all twelve but marks only ten `required`
# (`Interrupt` and `SessionEnd` carry `default: []`). That asymmetry describes
# what a *managed* config must enumerate, not which events fire, so it is not
# a reason to shorten this list.
CODEX_EVENTS = (
    "PreToolUse", "PermissionRequest", "PostToolUse", "PreCompact",
    "PostCompact", "SessionStart", "SessionEnd", "UserPromptSubmit",
    "SubagentStart", "SubagentStop", "Stop", "Interrupt",
)

#: Claude event -> Codex event, or ``None`` where there is no counterpart.
#:
#: Explicit like :data:`CLAUDE_TO_GEMINI`, and for the same reason: a Claude
#: event that fell through unnoticed is what this table prevents. Nine are the
#: identity — Codex borrowed Claude's vocabulary, including the sub-agent
#: lifecycle Gemini has no concept of — and ``Notification`` is the one Claude
#: event Codex does not have.
CLAUDE_TO_CODEX: dict[str, str | None] = {
    "SessionStart": "SessionStart",
    "SessionEnd": "SessionEnd",
    "UserPromptSubmit": "UserPromptSubmit",
    "PreToolUse": "PreToolUse",
    "PostToolUse": "PostToolUse",
    "Stop": "Stop",
    "SubagentStop": "SubagentStop",
    "SubagentStart": "SubagentStart",
    "PreCompact": "PreCompact",
    "Notification": None,
}

# name -> host facts. Order is the order hosts are reported in.
#
# ``events_label`` is the *event namespace* name, not the product name: it is
# interpolated into "not a known %s hook event", where "Claude Code hook event"
# would read as a product rather than a vocabulary.
#
# ``history_prefix`` keeps the hosts' settings snapshots apart in
# ``~/.boost/state/claude-settings-history/``, which names files
# ``<prefix><scope>-<stamp>.json``. Claude's prefix is empty so its existing
# filenames stay byte-identical.
#
# ``file`` is the settings filename, because Codex's is ``hooks.json`` where
# the other two are ``settings.json``; ``movable_user_root`` says the
# user-scope root is an environment variable away from ``$HOME/<dir>``;
# ``strict_events`` says an unrecognised event name must be refused rather
# than passed through; ``claude_map`` is the host's own Claude-event
# translation table (``None`` for Claude, which needs none); and
# ``no_counterpart_note`` is the one clause explaining *why* some Claude event
# cannot exist here. That last one is a per-host fact and not a shared one:
# "%s has no sub-agents" was hardcoded into the refusal in ``commands/hooks.py``
# and is false for Codex, which has both sub-agent events and no
# ``Notification``.
HOSTS: dict[str, dict] = {
    CLAUDE: {
        "cli": "claude",
        "label": "Claude Code",
        "events_label": "Claude",
        "dir": ".claude",
        "file": "settings.json",
        "events": CLAUDE_EVENTS,
        "claude_map": None,
        "no_counterpart_note": "",
        "strict_events": False,
        "movable_user_root": False,
        "timeout_scale": 1,
        "timeout_unit": "seconds",
        "history_prefix": "",
        "names_hooks": False,
    },
    GEMINI: {
        "cli": "gemini",
        "label": "Gemini CLI",
        "events_label": "Gemini",
        "dir": ".gemini",
        "file": "settings.json",
        "events": GEMINI_EVENTS,
        "claude_map": CLAUDE_TO_GEMINI,
        "no_counterpart_note": "Gemini CLI has no sub-agents",
        "strict_events": False,
        "movable_user_root": False,
        "timeout_scale": 1000,
        "timeout_unit": "milliseconds",
        "history_prefix": "gemini-",
        "names_hooks": True,
    },
    CODEX: {
        "cli": "codex",
        "label": "Codex CLI",
        "events_label": "Codex",
        "dir": ".codex",
        "file": "hooks.json",
        "events": CODEX_EVENTS,
        "claude_map": CLAUDE_TO_CODEX,
        "no_counterpart_note": "Codex CLI has no notification event",
        "strict_events": True,
        "movable_user_root": True,
        "timeout_scale": 1,
        "timeout_unit": "seconds",
        "history_prefix": "codex-",
        "names_hooks": False,
    },
}


def hosts() -> list[str]:
    """Known hook host ids, in report order."""
    return list(HOSTS)


def _spec(host: str) -> dict:
    """The table row for ``host``, or a BoostError naming the alternatives."""
    try:
        return HOSTS[host]
    except KeyError:
        raise BoostError(
            "unknown hook host %r" % host,
            hint="use one of: %s" % ", ".join(hosts())) from None


def cli(host: str) -> str:
    """The executable name for ``host`` (``gemini`` -> "gemini")."""
    return str(_spec(host)["cli"])


def label(host: str) -> str:
    """Display name for ``host`` (``gemini`` -> "Gemini CLI")."""
    return str(_spec(host)["label"])


def event_label(host: str) -> str:
    """Name of ``host``'s event *vocabulary* (``claude`` -> "Claude")."""
    return str(_spec(host)["events_label"])


def settings_dir(host: str) -> str:
    """The dotdir holding ``host``'s settings.json (``.claude`` / ``.gemini``)."""
    return str(_spec(host)["dir"])


def settings_file(host: str) -> str:
    """The filename inside :func:`settings_dir` that ``host`` reads hooks from.

    ``settings.json`` for Claude Code and Gemini CLI; Codex reads
    ``hooks.json`` and never opens a ``settings.json``.
    """
    return str(_spec(host)["file"])


def movable_user_root(host: str) -> bool:
    """Whether ``host``'s *user*-scope root is relocatable by the environment.

    True only for Codex, whose ``$CODEX_HOME`` moves it. Project scope is never
    movable — Codex's repo root is the literal ``<project>/.codex`` — so a
    caller must apply this to the global scope alone.
    """
    return bool(_spec(host)["movable_user_root"])


def no_counterpart_note(host: str) -> str:
    """Why some Claude event cannot exist on ``host``, in one clause.

    Empty for Claude, which is the vocabulary the others are mapped from. The
    two answers differ in kind, which is why this is a table entry rather than
    one sentence at the call site: Gemini's gap is the sub-agent lifecycle and
    Codex's is ``Notification``.
    """
    return str(_spec(host)["no_counterpart_note"])


def unmappable(host: str) -> tuple[str, ...]:
    """The Claude events with no counterpart on ``host``, in Claude's order."""
    mapping = _spec(host)["claude_map"] or {}
    return tuple(e for e in CLAUDE_EVENTS if e in mapping and mapping[e] is None)


def strict_events(host: str) -> bool:
    """Whether ``host`` silently ignores an event name it does not know.

    True for Codex, where an unknown or wrong-case key produces no hook, no
    warning and no error, so boost must refuse rather than write one. False for
    the two hosts whose warn-but-add path is safe.
    """
    return bool(_spec(host)["strict_events"])


def history_prefix(host: str) -> str:
    """Filename prefix for ``host``'s settings snapshots. Claude's is empty."""
    return str(_spec(host)["history_prefix"])


def events(host: str) -> tuple[str, ...]:
    """``host``'s known hook events."""
    return tuple(_spec(host)["events"])


def timeout_unit(host: str) -> str:
    """What ``host``'s ``timeout`` field is measured in."""
    return str(_spec(host)["timeout_unit"])


def timeout_seconds(host: str, native: int | None) -> int | None:
    """``native`` (a value read from ``host``'s settings) back in seconds.

    The inverse of :func:`timeout`, for the readers rather than the writers —
    ``hooks list`` reports what is stored, and the stored number means
    different things per host. A consumer comparing a Claude hook's ``10``
    against a Gemini hook's ``10000`` would otherwise read the same
    ``--timeout 10`` as two very different settings.

    ``None`` in, ``None`` out: a hook block written without a timeout has
    none, and reporting ``0`` would describe a hook that gives up instantly.
    """
    if native is None:
        return None
    return int(native) // int(_spec(host)["timeout_scale"])


def timeout(host: str, seconds: int) -> int:
    """``seconds`` expressed in ``host``'s own timeout units.

    Claude's field is seconds, so this is the identity for it and the existing
    settings.json bytes are unchanged. Gemini's is milliseconds.
    """
    return seconds * int(_spec(host)["timeout_scale"])


def translate(host: str, event: str) -> str | None:
    """``event`` spelled the way ``host`` spells it, or ``None`` if it cannot be.

    An event already native to ``host`` passes through unchanged, and a Claude
    event with a counterpart is mapped by the host's own ``claude_map``.

    ``None`` means the caller must refuse the hook and say why, and it arrives
    two ways. A Claude event **known** to have no counterpart maps to ``None``
    explicitly (Gemini has no sub-agents; Codex has no ``Notification``). And
    on a ``strict_events`` host an *unrecognised* name is ``None`` too, because
    Codex drops such a key with no warning and no error — the warn-but-add
    fallthrough that is right for Gemini would write a hook that never fires.
    """
    spec = _spec(host)
    if host == CLAUDE or event in spec["events"]:
        return event
    mapping = spec["claude_map"]
    if mapping is not None and event in mapping:
        target: str | None = mapping[event]
        return target
    return None if spec["strict_events"] else event


def hook_entry(host: str, command: str, seconds: int,
               name: str = "") -> dict:
    """The inner hook config ``host`` reads, for an already-tagged ``command``.

    Key order is fixed: Claude's entries have been ``{type, command, timeout}``
    since boost first wrote one, and a reordered dict rewrites every user's
    settings.json for no reason on the next save.
    """
    entry: dict = {
        "type": "command",
        "command": command,
        "timeout": timeout(host, seconds),
    }
    if name and _spec(host)["names_hooks"]:
        # Gemini surfaces this in `/hooks panel` and takes it as the argument
        # to `/hooks enable|disable <name>`. Namespaced so a user scanning the
        # panel can see at a glance which hooks are boost's.
        entry["name"] = "boost:%s" % name
    return entry


def resolve(requested: str | None) -> list[str]:
    """Which hosts a ``--host`` value selects, validated.

    ``None``, ``""`` or ``"auto"`` means every known host — what the read-only
    ``list`` action wants. Anything else must name exactly one known host,
    because adding or removing a hook is a write and must not fan out.
    """
    if requested in (None, "", "auto"):
        return hosts()
    _spec(str(requested))
    return [str(requested)]


def context_output(host: str, event: str, text: str) -> str:
    """What a hook prints to hand ``text`` to the model, for a Claude ``event``.

    The two hosts read hook stdout differently, and the difference is silent.
    Claude Code adds a `SessionStart` hook's plain stdout to the context, and
    takes `UserPromptSubmit` context from ``hookSpecificOutput``. Gemini CLI
    turns any non-JSON stdout into ``{decision: "allow", systemMessage: text}``
    — shown to the *user* — and adds only ``additionalContext`` to the model's
    history. So boost's session briefing, printed as text, reached Gemini users
    as a 26-line info message and never reached the model at all (measured
    against Gemini CLI 0.57.0's hook runner: ``systemMessage`` 1,297 chars,
    ``additionalContext`` 0).

    Claude's bytes are unchanged. Gemini always gets JSON, under its own name
    for the event.
    """
    if host == CLAUDE and event == "SessionStart":
        return text
    return json.dumps({"hookSpecificOutput": {
        "hookEventName": translate(host, event),
        "additionalContext": text,
    }})
