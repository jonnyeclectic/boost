# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""boost hooks — scope- and host-aware management of agent hooks in settings.json.

    boost hooks add SessionStart --command 'boost bmad orient' --name bmad \
        --scope global --matcher 'startup|resume|clear'
    boost hooks add PreToolUse --host gemini -c 'boost check' -n guard
    boost hooks list
    boost hooks remove --name bmad

Two hosts have hooks: Claude Code (`~/.claude/settings.json`, the default and
unchanged) and Gemini CLI (`~/.gemini/settings.json`). What differs between
them is a pure table in core/hookhost.py; this layer only picks a host, spells
the event the way that host spells it, and reports what it did.

Event names mostly differ, so `--host gemini` accepts either vocabulary and
says which translation it applied. Two Claude events — SubagentStop and
SubagentStart — have no Gemini counterpart at all, and are refused rather than
silently dropped: a hook that looks installed and never fires is the failure
mode worth being loud about.

Only hooks boost created (tagged `# boost:<name>`) are ever touched; user hooks
are left untouched. See core/claude_settings.py.
"""
from __future__ import annotations

from .. import cliparse
from ..core import claude_settings as cs
from ..core import hookhost, journal
from ..core import output as out
from ..errors import BoostError


def cmd_hooks(argv) -> int:
    p = cliparse.parser(
        prog="boost hooks",
        description="Manage agent hooks (scope- and host-aware) in settings.json")
    p.add_argument("action", choices=("add", "remove", "list"),
                   help="add | remove | list")
    p.add_argument("event", nargs="?",
                   help="hook event, e.g. SessionStart (required for add)")
    p.add_argument("--host", metavar="H", default=None,
                   choices=(*hookhost.hosts(), "auto"),
                   help="agent CLI whose settings.json to manage: %s "
                        "(default: claude for add/remove, all of them for list)"
                        % ", ".join(hookhost.hosts()))
    p.add_argument("-c", "--command", help="command the hook runs (add)")
    p.add_argument("-n", "--name", help="stable name used to tag & find the hook")
    p.add_argument("-s", "--scope", choices=cs.SCOPES, default=None,
                   help="settings scope (default: project; list shows both)")
    p.add_argument("-m", "--matcher",
                   help="Claude matcher, e.g. 'startup|resume|clear'")
    p.add_argument("--timeout", type=int, default=10,
                   help="hook timeout in seconds (default: 10)")
    args = p.parse_args(argv)

    if args.action == "list":
        return _list(args.scope, args.host)
    if args.action == "add":
        return _add(args)
    return _remove(args)


def _list(scope, host) -> int:
    rows = cs.list_all_hooks(scope, host=host)
    if not rows:
        out.info("no boost-managed hooks" + (" in %s scope" % scope if scope else ""))
        return 0
    out.table(
        [(r["host"], r["scope"], r["event"], r["name"], r["matcher"] or "-",
          r["command"]) for r in rows],
        headers=("host", "scope", "event", "name", "matcher", "command"))
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
    """`event` as `host` spells it, saying so, or refusing if it cannot."""
    native = hookhost.translate(host, event)
    if native is None:
        raise BoostError(
            "'%s' has no %s counterpart" % (event, hookhost.label(host)),
            hint="%s has no sub-agents; its events are: %s"
                 % (hookhost.label(host), ", ".join(hookhost.events(host))))
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
    cs.add_hook(scope, event, args.name, args.command,
                matcher=args.matcher, timeout=args.timeout, host=host)
    journal.log("hook-add", args.name, scope=scope, event=event, host=host)
    out.ok("added %s hook '%s' (%s) → %s"
           % (event, args.name, _where(host, scope), args.command))
    out.dim("  settings: %s" % cs.settings_path(scope, host=host))
    return 0


def _remove(args) -> int:
    if not args.name:
        raise BoostError("hooks remove needs --name",
                         hint="the name you gave the hook when adding it")
    scope = args.scope or "project"
    host = _write_host(args.host)
    event = _native_event(host, args.event) if args.event else None
    removed = cs.remove_hook_by_name(scope, args.name, event, host=host)
    journal.log("hook-remove", args.name, scope=scope, host=host)
    if removed:
        out.ok("removed %d hook(s) named '%s' (%s)"
               % (removed, args.name, _where(host, scope)))
        return 0
    out.warn("no boost hook named '%s' in %s scope"
             % (args.name, _where(host, scope)))
    return 1
