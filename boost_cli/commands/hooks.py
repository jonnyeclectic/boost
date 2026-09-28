# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""boost hooks — scope- and host-aware management of agent hooks.

    boost hooks add SessionStart --command 'boost bmad orient' --name bmad \
        --scope global --matcher 'startup|resume|clear'
    boost hooks add PreToolUse --host gemini -c 'boost check' -n guard
    boost hooks add SessionStart --host codex -c 'boost bmad orient' -n bmad
    boost hooks list
    boost hooks remove --name bmad

Three hosts have hooks: Claude Code (`~/.claude/settings.json`, the default and
unchanged), Gemini CLI (`~/.gemini/settings.json`) and Codex CLI
(`$CODEX_HOME/hooks.json` — a different filename, and a root the environment
can move). What differs between them is a pure table in core/hookhost.py; this
layer only picks a host, spells the event the way that host spells it, and
reports what it did.

Event names differ, so `--host` accepts either vocabulary and says which
translation it applied. An event with no counterpart on the named host is
refused rather than silently dropped — SubagentStop/SubagentStart on Gemini,
Notification on Codex — and so is an *unrecognised* name on Codex, which
matches keys exactly and ignores what it does not know without a word. A hook
that looks installed and never fires is the failure mode worth being loud
about.

Only hooks boost created (tagged `# boost:<name>`) are ever touched; user hooks
are left untouched. See core/claude_settings.py.
"""
from __future__ import annotations

import json

from .. import cliparse
from ..core import claude_settings as cs
from ..core import hookhost, journal, util
from ..core import output as out
from ..errors import BoostError


def cmd_hooks(argv) -> int:
    p = cliparse.parser(
        prog="boost hooks",
        description="Manage agent hooks (scope- and host-aware) in an agent's "
                    "settings")
    p.add_argument("action", choices=("add", "remove", "list"),
                   help="add | remove | list")
    p.add_argument("event", nargs="?",
                   help="hook event, e.g. SessionStart "
                        "(required for add; filters remove/list)")
    p.add_argument("--host", metavar="H", default=None,
                   choices=(*hookhost.hosts(), "auto"),
                   help="agent CLI whose hook settings to manage: %s "
                        "(default: claude for add/remove, all of them for list)"
                        % ", ".join(hookhost.hosts()))
    p.add_argument("-c", "--command", help="command the hook runs (add)")
    p.add_argument("-n", "--name", help="stable name used to tag & find the hook")
    p.add_argument("-s", "--scope", choices=cs.SCOPES, default=None,
                   help="settings scope (default: project; list shows both)")
    p.add_argument("-m", "--matcher",
                   help="Claude matcher, e.g. 'startup|resume|clear'")
    p.add_argument("--timeout", type=util.positive_int, default=10,
                   help="hook timeout in seconds (default: 10)")
    p.add_argument("--json", action="store_true", dest="as_json",
                   help="machine-readable output (list)")
    p.add_argument("--force", action="store_true",
                   help="write even when $CODEX_HOME points outside this $HOME")
    args = p.parse_args(argv)

    if args.action == "list":
        return _list(args.scope, args.host, args.event, args.as_json)
    if args.action == "add":
        return _add(args)
    return _remove(args)


def _list(scope, host, event=None, as_json=False) -> int:
    rows = cs.list_all_hooks(scope, host=host)
    if event:
        # Each row is already tagged with its own host, so filter against
        # that host's native spelling rather than the one the caller typed —
        # `hooks list` (no --host) mixes Claude and Gemini rows in one table.
        rows = [r for r in rows if r["event"] == hookhost.translate(r["host"], event)]
    if as_json:
        # Every field the table shows, and `timeout` besides — it is in the
        # rows already and is the one value a reader cannot see in the prose
        # listing at all.
        print(json.dumps({"hooks": [
            {"host": r["host"], "scope": r["scope"], "event": r["event"],
             "name": r["name"], "matcher": r["matcher"] or None,
             "command": r["command"], "timeout": r.get("timeout")}
            for r in rows]}, indent=2))
        return 0
    if not rows:
        out.info("no boost-managed hooks" + (" in %s scope" % scope if scope else "")
                 + (" for event '%s'" % event if event else ""))
        return 0
    out.table(
        [(r["name"], r["host"], r["scope"], r["event"], r["matcher"] or "-",
          r["command"]) for r in rows],
        # `name` leads because a narrow pane drops columns right to left: it is
        # what `hooks remove -n` takes, so it goes last, while `host` — the
        # same word on every row — goes before it. Fourth, it went second.
        headers=("name", "host", "scope", "event", "matcher", "command"),
        # A hook's command is what the user came to read — a clipped one
        # cannot be compared against what they registered, or copied back.
        keep=("command",),
        # `name` is whole or absent: `bmad-r…` reads like a name and is not
        # one `hooks remove -n` accepts. Not `keep` — two never-dropped
        # columns outgrew the pane together with nothing left to drop — so
        # a narrow pane drops it, last, rather than clipping it.
        whole=("name",))
    return 0


def _write_host(requested) -> str:
    """The single host an `add`/`remove` targets. Claude unless told otherwise.

    `auto` is a read-only idea — fanning a write across every installed CLI is
    not what someone asking for one hook meant — so it is rejected here rather
    than quietly meaning "claude".
    """
    if requested in (None, ""):
        return hookhost.CLAUDE
    if requested == "auto":
        raise BoostError("--host auto only makes sense for `hooks list`",
                         hint="name one host: %s" % ", ".join(hookhost.hosts()))
    return requested


def _where(host: str, scope: str) -> str:
    """How a write is named back to the user: "global", or "gemini/global".

    Claude Code is the default host, so its scope stays unqualified — the
    wording predates there being a second host and there is nothing to
    disambiguate. A host the user had to ask for by name is worth repeating
    back, because "removed 1 hook" is only reassuring if it says where from.
    """
    return scope if host == hookhost.CLAUDE else "%s/%s" % (host, scope)


def _native_event(host: str, event: str) -> str:
    """`event` as `host` spells it, saying so, or refusing if it cannot.

    The two refusals are different problems and read differently. A *known*
    Claude event with no counterpart is a gap in the host (`hookhost` says
    which, per host — the note used to be a hardcoded "has no sub-agents",
    which is Gemini's gap and not Codex's). An *unrecognised* name reaching
    here at all means a `strict_events` host, where boost refuses because the
    host would accept the write and never fire the hook.
    """
    native = hookhost.translate(host, event)
    if native is None:
        known = ", ".join(hookhost.events(host))
        if event in hookhost.unmappable(host):
            raise BoostError(
                "'%s' has no %s counterpart" % (event, hookhost.label(host)),
                hint="%s; its events are: %s"
                     % (hookhost.no_counterpart_note(host), known))
        raise BoostError(
            "'%s' is not a known %s hook event"
            % (event, hookhost.event_label(host)),
            hint="%s matches an event name exactly and ignores one it does "
                 "not know — with no warning and no error — so boost refuses "
                 "rather than writing a hook that never fires. Its events "
                 "are: %s" % (hookhost.label(host), known))
    if native != event:
        out.info("Claude's '%s' is %s's '%s' — using that"
                 % (event, hookhost.event_label(host), native))
    return native


def _add(args) -> int:
    if not args.event:
        raise BoostError("hooks add needs an EVENT",
                         hint="e.g. boost hooks add SessionStart -c '<cmd>' -n <name>")
    if not args.command:
        raise BoostError("hooks add needs --command",
                         hint="the shell command Claude should run for this hook")
    if not args.name:
        raise BoostError("hooks add needs --name",
                         hint="a stable name so the hook can be removed later")
    scope = args.scope or "project"
    host = _write_host(args.host)
    event = _native_event(host, args.event)
    if event not in hookhost.events(host):
        out.warn("'%s' is not a known %s hook event — adding anyway"
                 % (event, hookhost.event_label(host)))
    snapshot = cs.add_hook(scope, event, args.name, args.command,
                           matcher=args.matcher, timeout=args.timeout,
                           host=host, force=args.force)
    journal.log("hook-add", args.name, scope=scope, event=event, host=host)
    out.ok("added %s hook '%s' (%s) → %s"
           % (event, args.name, _where(host, scope), args.command))
    out.dim("  settings: %s" % cs.settings_path(scope, host=host))
    if snapshot is not None:
        out.dim("  backup:   %s" % snapshot)
    for line in _after_add(host, scope):
        out.info(line, wrap=True)
    return 0


def _after_add(host: str, scope: str) -> list[str]:
    """What the user still has to do before this hook can run, if anything.

    Empty for Claude and Gemini, which load a hook as soon as it is written.
    Codex gates one behind a trust grant: an untrusted hook does not run, and
    a project-scope one is not even listed until the repo itself is trusted —
    `hooks/list` returns an empty list with no warning at all. Saying "added"
    and nothing else would be true and useless.
    """
    if host != hookhost.CODEX:
        return []
    lines = ["Codex reviews new hooks at startup — it will ask you to trust "
             "this one before it runs."]
    if scope == "project":
        lines.append("A project hook is also ignored until the repo is "
                     "trusted (`trust_level = \"trusted\"` in "
                     "$CODEX_HOME/config.toml).")
    return lines


def _remove(args) -> int:
    if not args.name:
        raise BoostError("hooks remove needs --name",
                         hint="the name you gave the hook when adding it")
    scope = args.scope or "project"
    host = _write_host(args.host)
    event = _native_event(host, args.event) if args.event else None
    removed = cs.remove_hook_by_name(scope, args.name, event, host=host,
                                     force=args.force)
    journal.log("hook-remove", args.name, scope=scope, host=host)
    if removed:
        out.ok("removed %d hook(s) named '%s' (%s)"
               % (removed, args.name, _where(host, scope)))
        return 0
    out.warn("no boost hook named '%s' in %s scope"
             % (args.name, _where(host, scope)))
    return 1
