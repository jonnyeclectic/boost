"""Scope-aware read/merge/write of Claude Code's settings.json + hook management.

Claude Code reads hooks from a JSON `settings.json` at two scopes:
  global  -> ~/.claude/settings.json
  project -> <project>/.claude/settings.json

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
from typing import List, Optional

from ..errors import BoostError
from . import paths, util

SCOPES = ("global", "project")
MARKER = "# boost:"
HISTORY_KEEP = 50

# Known Claude Code hook events (permissive — validated by callers that care).
KNOWN_EVENTS = (
    "SessionStart", "SessionEnd", "UserPromptSubmit", "PreToolUse", "PostToolUse",
    "Stop", "SubagentStop", "SubagentStart", "PreCompact", "Notification",
)


def settings_path(scope: str, project_dir: Optional[Path] = None) -> Path:
    """Absolute path to the settings.json for a scope."""
    if scope == "global":
        return paths.home() / ".claude" / "settings.json"
    if scope == "project":
        base = Path(project_dir) if project_dir else Path.cwd()
        return base / ".claude" / "settings.json"
    raise BoostError("unknown scope %r" % scope,
                     hint="use 'global' or 'project'")


def _history_dir() -> Path:
    return paths.state_dir() / "claude-settings-history"


def load(scope: str, project_dir: Optional[Path] = None) -> dict:
    """Parse a scope's settings.json ({} if missing or corrupt)."""
    p = settings_path(scope, project_dir)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save(scope: str, data: dict, project_dir: Optional[Path] = None) -> None:
    """Write a scope's settings.json, snapshotting the prior version first."""
    p = settings_path(scope, project_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        hist = _history_dir()
        hist.mkdir(parents=True, exist_ok=True)
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = hist / ("%s-%s.json" % (scope, stamp))
        n = 2
        while dest.exists():
            dest = hist / ("%s-%s-%d.json" % (scope, stamp, n))
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


def _hook_name(command: str) -> Optional[str]:
    """The boost name embedded in a command string, or None if unmanaged."""
    if MARKER not in command:
        return None
    return command.split(MARKER, 1)[1].strip() or None


# ------------------------------------------------------------------ hook CRUD

def add_hook(scope: str, event: str, name: str, command: str,
             matcher: Optional[str] = None, timeout: int = 10,
             project_dir: Optional[Path] = None) -> None:
    """Idempotently install a boost-managed hook (replaces same-named entry)."""
    data = load(scope, project_dir)
    event_list = data.setdefault("hooks", {}).setdefault(event, [])
    # Drop any prior entry we own with this name so re-adding is idempotent.
    _strip(event_list, name)
    block: dict = {}
    if matcher:
        block["matcher"] = matcher
    block["hooks"] = [{
        "type": "command",
        "command": _tag(command, name),
        "timeout": timeout,
    }]
    event_list.append(block)
    save(scope, data, project_dir)


def remove_hook(scope: str, event: str, name: str,
                project_dir: Optional[Path] = None) -> int:
    """Remove boost-managed hooks matching name; return how many were removed."""
    data = load(scope, project_dir)
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
    save(scope, data, project_dir)
    return removed


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
             project_dir: Optional[Path] = None) -> bool:
    data = load(scope, project_dir)
    for block in data.get("hooks", {}).get(event, []) or []:
        for h in (block.get("hooks") or []) if isinstance(block, dict) else []:
            if _hook_name(str(h.get("command", ""))) == name:
                return True
    return False


def list_hooks(scope: Optional[str] = None,
               project_dir: Optional[Path] = None) -> List[dict]:
    """All boost-managed hooks: [{scope, event, name, command, matcher}]."""
    scopes = (scope,) if scope else SCOPES
    rows: List[dict] = []
    for sc in scopes:
        data = load(sc, project_dir)
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
                        "command": raw.split(MARKER, 1)[0].strip(),
                        "matcher": block.get("matcher", ""),
                    })
    return rows
