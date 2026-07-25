"""The v3 lock file: ~/.agents/skills/.skill-lock.json

Every write snapshots the previous version into ~/.boost/state/lock-history/
so `boost replay` can show history and roll back.

Skill entry schema (v3):
  version, tap, source_dir, commit, sha256,
  installed_at, updated_at, pinned, quarantined, agents[], tags[]
"""
from __future__ import annotations

import json
import shutil
from contextlib import suppress
from typing import List, Optional

from . import paths, util

SCHEMA_VERSION = 3
HISTORY_KEEP = 50


def _skeleton() -> dict:
    return {"version": SCHEMA_VERSION, "updated": util.now_iso(),
            "skills": {}, "rules": {}, "workflows": {}}


def read() -> dict:
    """Load the lock file, guaranteeing skills/rules/workflows keys.

    Missing file -> empty skeleton; a corrupt file is preserved as
    ``<lock>.corrupt`` before falling back to the skeleton.
    """
    p = paths.lockfile_path()
    if not p.exists():
        return _skeleton()          # empty: never installed anything yet
    try:
        lock = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # Corrupt (present but unparseable) is NOT the same as empty: returning
        # a bare skeleton here would let the next write() overwrite the only
        # record of every prior install. Preserve the bytes for recovery and
        # surface it loudly before falling back to the skeleton.
        _preserve_corrupt(p)
        return _skeleton()
    lock.setdefault("version", SCHEMA_VERSION)
    lock.setdefault("skills", {})
    lock.setdefault("rules", {})       # rules install alongside skills (v3+)
    lock.setdefault("workflows", {})   # workflows too (v3+)
    return lock


def _preserve_corrupt(p) -> None:
    """Copy an unparseable lock file aside as ``<lock>.corrupt`` and warn.

    Best effort: a read must still succeed (returning the skeleton) even if the
    sidecar cannot be written, so failures here are swallowed after logging.
    """
    try:
        backup = p.with_name(p.name + ".corrupt")
        shutil.copy(p, backup)
    except OSError:
        backup = None
    with suppress(Exception):
        from . import logs
        logs.get_logger().warning(
            "lock file %s is corrupt; preserved %s and continuing with an "
            "empty lock", p, backup or "(backup failed)")


def write(lock: dict) -> None:
    """Snapshot the existing lock to history, then write ``lock`` atomically.

    Stamps ``version``/``updated`` on ``lock`` in place and prunes
    history to the newest HISTORY_KEEP snapshots.
    """
    paths.ensure_dirs()
    p = paths.lockfile_path()
    if p.exists():
        stamp = util.now_iso().replace(":", "").replace("-", "")
        dest = paths.lock_history_dir() / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = paths.lock_history_dir() / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    lock["version"] = SCHEMA_VERSION
    lock["updated"] = util.now_iso()
    util.atomic_write_text(p, json.dumps(lock, indent=2, sort_keys=True) + "\n")


def _history_files() -> List:
    """History snapshots oldest→newest (mtime, then name — '-2' suffixed
    same-second snapshots would sort before their base name otherwise)."""
    return sorted(paths.lock_history_dir().glob("lock-*.json"),
                  key=lambda f: (f.stat().st_mtime, f.name))


def _prune_history() -> None:
    for old in _history_files()[:-HISTORY_KEEP]:
        old.unlink()


def get_skill(name: str) -> Optional[dict]:
    """Return the lock entry for skill ``name``, or None if not installed."""
    return read()["skills"].get(name)


def set_skill(name: str, entry: dict) -> None:
    """Insert or replace the lock entry for skill ``name`` and persist."""
    lock = read()
    lock["skills"][name] = entry
    write(lock)


def remove_skill(name: str) -> bool:
    """Drop skill ``name`` from the lock; return True if it was present."""
    lock = read()
    if name in lock["skills"]:
        del lock["skills"][name]
        write(lock)
        return True
    return False


def installed() -> dict:
    """Return the name -> entry mapping of installed skills."""
    return read()["skills"]


def get_rule(name: str) -> Optional[dict]:
    """Return the lock entry for rule ``name``, or None if not installed."""
    return read()["rules"].get(name)


def set_rule(name: str, entry: dict) -> None:
    """Insert or replace the lock entry for rule ``name`` and persist."""
    lock = read()
    lock["rules"][name] = entry
    write(lock)


def remove_rule(name: str) -> bool:
    """Drop rule ``name`` from the lock; return True if it was present."""
    lock = read()
    if name in lock["rules"]:
        del lock["rules"][name]
        write(lock)
        return True
    return False


def installed_rules() -> dict:
    """Return the name -> entry mapping of installed rules."""
    return read()["rules"]


def get_workflow(name: str) -> Optional[dict]:
    """Return the lock entry for workflow ``name``, or None if not installed."""
    return read()["workflows"].get(name)


def set_workflow(name: str, entry: dict) -> None:
    """Insert or replace the lock entry for workflow ``name`` and persist."""
    lock = read()
    lock["workflows"][name] = entry
    write(lock)


def remove_workflow(name: str) -> bool:
    """Drop workflow ``name`` from the lock; return True if it was present."""
    lock = read()
    if name in lock["workflows"]:
        del lock["workflows"][name]
        write(lock)
        return True
    return False


def installed_workflows() -> dict:
    """Return the name -> entry mapping of installed workflows."""
    return read()["workflows"]


def history_list() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": p.stem.replace("lock-", ""),
            "path": str(p),
            "updated": data.get("updated", "?"),
            "count": len(data.get("skills", {})),
        })
    return out


def history_read(hist_id: str) -> dict:
    """Return the parsed lock snapshot for history entry ``hist_id``.

    Raises BoostError (with a `boost replay` hint) if no such entry.
    """
    p = paths.lock_history_dir() / ("lock-%s.json" % hist_id)
    if not p.exists():
        from ..errors import BoostError
        raise BoostError("no lock history entry %s" % hist_id,
                        hint="list entries with `boost replay`")
    return json.loads(p.read_text(encoding="utf-8"))
