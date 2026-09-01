# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Scope- and host-aware read/merge/write of a settings.json + hook management.

Claude Code reads hooks from a JSON `settings.json` at two scopes:
  global  -> ~/.claude/settings.json
  project -> <project>/.claude/settings.json

Gemini CLI reads the same shape from `~/.gemini/settings.json` and
`<project>/.gemini/settings.json`. Every function here takes `host=` (default
`"claude"`, so nothing that predates the second host changed) and gets the
per-host facts — the dotdir, the event vocabulary, the timeout units — from
`core/hookhost.py`, which is a pure table. The units are the trap worth naming
twice: Claude's `timeout` is seconds and Gemini's is milliseconds, so callers
pass **seconds** and `hookhost.hook_entry` converts.

boost only ever touches hooks it created. Each managed hook's command carries a
trailing shell comment marker `# boost:<name>` so we can find and remove exactly
our own entries and never clobber the user's hooks. Every write first snapshots
the current file into ~/.boost/state/claude-settings-history/ (the restore net for
"the global install went bad").

A Claude SessionStart hook block looks like:
    "hooks": {
      "SessionStart": [
        {"matcher": "startup|resume|clear",
         "hooks": [{"type": "command", "command": "<cmd> # boost:bmad", "timeout": 10}]}
      ]
    }
"""
from __future__ import annotations

import contextlib
import json
from pathlib import Path

from ..errors import BoostError
from . import hookhost, paths, util

SCOPES = ("global", "project")
MARKER = "# boost:"
HISTORY_KEEP = 50

# Known Claude Code hook events (permissive — validated by callers that care).
# Kept as an alias so importers that predate the host table still work; the
# list itself lives in hookhost alongside Gemini's.
KNOWN_EVENTS = hookhost.CLAUDE_EVENTS


def settings_path(scope: str, project_dir: Path | None = None,
                  host: str = hookhost.CLAUDE) -> Path:
    """Absolute path to the settings.json for a scope, on a host."""
    dotdir = hookhost.settings_dir(host)
    if scope == "global":
        return paths.home() / dotdir / "settings.json"
    if scope == "project":
        base = Path(project_dir) if project_dir else Path.cwd()
        return base / dotdir / "settings.json"
    raise BoostError("unknown scope %r" % scope,
                     hint="use 'global' or 'project'")


def _history_dir() -> Path:
    return paths.state_dir() / "claude-settings-history"


def load(scope: str, project_dir: Path | None = None,
         host: str = hookhost.CLAUDE) -> dict:
    """Parse a scope's settings.json ({} if missing or corrupt)."""
    p = settings_path(scope, project_dir, host)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save(scope: str, data: dict, project_dir: Path | None = None,
         host: str = hookhost.CLAUDE) -> None:
    """Write a scope's settings.json, snapshotting the prior version first.

    Snapshots are named ``<host prefix><scope>-<stamp>.json``. Claude's prefix
    is empty, so its history filenames are exactly what they always were and a
    Gemini write cannot land on top of one.
    """
    p = settings_path(scope, project_dir, host)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        hist = _history_dir()
        hist.mkdir(parents=True, exist_ok=True)
        stamp = util.now_iso().replace(":", "").replace("-", "")
        pre = hookhost.history_prefix(host)
        dest = hist / ("%s%s-%s.json" % (pre, scope, stamp))
        n = 2
        while dest.exists():
            dest = hist / ("%s%s-%s-%d.json" % (pre, scope, stamp, n))
            n += 1
        dest.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
        _prune_history()
    p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _prune_history() -> None:
    snaps = sorted(_history_dir().glob("*.json"),
                   key=lambda f: (f.stat().st_mtime, f.name))
    for old in snaps[:-HISTORY_KEEP]:
        with contextlib.suppress(OSError):
            old.unlink()


# --------------------------------------------------------------- marker helpers

def _tag(command: str, name: str) -> str:
    return "%s %s%s" % (command, MARKER, name)


def _hook_name(command: str) -> str | None:
    """The boost name embedded in a command string, or None if unmanaged.

    Split on the *last* marker: boost's own tag is always the one it just
    appended in :func:`_tag`, and a user command can legitimately contain the
    literal text ``# boost:...`` earlier in the string (e.g. quoting another
    hook's command). Splitting on the first marker would read that embedded
    text as the name instead of boost's own tag.
    """
    if MARKER not in command:
        return None
    return command.rsplit(MARKER, 1)[1].strip() or None


# ------------------------------------------------------------------ hook CRUD

def add_hook(scope: str, event: str, name: str, command: str,
             matcher: str | None = None, timeout: int = 10,
             project_dir: Path | None = None,
             host: str = hookhost.CLAUDE) -> None:
    """Idempotently install a boost-managed hook (replaces same-named entry).

    ``timeout`` is in **seconds** whatever the host; ``hookhost.hook_entry``
    converts it to the units that host's settings.json is read in. ``event``
    must already be spelled the way ``host`` spells it — translating is the
    command layer's job, because a Claude event with no Gemini counterpart has
    to be refused out loud rather than silently dropped here.
    """
    data = load(scope, project_dir, host)
    event_list = data.setdefault("hooks", {}).setdefault(event, [])
    # Drop any prior entry we own with this name so re-adding is idempotent.
    _strip(event_list, name)
    block: dict = {}
    if matcher:
        block["matcher"] = matcher
    block["hooks"] = [hookhost.hook_entry(host, _tag(command, name), timeout,
                                          name=name)]
    event_list.append(block)
    save(scope, data, project_dir, host)


def remove_hook(scope: str, event: str, name: str,
                project_dir: Path | None = None,
                host: str = hookhost.CLAUDE) -> int:
    """Remove boost-managed hooks matching name; return how many were removed."""
    data = load(scope, project_dir, host)
    hooks = data.get("hooks")
    if not isinstance(hooks, dict) or event not in hooks:
        return 0
    removed = _strip(hooks[event], name)
    if not removed:
        return 0
    if not hooks[event]:
        del hooks[event]
    if not hooks:
        del data["hooks"]
    save(scope, data, project_dir, host)
    return removed


def remove_hook_by_name(scope: str, name: str, event: str | None = None,
                        project_dir: Path | None = None,
                        host: str = hookhost.CLAUDE) -> int:
    """Remove boost-managed hooks named ``name``; return how many were removed.

    With ``event`` given, scoped to just that event, like :func:`remove_hook`.
    With ``event=None``, scans the events actually present in the settings
    file rather than a fixed known-event table: ``add_hook``'s caller accepts
    (with a warning) an event name outside that table, and such a hook would
    otherwise be unremovable by name alone — only by naming its event
    positionally too.
    """
    if event is not None:
        events: tuple[str, ...] = (event,)
    else:
        present = load(scope, project_dir, host).get("hooks")
        events = tuple(present) if isinstance(present, dict) else ()
    return sum(remove_hook(scope, ev, name, project_dir, host) for ev in events)


def _strip(event_list: list, name: str) -> int:
    """Drop inner hook entries owned by `name`; prune emptied blocks. In place."""
    removed = 0
    survivors = []
    for block in event_list:
        inner = block.get("hooks") if isinstance(block, dict) else None
        if not isinstance(inner, list):
            survivors.append(block)
            continue
        kept = [h for h in inner
                if _hook_name(str(h.get("command", ""))) != name]
        removed += len(inner) - len(kept)
        if kept:
            block["hooks"] = kept
            survivors.append(block)
        # else: whole block owned by us and now empty -> drop it
    event_list[:] = survivors
    return removed


def has_hook(scope: str, event: str, name: str,
             project_dir: Path | None = None,
             host: str = hookhost.CLAUDE) -> bool:
    data = load(scope, project_dir, host)
    for block in data.get("hooks", {}).get(event, []) or []:
        for h in (block.get("hooks") or []) if isinstance(block, dict) else []:
            if _hook_name(str(h.get("command", ""))) == name:
                return True
    return False


def foreign_hooks(scope: str | None = None,
                  project_dir: Path | None = None,
                  host: str = hookhost.CLAUDE) -> list[dict]:
    """Hooks in this host's settings that boost does not own.

    The complement of :func:`list_hooks`, which skips every entry without the
    `# boost:` marker — so boost could write this file for years and never be
    able to say who else was writing it. That matters now that a settings.json
    routinely has more than one writer: `garrytan/gstack`'s `./setup` registers
    its own Stop hooks here and prunes "dead gstack entries" on every run, and
    boost prunes its own by marker. The two namespaces are disjoint and
    `tests/unit/test_gstack_coexistence.py` pins that they stay that way.

    This exists so `boost doctor` can *report* the other tenant rather than
    discover it by deleting something. Nothing here writes: a foreign hook is
    not a boost problem to fix, it is context for a user reading a health
    check — which is why doctor counts it with `out.info` rather than raising
    the issue count.
    """
    scopes = (scope,) if scope else SCOPES
    rows: list[dict] = []
    for sc in scopes:
        data = load(sc, project_dir, host)
        for event, blocks in (data.get("hooks") or {}).items():
            for block in blocks or []:
                if not isinstance(block, dict):
                    continue
                for h in block.get("hooks") or []:
                    raw = str(h.get("command", ""))
                    if _hook_name(raw) is not None:
                        continue        # ours
                    rows.append({"scope": sc, "event": event, "command": raw,
                                 "matcher": block.get("matcher", "")})
    return rows


def list_hooks(scope: str | None = None,
               project_dir: Path | None = None,
               host: str = hookhost.CLAUDE) -> list[dict]:
    """One host's boost-managed hooks: [{scope, event, name, command, matcher}]."""
    scopes = (scope,) if scope else SCOPES
    rows: list[dict] = []
    for sc in scopes:
        data = load(sc, project_dir, host)
        for event, blocks in (data.get("hooks") or {}).items():
            for block in blocks or []:
                if not isinstance(block, dict):
                    continue
                for h in block.get("hooks") or []:
                    raw = str(h.get("command", ""))
                    nm = _hook_name(raw)
                    if nm is None:
                        continue
                    rows.append({
                        "scope": sc,
                        "event": event,
                        "name": nm,
                        "command": raw.rsplit(MARKER, 1)[0].strip(),
                        "matcher": block.get("matcher", ""),
                    })
    return rows


def list_all_hooks(scope: str | None = None,
                   project_dir: Path | None = None,
                   host: str | None = None) -> list[dict]:
    """:func:`list_hooks` across hosts, each row tagged with the host it is in.

    ``host=None`` means every known host, which is what ``boost hooks list``
    wants: a hook boost installed into a CLI the user has since stopped naming
    is exactly the one they need shown. Kept separate from :func:`list_hooks`
    rather than folded into it because that function's row shape is what
    callers already destructure.
    """
    return [{"host": hs} | row
            for hs in hookhost.resolve(host)
            for row in list_hooks(scope, project_dir, hs)]
