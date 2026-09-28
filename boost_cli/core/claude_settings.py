# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Scope- and host-aware read/merge/write of a settings.json + hook management.

Claude Code reads hooks from a JSON `settings.json` at two scopes:
  global  -> ~/.claude/settings.json
  project -> <project>/.claude/settings.json

Gemini CLI reads the same shape from `~/.gemini/settings.json` and
`<project>/.gemini/settings.json`, and Codex CLI from `$CODEX_HOME/hooks.json`
and `<project>/.codex/hooks.json`. Every function here takes `host=` (default
`"claude"`, so nothing that predates the second host changed) and gets the
per-host facts — the dotdir, the *filename*, the event vocabulary, the timeout
units — from `core/hookhost.py`, which is a pure table. The units are the trap
worth naming twice: Claude's `timeout` is seconds and Gemini's is milliseconds,
so callers pass **seconds** and `hookhost.hook_entry` converts. Codex agrees
with Claude on seconds and disagrees on the filename.

Two things are Codex's alone and both are silent when wrong:

* **The user-scope root moves.** `$CODEX_HOME` relocates it, resolved through
  `mcphost.config_home` so the measured grammar (including that a *relative*
  value is honoured against the cwd) has exactly one copy. The **project** root
  does not move — it is the literal `<project>/.codex` whatever the variable
  says, the asymmetry `agents.project_dotdir` exists for. Because that root
  comes from the ambient environment rather than from boost's `HOME`,
  :func:`escaping_path` is the same guard `mcphost.escapes_home` is for
  `mcp add`: a run under a sandboxed `HOME` must not write the developer's
  real `~/.codex/hooks.json`. `force=` is the escape hatch for a genuinely
  relocated Codex.
* **Position is identity.** A Codex hook's trust key is
  `<sourcePath>:<snake_case_event>:<group_index>:<handler_index>`, so
  :func:`add_hook` replaces a same-named block *in place* rather than removing
  it and appending — the latter re-keys every later group and voids the user's
  trust grant on each (measured: an untouched neighbour moved `:0:0` ->
  `:1:0`). It is the right behaviour for the other hosts too; it was just
  never load-bearing before.

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
import os
import sys
from pathlib import Path

from ..errors import BoostError
from . import hookhost, jsonstate, mcphost, output, paths, scopes, util

SCOPES = ("global", "project")
MARKER = "# boost:"
HISTORY_KEEP = 50

# Known Claude Code hook events (permissive — validated by callers that care).
# Kept as an alias so importers that predate the host table still work; the
# list itself lives in hookhost alongside Gemini's.
KNOWN_EVENTS = hookhost.CLAUDE_EVENTS


def settings_path(scope: str, project_dir: Path | None = None,
                  host: str = hookhost.CLAUDE) -> Path:
    """Absolute path to the hooks settings file for a scope, on a host.

    The filename is the host's (`settings.json`, or Codex's `hooks.json`), and
    for a host with a `movable_user_root` the **global** root comes from
    `mcphost.config_home` rather than `$HOME/<dotdir>`. Project scope is always
    `<base>/<dotdir>/<file>`: Codex reads `<project>/.codex` whatever
    `CODEX_HOME` says, so moving it here would put the file where the CLI never
    looks and still report success.

    This is a pure path computation, deliberately: `bmad._hook_hosts` probes
    `settings_path(...).parent.is_dir()` to decide whether a host is in use and
    `hooks add` prints the path, so a refusal belongs at the write (see
    :func:`escaping_path`), not here.
    """
    dotdir = hookhost.settings_dir(host)
    fname = hookhost.settings_file(host)
    if scope == "global":
        if hookhost.movable_user_root(host):
            return Path(mcphost.config_home(
                host, os.environ, str(paths.home()))) / fname
        return paths.home() / dotdir / fname
    if scope == "project":
        base = Path(project_dir) if project_dir else Path.cwd()
        return base / dotdir / fname
    raise BoostError("unknown scope %r" % scope,
                     hint="use 'global' or 'project'")


def escaping_path(scope: str, host: str,
                  project_dir: Path | None = None) -> Path | None:
    """The file this write would touch, when it is **outside** boost's `$HOME`.

    `None` means contained, and is the answer for every host whose root is
    fixed at `$HOME` and for every project-scope write — `<project>/.codex` is
    the one scope no `$HOME` contains, so judging it here would vouch for a
    file nothing was going to write, the same reason `pkg._register_mcp_server`
    refuses a project scope outright rather than guessing.

    `scopes.contains` resolves both sides, which is what makes it right on
    macOS: a `$HOME` under `/var/folders` resolves to `/private/var/...`, and
    comparing one resolved path against one nominal path never matches.
    """
    if scope != "global" or not hookhost.movable_user_root(host):
        return None
    target = settings_path(scope, project_dir, host)
    home = paths.home()
    return None if scopes.contains(home, target) else target


def refuse_escape(scope: str, host: str, project_dir: Path | None = None,
                  force: bool = False) -> None:
    """Raise unless this write lands inside boost's `$HOME`, or `force`.

    Public because a caller that writes other things first has to refuse
    *before* them: `bmad on` installs personas and then hooks, so a refusal
    raised from `add_hook` left persona files on disk that no state record
    claimed. Rebuilding the message at that call site would be a second copy
    of the one sentence that has to name the right environment variable.
    """
    if force:
        return
    target = escaping_path(scope, host, project_dir)
    if target is None:
        return
    var = mcphost.config_home_env(host)
    raise BoostError(
        "%s would write %s, outside this $HOME (%s)"
        % (hookhost.label(host), target, paths.home()),
        hint="%s points there — unset it, or pass --force to write anyway"
             % var)


def _history_dir() -> Path:
    return paths.state_dir() / "claude-settings-history"


def load(scope: str, project_dir: Path | None = None,
         host: str = hookhost.CLAUDE) -> dict:
    """Parse a scope's settings.json ({} if missing or corrupt).

    A file that exists but fails to parse is warned about by name: it stays
    on disk untouched by this read, but `save` treats an empty `{}` as this
    scope's *whole* settings from here on, so silently swallowing the error
    is how a hooks-only settings.json used to eat the user's `permissions`
    and `model` keys on the next `hooks add`.
    """
    p = settings_path(scope, project_dir, host)
    data, err = jsonstate.read_object(p)
    if err:
        output.warn(
            "%s — reading as empty; the file is left on disk but the next "
            "write here replaces its contents (a snapshot lands in %s "
            "first)" % (err, _history_dir()), stream=sys.stderr)
    return data if data is not None else {}


def save(scope: str, data: dict, project_dir: Path | None = None,
        host: str = hookhost.CLAUDE) -> Path | None:
    """Write a scope's settings.json, snapshotting the prior version first.

    Snapshots are named ``<host prefix><scope>-<stamp>.json``. Claude's prefix
    is empty, so its history filenames are exactly what they always were and a
    Gemini write cannot land on top of one.

    Returns the snapshot path, or None when there was no prior file to
    snapshot — callers that just replaced a scope's settings (`hooks add`)
    use this to tell the user where the previous version went. A write whose
    serialised bytes are identical to what is already on disk also returns
    None and touches nothing: a no-op ``boost bmad on`` used to snapshot and
    rewrite an unchanged file on every host it wrote to, burning
    :data:`HISTORY_KEEP` slots (2 hosts x 2 hooks = 4 per run) on nothing a
    restore would ever need.
    """
    p = settings_path(scope, project_dir, host)
    payload = json.dumps(data, indent=2) + "\n"
    if p.exists() and p.read_text(encoding="utf-8") == payload:
        return None
    p.parent.mkdir(parents=True, exist_ok=True)
    dest = None
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
    p.write_text(payload, encoding="utf-8")
    return dest


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
             host: str = hookhost.CLAUDE, force: bool = False) -> Path | None:
    """Idempotently install a boost-managed hook (replaces same-named entry).

    ``timeout`` is in **seconds** whatever the host; ``hookhost.hook_entry``
    converts it to the units that host's settings file is read in. ``event``
    must already be spelled the way ``host`` spells it — translating is the
    command layer's job, because an event with no counterpart on ``host`` has
    to be refused out loud rather than silently dropped here.

    The replacement is **in place**: the new block goes where the old one was,
    and only a genuinely new hook is appended. Codex keys a hook's trust grant
    by its index (``…:<group_index>:<handler_index>``), so remove-then-append
    re-keyed every group after ours and made the user re-trust hooks they had
    already trusted and boost had not touched.

    ``force`` waves through a write outside boost's ``$HOME`` — see
    :func:`escaping_path`.

    Returns `save`'s snapshot path (or None) so the caller can tell the user
    where the pre-edit settings went.
    """
    refuse_escape(scope, host, project_dir, force)
    data = load(scope, project_dir, host)
    event_list = data.setdefault("hooks", {}).setdefault(event, [])
    block: dict = {}
    if matcher:
        block["matcher"] = matcher
    block["hooks"] = [hookhost.hook_entry(host, _tag(command, name), timeout,
                                          name=name)]
    _strip(event_list, name, insert=block)
    return save(scope, data, project_dir, host)


def remove_hook(scope: str, event: str, name: str,
                project_dir: Path | None = None,
                host: str = hookhost.CLAUDE, force: bool = False) -> int:
    """Remove boost-managed hooks matching name; return how many were removed.

    The escape guard runs before the read: ``bmad off`` must not reach the file
    ``bmad on`` was stopped from reaching, and a no-op read-modify-write still
    rewrites it.
    """
    refuse_escape(scope, host, project_dir, force)
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
                        host: str = hookhost.CLAUDE,
                        force: bool = False) -> int:
    """Remove boost-managed hooks named ``name``; return how many were removed.

    With ``event`` given, scoped to just that event, like :func:`remove_hook`.
    With ``event=None``, scans the events actually present in the settings
    file rather than a fixed known-event table: ``add_hook``'s caller accepts
    (with a warning) an event name outside that table, and such a hook would
    otherwise be unremovable by name alone — only by naming its event
    positionally too.

    ``force`` as in :func:`remove_hook`, and the guard runs **here** as well,
    before the read that decides ``events``: with no ``event`` the loop below
    may run zero times, so delegating the refusal to ``remove_hook`` would let
    an escaping path be read and reported as "no such hook" rather than
    refused.
    """
    refuse_escape(scope, host, project_dir, force)
    if event is not None:
        events: tuple[str, ...] = (event,)
    else:
        present = load(scope, project_dir, host).get("hooks")
        events = tuple(present) if isinstance(present, dict) else ()
    return sum(remove_hook(scope, ev, name, project_dir, host, force=True)
               for ev in events)


def _strip(event_list: list, name: str, insert: dict | None = None) -> int:
    """Drop inner hook entries owned by `name`; prune emptied blocks. In place.

    With ``insert``, that block takes the place of the *first* one we owned an
    entry in — the vacated slot when the block empties, immediately after it
    when another writer's entries keep it alive — and is appended when we owned
    nothing. The slot is counted against the survivors as they are collected
    rather than read off the input, because a block dropped ahead of ours
    shifts every later index.

    Position is a Codex hook's identity (``…:<group_index>:<handler_index>``),
    so a re-add that removed our block and appended a new one re-keyed every
    group after it and voided the user's trust grant on each. Right for the
    other hosts too — shuffling a file boost does not own was never a feature,
    only never load-bearing.
    """
    removed = 0
    survivors: list = []
    at: int | None = None
    for block in event_list:
        inner = block.get("hooks") if isinstance(block, dict) else None
        if not isinstance(inner, list):
            survivors.append(block)
            continue
        kept = [h for h in inner
                if _hook_name(str(h.get("command", ""))) != name]
        if len(kept) != len(inner):
            removed += len(inner) - len(kept)
            if at is None:
                at = len(survivors) + (1 if kept else 0)
        if kept:
            block["hooks"] = kept
            survivors.append(block)
        # else: whole block owned by us and now empty -> drop it
    if insert is not None:
        survivors.insert(len(survivors) if at is None else at, insert)
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
    """One host's boost-managed hooks.

    Rows are ``{scope, event, name, command, matcher, timeout}``, with
    ``timeout`` normalized to seconds whatever the host stores.
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
                    nm = _hook_name(raw)
                    if nm is None:
                        continue
                    rows.append({
                        "scope": sc,
                        "event": event,
                        "name": nm,
                        "command": raw.rsplit(MARKER, 1)[0].strip(),
                        "matcher": block.get("matcher", ""),
                        # Normalized to seconds. The stored number is in the
                        # host's own units — Claude seconds, Gemini
                        # milliseconds — so reporting it raw would show the
                        # same `--timeout 10` as 10 on one host and 10000 on
                        # the other.
                        "timeout": hookhost.timeout_seconds(
                            host, h.get("timeout")),
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
