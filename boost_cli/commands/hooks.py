"""boost hooks — scope-aware management of Claude Code hooks in settings.json.

    boost hooks add SessionStart --command 'boost bmad orient' --name bmad \
        --scope global --matcher 'startup|resume|clear'
    boost hooks list
    boost hooks remove --name bmad

Only hooks boost created (tagged `# boost:<name>`) are ever touched; user hooks
are left untouched. See core/claude_settings.py.
"""
from __future__ import annotations

from .. import cliparse
from ..core import claude_settings as cs
from ..core import journal
from ..core import output as out
from ..errors import BoostError


def cmd_hooks(argv) -> int:
    p = cliparse.parser(
        prog="boost hooks",
        description="Manage Claude Code hooks (scope-aware) in settings.json")
    p.add_argument("action", choices=("add", "remove", "list"),
                   help="add | remove | list")
    p.add_argument("event", nargs="?",
                   help="hook event, e.g. SessionStart (required for add)")
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
        return _list(args.scope)
    if args.action == "add":
        return _add(args)
    return _remove(args)


def _list(scope) -> int:
    rows = cs.list_hooks(scope)
    if not rows:
        out.info("no boost-managed hooks" + (" in %s scope" % scope if scope else ""))
        return 0
    out.table(
        [(r["scope"], r["event"], r["name"], r["matcher"] or "-", r["command"])
         for r in rows],
        headers=("scope", "event", "name", "matcher", "command"))
    return 0


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
    if args.event not in cs.KNOWN_EVENTS:
        out.warn("'%s' is not a known Claude hook event — adding anyway" % args.event)
    cs.add_hook(scope, args.event, args.name, args.command,
                matcher=args.matcher, timeout=args.timeout)
    journal.log("hook-add", args.name, scope=scope, event=args.event)
    out.ok("added %s hook '%s' (%s) → %s"
           % (args.event, args.name, scope, args.command))
    out.dim("  settings: %s" % cs.settings_path(scope))
    return 0


def _remove(args) -> int:
    if not args.name:
        raise BoostError("hooks remove needs --name",
                         hint="the name you gave the hook when adding it")
    scope = args.scope or "project"
    events = (args.event,) if args.event else cs.KNOWN_EVENTS
    removed = sum(cs.remove_hook(scope, ev, args.name) for ev in events)
    journal.log("hook-remove", args.name, scope=scope)
    if removed:
        out.ok("removed %d hook(s) named '%s' (%s)" % (removed, args.name, scope))
    else:
        out.warn("no boost hook named '%s' in %s scope" % (args.name, scope))
    return 0
