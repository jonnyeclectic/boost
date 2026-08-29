# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Which agent CLIs can boost install *hooks* into, and how they differ.

``boost hooks`` used to speak Claude Code and nothing else. Gemini CLI grew a
hook system too, and — like the MCP grammars in :mod:`boost_cli.core.mcphost` —
the two agree on the *concept* while disagreeing on details that are silent
when you get them wrong. A hook written to the wrong schema is worse than no
hook: it looks installed and never fires. So this is the table of those
differences, kept pure and I/O-free (like :mod:`mcphost`) so every branch is
unit testable and reachable by the mutation gate; the command layer does the
file work through :mod:`boost_cli.core.claude_settings`.

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
"""
from __future__ import annotations

from ..errors import BoostError

CLAUDE = "claude"
GEMINI = "gemini"

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

# name -> host facts. Order is the order hosts are reported in.
#
# ``events_label`` is the *event namespace* name, not the product name: it is
# interpolated into "not a known %s hook event", where "Claude Code hook event"
# would read as a product rather than a vocabulary.
#
# ``history_prefix`` keeps the two hosts' settings snapshots apart in
# ``~/.boost/state/claude-settings-history/``, which names files
# ``<prefix><scope>-<stamp>.json``. Claude's prefix is empty so its existing
# filenames stay byte-identical.
HOSTS: dict[str, dict] = {
    CLAUDE: {
        "cli": "claude",
        "label": "Claude Code",
        "events_label": "Claude",
        "dir": ".claude",
        "events": CLAUDE_EVENTS,
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
        "events": GEMINI_EVENTS,
        "timeout_scale": 1000,
        "timeout_unit": "milliseconds",
        "history_prefix": "gemini-",
        "names_hooks": True,
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


def history_prefix(host: str) -> str:
    """Filename prefix for ``host``'s settings snapshots. Claude's is empty."""
    return str(_spec(host)["history_prefix"])


def events(host: str) -> tuple[str, ...]:
    """``host``'s known hook events."""
    return tuple(_spec(host)["events"])


def timeout_unit(host: str) -> str:
    """What ``host``'s ``timeout`` field is measured in."""
    return str(_spec(host)["timeout_unit"])


def timeout(host: str, seconds: int) -> int:
    """``seconds`` expressed in ``host``'s own timeout units.

    Claude's field is seconds, so this is the identity for it and the existing
    settings.json bytes are unchanged. Gemini's is milliseconds.
    """
    return seconds * int(_spec(host)["timeout_scale"])


def translate(host: str, event: str) -> str | None:
    """``event`` spelled the way ``host`` spells it.

    Returns ``None`` only for an event that is known to have **no** counterpart
    on ``host`` — the caller must say so rather than dropping the hook. An
    event already native to ``host``, and any name neither host recognises,
    passes through unchanged so the warn-but-add path keeps working.
    """
    _spec(host)
    if host == CLAUDE or event in GEMINI_EVENTS:
        return event
    if event in CLAUDE_TO_GEMINI:
        return CLAUDE_TO_GEMINI[event]
    return event


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
