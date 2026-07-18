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
from typing import List, Optional

from . import paths, util

SCHEMA_VERSION = 3
HISTORY_KEEP = 50


def _skeleton() -> dict:
    return {"version": SCHEMA_VERSION, "updated": util.now_iso(), "skills": {}}


def read() -> dict:
    p = paths.lockfile_path()
    if not p.exists():
        return _skeleton()          # empty: never installed anything yet
    try:
        lock = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        # Corrupt (present but unparseable) is NOT the same as empty: returning
        # a bare skeleton here would let the next write() overwrite the only
        # record of every prior install. Preserve the bytes for recovery and
        # surface it loudly before falling back to the skeleton.
        _preserve_corrupt(p)
        return _skeleton()
    lock.setdefault("version", SCHEMA_VERSION)
    lock.setdefault("skills", {})
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
    try:
        from . import logs
        logs.get_logger().warning(
            "lock file %s is corrupt; preserved %s and continuing with an "
            "empty lock", p, backup or "(backup failed)")
    except Exception:
        pass


def write(lock: dict) -> None:
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
    return read()["skills"].get(name)


def set_skill(name: str, entry: dict) -> None:
    lock = read()
    lock["skills"][name] = entry
    write(lock)


def remove_skill(name: str) -> bool:
    lock = read()
    if name in lock["skills"]:
        del lock["skills"][name]
        write(lock)
        return True
    return False


def installed() -> dict:
    return read()["skills"]


def history_list() -> List[dict]:
    """[{id, path, updated, count}] oldest→newest."""
    out = []
    for p in _history_files():
        try:
            data = json.loads(p.read_text())
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
    p = paths.lock_history_dir() / ("lock-%s.json" % hist_id)
    if not p.exists():
        from ..errors import BoostError
        raise BoostError("no lock history entry %s" % hist_id,
                        hint="list entries with `boost replay`")
    return json.loads(p.read_text())
