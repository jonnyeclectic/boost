# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
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
from typing import NamedTuple

from ..errors import BoostError
from . import paths, util

SCHEMA_VERSION = 3
HISTORY_KEEP = 50

# One section per installable kind, in lookup-precedence order. `find_any`
# resolves a bare name through these left to right, so a skill shadows a rule
# of the same name — matching the order `store.uninstall` already established.
SECTIONS: tuple[tuple[str, str], ...] = (
    ("skill", "skills"), ("rule", "rules"), ("workflow", "workflows"))


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


class Integrity(NamedTuple):
    """The lock file's own health, as opposed to what it records.

    ``read()`` collapses a missing, corrupt, or wrong-schema lock file into
    an empty skeleton so every other caller can treat "never installed" and
    "lock file broke" the same way when they only want the content. A health
    check must not conflate the two: `boost verify`/`drift`/`doctor` call
    this instead so they can tell a genuinely empty install apart from one
    whose record vanished out from under a populated store.
    """
    ok: bool
    problem: str | None    # None | "missing" | "corrupt" | "schema"
    version: object = None  # the schema version actually found, for "schema"


def check() -> Integrity:
    """Report whether the lock file itself parses as the current schema.

    Does not touch the store — a missing lock file with an empty store is a
    fresh install, not a fault; callers that care about that distinction
    combine this with a store-content check of their own.
    """
    p = paths.lockfile_path()
    if not p.exists():
        return Integrity(False, "missing")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return Integrity(False, "corrupt")
    version = raw.get("version")
    if version != SCHEMA_VERSION:
        return Integrity(False, "schema", version)
    return Integrity(True, None, version)


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


def _history_files() -> list:
    """History snapshots oldest→newest (mtime, then name — '-2' suffixed
    same-second snapshots would sort before their base name otherwise)."""
    return sorted(paths.lock_history_dir().glob("lock-*.json"),
                  key=lambda f: (f.stat().st_mtime, f.name))


def _prune_history() -> None:
    for old in _history_files()[:-HISTORY_KEEP]:
        old.unlink()


def get_skill(name: str) -> dict | None:
    """Return the lock entry for skill ``name``, or None if not installed."""
    return read()["skills"].get(name)


def set_skill(name: str, entry: dict) -> None:
    """Insert or replace the lock entry for skill ``name`` and persist."""
    lock = read()
    lock["skills"][name] = entry
    write(lock)


def apply_tag_mods(tags: list[str], mods: list[str]) -> tuple[list[str], bool]:
    """Apply ``+tag``/``-tag`` tokens to ``tags``; return (new_tags, changed).

    ``changed`` compares the resulting *set* to the starting one rather than
    tracking a per-token flag: ``+x -x`` against a skill that never carried
    ``x`` used to flip a token-level flag on both the add and the remove, so
    a pure no-op still rewrote the lock and logged a journal event. Comparing
    sorted before/after here is what makes a no-op read as one.
    """
    before = sorted(tags)
    result = tags.copy()
    for tok in mods:
        if not tok or tok[0] not in "+-":
            raise BoostError("cannot parse %r" % tok,
                            hint="prefix tags with + to add or - to remove")
        t = tok[1:].lstrip("#").strip()
        if not t:
            raise BoostError("empty tag in %r" % tok)
        if any(c.isspace() for c in t):
            raise BoostError("tag %r contains whitespace" % t,
                            hint="use a single word, joined with - or _ if needed")
        if tok[0] == "+" and t not in result:
            result.append(t)
        elif tok[0] == "-" and t in result:
            result.remove(t)
    result.sort()
    return result, result != before


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


def get_rule(name: str) -> dict | None:
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


def get_workflow(name: str) -> dict | None:
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


def find_any(name: str) -> tuple[str, dict] | None:
    """Resolve ``name`` across all three sections: ``(kind, entry)`` or None.

    This is the accessor every command that takes an installed name should
    reach for. `get_skill`/`installed()` read the ``skills`` section only,
    which is how twenty commands came to deny that an installed rule or
    workflow exists — see docs/roadmap/items/rules-install-but-cannot-be-governed.md.
    """
    lock = read()
    for kind, section in SECTIONS:
        if name in lock[section]:
            return kind, lock[section][name]
    return None


def set_entry(kind: str, name: str, entry: dict) -> None:
    """Insert or replace the lock entry for ``name`` of ``kind`` and persist."""
    section = dict(SECTIONS).get(kind)
    if section is None:
        raise ValueError("unknown lock kind %r" % kind)
    lock = read()
    lock[section][name] = entry
    write(lock)


def all_installed() -> dict[str, dict]:
    """Every installed item as ``{kind: {name: entry}}``, one read."""
    lock = read()
    return {kind: lock[section] for kind, section in SECTIONS}


def history_list(*, with_skipped: bool = False):
    """[{id, path, updated, count}] oldest→newest.

    An entry that exists but fails to parse is skipped rather than raised —
    one bad snapshot must not hide the rest of the history. Pass
    ``with_skipped=True`` to also learn how many were dropped, so a caller
    can say so instead of the id silently vanishing; the default keeps the
    plain-list return existing callers (and their equality assertions) rely
    on.
    """
    out = []
    skipped = 0
    for p in _history_files():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            skipped += 1
            continue
        out.append({
            "id": p.stem.replace("lock-", ""),
            "path": str(p),
            "updated": data.get("updated", "?"),
            # All three sections: a snapshot holding one rule is not empty.
            "count": sum(len(data.get(s, {})) for _k, s in SECTIONS),
        })
    return (out, skipped) if with_skipped else out


def history_read(hist_id: str) -> dict:
    """Return the parsed lock snapshot for history entry ``hist_id``.

    Raises BoostError (with a `boost replay` hint) if no such entry, or if
    the entry exists but is not valid JSON.
    """
    from ..errors import BoostError
    p = paths.lock_history_dir() / ("lock-%s.json" % hist_id)
    if not p.exists():
        raise BoostError("no lock history entry %s" % hist_id,
                        hint="list entries with `boost replay`")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise BoostError("lock history entry %s is unreadable: %s" % (hist_id, exc),
                        hint="list other entries with `boost replay`") from exc
