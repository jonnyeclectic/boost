# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The v3 lock file: ~/.agents/skills/.skill-lock.json

Every write snapshots the previous version into ~/.boost/state/lock-history/
so `boost replay` can show history and roll back.

Skill entry schema (v3):
  version, tap, tap_url, source_dir, commit, sha256,
  installed_at, updated_at, pinned, quarantined, agents[], tags[]
  (+ source_url on a `boost import`: the git URL, or "" for a local path; when
  set, source_dir is the skill's directory inside that repo)
  (tap_url is the tap's own URL or local path at install time, absent on
  entries written before it was recorded: `drift` re-taps from it, and
  `sync`, `heal`, `update` and `untap` backfill it from config.json while
  the tap is still configured — `store.backfill_tap_urls`)
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import NamedTuple

from ..errors import BoostError
from . import jsonstate, output, paths, util

SCHEMA_VERSION = 3
HISTORY_KEEP = 50

# Once per process: one command can write the lock several times, and the
# fix is the same each time.
_WARNED_UNSAVED = False
# Once per process too: every read of a corrupt lock finds the same fault, and
# `boost list` reads it several times before it prints "no skills installed".
_WARNED_CORRUPT = False
#: What a refused write tells the user. History snapshots the lock *before*
#: each write, so the newest snapshot predates the last change.
ROLLBACK_HINT = ("`boost replay rollback <id>` restores the lock as it was "
                 "before its last change; the newest record is only in %s")
#: The same, when there is no history to roll back to — which is always the
#: case after the first install, since a snapshot is only taken *before* a
#: write. `boost sync --rebuild-lock` (:func:`set_aside`) is what works then.
REBUILD_HINT = ("`boost sync --rebuild-lock` sets it aside and re-records the "
                "store; the newest record is only in %s")
#: A lock a newer boost wrote is that boost's to read: rolling it back would
#: discard that boost's last change, and writing over it its whole schema.
UPGRADE = "upgrade boost with `boost self-update`"

# One section per installable kind, in lookup-precedence order. `find_any`
# resolves a bare name through these left to right, so a skill shadows a rule
# of the same name — matching the order `store.uninstall` already established.
SECTIONS: tuple[tuple[str, str], ...] = (
    ("skill", "skills"), ("rule", "rules"), ("workflow", "workflows"))


# Held across every read-modify-write of the lock (see :func:`mutate`).
# Re-entrant within one process — `write` takes it, and so does `mutate`,
# which calls `write` — while `util.file_lock` excludes other processes.
_HELD = threading.RLock()
_depth = 0


def guard_path():
    """The sidecar :func:`mutate` locks: beside the lock file, never it."""
    p = paths.lockfile_path()
    return p.with_name(p.name + ".lock")


@contextmanager
def exclusive() -> Iterator[None]:
    """Hold the lock file against every other boost process for the body.

    Each mutation used to `read()` the whole lock, change one row and
    `write()` it back with nothing between processes: run `boost install a`
    and `boost pin b` at once and the second write replaced the first, so
    one command reported "lock updated" for a row that was never kept.
    Atomic writes stop a torn file, not a lost update.
    """
    global _depth
    with _HELD:
        if _depth:
            _depth += 1
            try:
                yield
            finally:
                _depth -= 1
            return
        with util.file_lock(guard_path(), what="the lock file", strict=False):
            _depth = 1
            try:
                yield
            finally:
                _depth = 0


def mutate(fn: Callable[[dict], bool | None]) -> bool:
    """Apply ``fn`` to a fresh read of the lock and persist it, atomically.

    The read happens *inside* :func:`exclusive`, so ``fn`` sees every write
    another process finished before it. ``fn`` returning False means "nothing
    changed" and skips the write; anything else writes. Returns whether it
    wrote. An exception from ``fn`` writes nothing and releases the lock.
    """
    with exclusive():
        lock = read()
        if fn(lock) is False:
            return False
        write(lock)
        return True


def _skeleton() -> dict:
    return {"version": SCHEMA_VERSION, "updated": util.now_iso(),
            "skills": {}, "rules": {}, "workflows": {}}


def read() -> dict:
    """Load the lock file, guaranteeing skills/rules/workflows keys.

    Missing file -> empty skeleton; a corrupt file — not UTF-8, not JSON, or
    JSON that is not an object — is preserved as ``<lock>.corrupt`` before
    falling back to the skeleton.
    """
    p = paths.lockfile_path()
    lock, err = jsonstate.read_object(p)
    if err is not None:
        # Corrupt (present but unparseable) is NOT the same as empty: returning
        # a bare skeleton here would let the next write() overwrite the only
        # record of every prior install. Preserve the bytes for recovery and
        # surface it loudly before falling back to the skeleton.
        _preserve_corrupt(p)
        return _skeleton()
    if lock is None:
        return _skeleton()          # empty: never installed anything yet
    if shape_error(lock) is not None:
        # `{"rules": []}` or a row that is a string parses, and every reader
        # that walks it then died on `.items()`/`.get` — doctor included. A
        # schema boost knows, so it is corrupt; one it does not know is a
        # newer boost's, kept as it is (:func:`refuse_corrupt` guards it).
        if _known(lock.get("version")):
            _preserve_corrupt(p)
        return _skeleton()
    lock.setdefault("version", SCHEMA_VERSION)
    lock.setdefault("skills", {})
    lock.setdefault("rules", {})       # rules install alongside skills (v3+)
    lock.setdefault("workflows", {})   # workflows too (v3+)
    return lock


def shape_error(raw: dict) -> str | None:
    """Why a parsed lock's sections are not maps of records, or None."""
    for _kind, section in SECTIONS:
        bad = jsonstate.object_map_error(raw, section)
        if bad is not None:
            return bad
    return None


def _known(version: object) -> bool:
    """Whether ``version`` is a schema this boost reads: current or older."""
    return version == SCHEMA_VERSION or migratable(version)


def corrupt_backups(p=None) -> list:
    """Every backup of an unreadable lock, oldest first.

    ``<lock>.corrupt``, then ``<lock>.corrupt.2``, ``.3``, … — the names
    :func:`jsonstate.quarantine` uses. One fixed name was overwritten by the
    next corrupt read, so a hand fix that broke the file again destroyed the
    only copy of the newest record while the warning still pointed at it.
    """
    p = p or paths.lockfile_path()
    base = p.name + ".corrupt"
    found = []
    with suppress(OSError):
        for f in p.parent.iterdir():
            rest = f.name[len(base):] if f.name.startswith(base) else None
            if rest == "":
                found.append((1, f))
            # isascii too: "²".isdigit() is True and int("²") raises, so one
            # stray name would crash every reader of a corrupt lock.
            elif (rest and rest[0] == "." and rest[1:].isascii()
                  and rest[1:].isdigit()):
                found.append((int(rest[1:]), f))
    return [f for _n, f in sorted(found)]


def _holding(p, backups: list):
    """The backup in ``backups`` byte-identical to ``p``, or None."""
    try:
        data = p.read_bytes()
    except OSError:
        return None
    for b in backups:
        with suppress(OSError):
            if b.read_bytes() == data:
                return b
    return None


def corrupt_backup(p=None):
    """The backup of an unreadable lock to name to the user.

    The one holding the lock's current bytes, when there is one; else the
    newest; else ``<lock>.corrupt``, where :func:`keep_copy` puts the first.
    """
    p = p or paths.lockfile_path()
    backups = corrupt_backups(p)
    held = _holding(p, backups)
    if held is not None:
        return held
    return backups[-1] if backups else p.with_name(p.name + ".corrupt")


def keep_copy(p=None):
    """Copy the lock's bytes to a backup unless one already holds them.

    A distinct state goes to the next free name (``.corrupt``, then
    ``.corrupt.N`` one past the highest), so no backup is ever overwritten.
    Returns the backup that holds them. Raises OSError when it cannot copy.
    """
    p = p or paths.lockfile_path()
    backups = corrupt_backups(p)
    held = _holding(p, backups)
    if held is not None:
        return held
    if not backups:
        dest = p.with_name(p.name + ".corrupt")
    else:
        last = backups[-1].name.rsplit(".", 1)[-1]
        n = int(last) + 1 if last.isdigit() else 2
        dest = p.with_name("%s.corrupt.%d" % (p.name, n))
    shutil.copy(p, dest)
    return dest


def has_history() -> bool:
    """Whether `boost replay` has a snapshot it can roll back to."""
    return bool(history_list())


def _preserve_corrupt(p) -> None:
    """Copy an unparseable lock file aside as ``<lock>.corrupt`` and warn.

    Best effort: a read must still succeed (returning the skeleton) even if the
    sidecar cannot be written, so failures here are swallowed after logging.
    The warning goes to stderr, once per process: read-only commands such as
    `boost list` otherwise answered "no skills installed" with nothing on the
    terminal to say the record had broken rather than emptied.
    """
    global _WARNED_CORRUPT
    try:
        backup = keep_copy(p)
    except OSError:
        backup = None
    with suppress(Exception):
        from . import logs
        logs.get_logger().warning(
            "lock file %s is corrupt; preserved %s and continuing with an "
            "empty lock", p, backup or "(backup failed)")
    if not _WARNED_CORRUPT:
        _WARNED_CORRUPT = True
        how = ("`boost replay rollback <id>` restores it as it was before "
               "its last change" if has_history()
               else "`boost sync --rebuild-lock` sets it aside and re-records "
                    "the store")
        output.warn("the lock file %s is corrupt, so boost sees nothing "
                    "installed — %s%s"
                    % (paths.tilde(p), how, "; the newest record is only in %s"
                       % paths.tilde(backup) if backup else ""),
                    stream=sys.stderr, wrap=True)


def refuse_corrupt() -> None:
    """Raise while the lock on disk is one boost must not write over.

    :func:`read` hands a corrupt lock's callers an empty skeleton, so the next
    write would replace every record with whatever one change added to it — a
    fresh `boost install` did exactly that and reported "lock updated". A
    missing lock is a fresh install and passes; so does an older schema, which
    is migrated by being rewritten. A newer schema is refused: `pin`, `tag`
    and `install` each stamped a v4 lock as v3 with a green tick, while
    `verify`, `sync` and `heal` declined to touch it.
    """
    integ = check()
    if integ.ok or integ.problem == "missing":
        return
    p = paths.lockfile_path()
    if newer(integ):
        raise BoostError(
            "lock file is schema v%s, newer than this boost's v%d — boost will "
            "not write over it" % (integ.version, SCHEMA_VERSION),
            hint="%s; this boost would drop what v%s records"
                 % (UPGRADE, integ.version), wrap=True)
    # Kept now, not only by a read(): install refuses before reading, and the
    # newest backup may hold an earlier corruption rather than these bytes.
    try:
        held = keep_copy(p)
    except OSError:
        held = corrupt_backup(p)
    raise BoostError("lock file %s — boost will not write over it" % fault(integ),
                     hint=(ROLLBACK_HINT if has_history() else REBUILD_HINT)
                     % paths.tilde(held),
                     wrap=True)


def newer(integ: Integrity) -> bool:
    """Whether :func:`check` found a lock a newer boost wrote."""
    v = integ.version
    return (integ.problem == "schema" and isinstance(v, int)
            and not isinstance(v, bool) and v > SCHEMA_VERSION)


def remedy(integ: Integrity) -> str:
    """What fixes a lock :func:`check` found unreadable, worded to follow
    "— ": ``restore it with `boost replay``` only while there is history to
    restore, ``rebuild it …`` when there is none, and an upgrade for a lock a
    newer boost wrote, whose rollback would discard that boost's last change.
    """
    if newer(integ):
        return UPGRADE
    if has_history():
        return "restore it with `boost replay`"
    return "rebuild it from the store with `boost sync --rebuild-lock`"


def set_aside():
    """Move an unreadable lock out of the way so `boost sync` re-records it.

    The no-history way back (:data:`REBUILD_HINT`): its bytes are kept in a
    backup (:func:`keep_copy`) first, and a missing lock over a populated
    store is what `boost sync` already knows how to re-record. Refuses a lock
    boost can read, and one a newer boost wrote. Returns the backup.
    """
    with exclusive():
        integ = check()
        if integ.ok or integ.problem == "missing":
            raise BoostError("the lock file is readable — there is nothing "
                             "to rebuild", hint="run `boost sync`")
        if newer(integ):
            raise BoostError("the lock file %s — boost will not set it aside"
                             % fault(integ), hint=UPGRADE, wrap=True)
        p = paths.lockfile_path()
        try:
            backup = keep_copy(p)
            p.unlink()
        except OSError as e:
            raise BoostError("could not set %s aside (%s)"
                             % (paths.tilde(p), e.strerror or e)) from e
        return backup


def restore(hist_id: str) -> dict:
    """Make history entry ``hist_id`` the lock file again, and return it.

    The way back from a corrupt lock, and so the one write that does not go
    through :func:`write`'s guard: it replaces the lock with a snapshot boost
    itself took, byte for byte. The corrupt bytes are copied to
    ``<lock>.corrupt`` first, so restoring loses nothing.
    """
    snapshot = history_read(hist_id)
    p = paths.lockfile_path()
    with exclusive():
        integ = check()
        if not integ.ok and integ.problem != "missing":
            with suppress(OSError):
                keep_copy(p)
        src = paths.lock_history_dir() / ("lock-%s.json" % hist_id)
        util.atomic_write_text(p, src.read_text(encoding="utf-8"))
    return snapshot


def unrestored_corrupt():
    """The ``.corrupt`` backup while it is newer than every history snapshot.

    A snapshot is taken *before* each write, so none holds the lock's newest
    state: `boost replay rollback` to the newest one restores the lock as it
    was before its last change, and what that change recorded is only in the
    backup. Until boost writes the lock again (which snapshots the restored
    one, newer than the backup), a store dir the lock does not record may be
    a skill that change installed — not one added outside boost — and
    `boost sync` would re-file it as a ``local`` skill linked everywhere.
    An equal mtime counts as newer: a coarse clock must not hide the backup.
    Returns ``None`` when there is no backup or a later write superseded it.
    """
    backups = corrupt_backups()
    if not backups:
        return None
    backup = backups[-1]
    try:
        mtime = backup.stat().st_mtime_ns
    except OSError:
        return None
    newest = -1
    for snap in paths.lock_history_dir().glob("lock-*.json"):
        with suppress(OSError):
            newest = max(newest, snap.stat().st_mtime_ns)
    return backup if mtime >= newest else None


def unrestored_line(n: int, shown: str, backup) -> str:
    """Doctor's line for ``n`` store dirs (named in ``shown``) that a lock
    restored by `boost replay rollback` does not record; see
    :func:`unrestored_corrupt`."""
    one = n == 1
    return ("%d skill%s the restored lock file does not record (%s) — its "
            "newest record is only in %s; `boost sync` would re-file %s"
            % (n, "" if one else "s", shown,
               paths.tilde(backup),
               "it as a local skill" if one else "them as local skills"))


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
    # None | "missing" | "corrupt" | "schema" | "older". "older" is the one
    # problem that is ok: a lock with no schema version, or an earlier one,
    # still parses and is migrated by being rewritten (:func:`migrate`).
    problem: str | None
    version: object = None  # the schema version found, for "schema"/"older"


def check(p=None) -> Integrity:
    """Report whether the lock file itself parses as the current schema.

    Does not touch the store — a missing lock file with an empty store is a
    fresh install, not a fault; callers that care about that distinction
    combine this with a store-content check of their own. ``p`` checks a lock
    file somewhere else instead: `snapshot restore` asks it of the archived
    one before that replaces the live store.
    """
    raw, err = jsonstate.read_object(p or paths.lockfile_path())
    if err is not None:
        return Integrity(False, "corrupt")
    if raw is None:
        return Integrity(False, "missing")
    version = raw.get("version")
    if not _known(version):
        return Integrity(False, "schema", version)
    # The sections must be maps of records, as :func:`read` hands them on, or
    # every reader that walks one trips over what it holds. In a schema boost
    # knows, anything else is damage, not a format: corrupt, like bad JSON.
    if shape_error(raw) is not None:
        return Integrity(False, "corrupt", version)
    if version == SCHEMA_VERSION:
        return Integrity(True, None, version)
    return Integrity(True, "older", version)


def migratable(version: object) -> bool:
    """Whether a lock of schema ``version`` is one boost upgrades by rewriting.

    No version is the oldest format there is, and an earlier integer is one
    boost wrote before: :func:`read` hands back every record either holds and
    :func:`write` stamps the current schema over them, keeping every other
    key. A newer version, or one that is not an integer at all, was written
    by something boost has never seen, so nothing may write over it. Refusing
    the older ones sent `verify`, `drift`, `sync` and `heal` to `boost replay`,
    whose rollback undoes the last install, while the next install migrated
    the same lock without a word.
    """
    if version is None:
        return True
    return (isinstance(version, int) and not isinstance(version, bool)
            and 0 < version < SCHEMA_VERSION)


def older_line(integ: Integrity, dry: bool = False) -> str:
    """The sync/heal line for migrating an ``"older"`` lock."""
    was = ("had no schema version" if integ.version is None
           else "was schema v%s" % integ.version)
    return "%s the lock file, which %s, as schema v%d" % (
        "would record" if dry else "recorded", was, SCHEMA_VERSION)


def migrate() -> str | None:
    """Rewrite an ``"older"`` lock as the current schema; the line saying so.

    Under :func:`exclusive`, so the check and the write see one lock. None
    when there is nothing to migrate.
    """
    with exclusive():
        integ = check()
        if integ.problem != "older":
            return None
        write(read())
        return older_line(integ)


def fault(integ: Integrity) -> str:
    """What is wrong with a lock :func:`check` found corrupt or in another
    schema, worded to follow "the lock file": ``is corrupt``, or ``is schema
    v2, not v3``. A lock that is only missing has no fault to name here: sync
    re-records what it lost, so its callers word that case themselves.
    """
    if integ.problem == "corrupt":
        return "is corrupt"
    if newer(integ):
        return "is schema v%s, newer than this boost's v%d" % (
            integ.version, SCHEMA_VERSION)
    if integ.version is None:
        # "older" with no version; :func:`check` never says "schema" with
        # none (a versionless lock is the oldest format), but an Integrity
        # built by hand may, and "v None" names nothing.
        return ("has no schema version" if integ.problem == "older"
                else "is in no schema boost knows")
    return "is schema v%s, not v%d" % (integ.version, SCHEMA_VERSION)


def _stamp(iso: str) -> str:
    return iso.replace(":", "").replace("-", "")


def _archive_stamp(p) -> str:
    """History filename stamp for the lock file about to become history.

    The lock's own ``updated`` field is the moment it BECAME current; using
    that (rather than now, the moment it stops being current) makes the
    history id equal the state it captures, so ``replay list``'s ID and WHEN
    columns describe the same instant instead of two writes apart. Falls
    back to now for a lock with no readable ``updated`` (corrupt, or an
    older schema) — there is nothing truthful to stamp it with instead.
    """
    raw = jsonstate.read_object(p)[0] or {}
    updated = raw.get("updated")
    if isinstance(updated, str) and updated:
        return _stamp(updated)
    return _stamp(util.now_iso())


def write(lock: dict) -> None:
    """Snapshot the existing lock to history, then write ``lock`` atomically.

    Stamps ``version``/``updated`` on ``lock`` in place and prunes
    history to the newest HISTORY_KEEP snapshots.

    The snapshot is a record, not the work, so one that cannot be taken is a
    warning and the lock is still written. A refused history dir under a
    read-only ``~/.boost/state`` used to fail here after an install had
    already copied, linked or written its files, leaving them on disk with no
    lock entry any boost command could find.

    A corrupt lock is the exception: it raises (:func:`refuse_corrupt`)
    rather than being replaced by a lock built on :func:`read`'s skeleton.
    So does one in a schema boost does not know, a newer one included.
    """
    with exclusive():
        refuse_corrupt()
        p = paths.lockfile_path()      # atomic_write_text makes the store
        if p.exists():
            _snapshot(p)
        lock["version"] = SCHEMA_VERSION
        lock["updated"] = util.now_iso()
        try:
            util.atomic_write_text(
                p, json.dumps(lock, indent=2, sort_keys=True) + "\n")
        except OSError as e:
            # A full disk, an immutable lock or a read-only store: say which
            # file and why, as config.save does, instead of a crash report
            # naming a temp path.
            block = paths.refuses_writes(p.parent)
            raise BoostError(
                "could not save %s (%s)%s"
                % (paths.tilde(p), e.strerror or e,
                   ": " + paths.not_writable(p.parent, block) if block else ""),
                hint="%s, then re-run" % paths.write_remedy(block)
                if block else "free space or clear the file's immutable flag, "
                              "then re-run") from e


def _snapshot(p) -> None:
    """Copy the current lock into history; warn once if that is refused."""
    global _WARNED_UNSAVED
    hist = paths.lock_history_dir()
    try:
        hist.mkdir(parents=True, exist_ok=True)
        stamp = _archive_stamp(p)
        dest = hist / ("lock-%s.json" % stamp)
        n = 2
        while dest.exists():  # same-second writes each keep their snapshot
            dest = hist / ("lock-%s-%d.json" % (stamp, n))
            n += 1
        # plain copy: the snapshot's mtime is when it was TAKEN (copy2 would
        # inherit the lock file's older mtime and mis-sort it as oldest)
        shutil.copy(p, dest)
        _prune_history()
    except OSError as e:
        if not _WARNED_UNSAVED:
            _WARNED_UNSAVED = True
            where = paths.refuses_writes(hist) or hist
            output.warn("could not keep a history snapshot of the lock file "
                        "(%s) — `boost replay` will not offer the state before "
                        "this change; make %s writable"
                        % (e.strerror or e, paths.tilde(where)),
                        stream=sys.stderr, wrap=True)


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
    _put("skills", name, entry)


def _put(section: str, name: str, entry: dict) -> None:
    def put(lock: dict) -> None:
        lock[section][name] = entry
    mutate(put)


def _section(kind: str) -> str:
    section = dict(SECTIONS).get(kind)
    if section is None:
        raise ValueError("unknown lock kind %r" % kind)
    return section


def update_entry(kind: str, name: str,
                 fn: Callable[[dict], bool | None]) -> bool:
    """Apply ``fn`` to ``name``'s row as it is *under the lock*, and persist.

    The way a command changes the fields it owns without writing back the
    rest of a row it read earlier. `boost tag`, `pin` and `edit` each used to
    read the row, do their work, and hand the whole row to :func:`set_entry`:
    a pin made while `boost edit` sat in the editor was reverted when it
    exited, and an uninstall in that window came back as a ghost row.
    ``fn`` mutates the fresh row in place; returning False writes nothing.
    A row that is gone by now is not recreated: ``fn`` is not called and
    nothing is written. Returns whether it wrote.
    """
    section = _section(kind)

    def apply(lock: dict) -> bool | None:
        row = lock[section].get(name)
        if row is None:
            return False
        return fn(row)
    return mutate(apply)


def update_skill(name: str, fn: Callable[[dict], bool | None]) -> bool:
    """:func:`update_entry` for a skill row."""
    return update_entry("skill", name, fn)


def _drop(section: str, name: str) -> bool:
    def drop(lock: dict) -> bool:
        if name not in lock[section]:
            return False
        del lock[section][name]
        return True
    return mutate(drop)


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
    return _drop("skills", name)


def installed() -> dict:
    """Return the name -> entry mapping of installed skills."""
    return read()["skills"]


def split_sidelined(skills: dict) -> tuple[dict, list[str]]:
    """``(active, sidelined names)`` of a name -> entry skills mapping.

    A sidelined skill (``sidelined_by`` set by focus, profile or context) is
    installed but deliberately unlinked, so it is not part of the setup an
    agent sees. `profile save` snapshots that setup: recording a sidelined
    skill made `profile use` relink it later — a skill that was off when the
    profile was saved came back on when it was restored.
    """
    active = {n: e for n, e in skills.items() if not e.get("sidelined_by")}
    return active, sorted(n for n in skills if n not in active)


def get_rule(name: str) -> dict | None:
    """Return the lock entry for rule ``name``, or None if not installed."""
    return read()["rules"].get(name)


def set_rule(name: str, entry: dict) -> None:
    """Insert or replace the lock entry for rule ``name`` and persist."""
    _put("rules", name, entry)


def remove_rule(name: str) -> bool:
    """Drop rule ``name`` from the lock; return True if it was present."""
    return _drop("rules", name)


def installed_rules() -> dict:
    """Return the name -> entry mapping of installed rules."""
    return read()["rules"]


def get_workflow(name: str) -> dict | None:
    """Return the lock entry for workflow ``name``, or None if not installed."""
    return read()["workflows"].get(name)


def set_workflow(name: str, entry: dict) -> None:
    """Insert or replace the lock entry for workflow ``name`` and persist."""
    _put("workflows", name, entry)


def remove_workflow(name: str) -> bool:
    """Drop workflow ``name`` from the lock; return True if it was present."""
    return _drop("workflows", name)


def installed_workflows() -> dict:
    """Return the name -> entry mapping of installed workflows."""
    return read()["workflows"]


def portable(lock: dict, base=None) -> dict:
    """Deep copy of ``lock`` with machine-specific materialization paths dropped.

    A rule or workflow entry's ``materializations[].path`` is written absolute,
    rooted at this machine's ``$HOME`` (e.g. ``/Users/alice/.claude/CLAUDE.md``) —
    fine for boost's own bookkeeping, but ``boost onboard`` commits a lock
    snapshot into a shared repo. ``paths.tilde`` contracts each path to ``~``,
    keeping the useful part (which agent, which file) while dropping the
    username that would otherwise churn the committed file on every
    teammate's own run.

    ``base`` is the repo the snapshot is for. The user lock also records every
    ``--local`` rule and workflow from *every* checkout on the machine, each
    tagged with its absolute ``base`` — so without a filter, onboarding one repo
    committed another repo's installs into it, absolute path and all. With
    ``base`` given, a project-scope row survives only when this repo owns it
    (:func:`scopes.owns`), and its ``base`` and paths become repo-relative.
    Without one, project rows are kept but their ``base`` is contracted too.
    """
    from . import scopes
    projected = json.loads(json.dumps(lock))
    want = None if base is None else os.path.realpath(base)
    for _kind, section in SECTIONS:
        entries = projected.get(section, {})
        for name in list(entries):
            entry = entries[name]
            local = (isinstance(entry, dict)
                     and entry.get("scope") == scopes.SCOPE_PROJECT)
            if local and base is not None and not scopes.owns(entry, base):
                del entries[name]
                continue
            # Any string ``base``, not only a project row's: ``update`` can
            # write one back without ``scope``, and it names $HOME all the same.
            if isinstance(entry, dict) and isinstance(entry.get("base"), str):
                entry["base"] = ("." if local and want is not None
                                 else paths.tilde(entry["base"]))
            # A workflow's ``foreign`` rows name a path under $HOME too.
            for m in (*(entry.get("materializations") or ()),
                      *(entry.get("foreign") or ())):
                if isinstance(m, dict) and "path" in m:
                    m["path"] = _portable_path(m["path"], want if local else None)
    return projected


def _root_of(p: str, root) -> str | None:
    """The spelling of ``root`` — as given, or resolved (a symlinked or
    /private home) — that the absolute path ``p`` is or sits beneath."""
    for r in (str(root), os.path.realpath(root)):
        stem = r.rstrip(os.sep)
        if p == stem or p.startswith(stem + os.sep):
            # ``/`` strips to "", which relpath would read as the cwd.
            return stem or os.sep
    return None


def _under(p: str, root) -> bool:
    """Whether the absolute path ``p`` is ``root`` or sits beneath it."""
    return _root_of(p, root) is not None


def _dot_home(p: str, agent, home, dirs: dict) -> str | None:
    """The home ``p`` was written under, read off where its agent's dotdir
    (``.claude`` for ``~/.claude/skills``) appears in it, nearest the file."""
    adir = dirs.get(agent)
    dot = adir.parent if adir is not None else None
    if dot is None or not _under(str(dot), home):
        return None
    rel = Path(os.path.relpath(dot, home)).parts
    parts = Path(p).parts
    for i in range(len(parts) - len(rel), 0, -1):
        if parts[i:i + len(rel)] == rel:
            return str(Path(*parts[:i]))
    return None


def _rehome(p: str, agent, old_home: str | None, home,
            dirs: dict) -> str | None:
    """``p`` placed under ``home``; ``p`` itself when it already belongs on
    this machine; None when nothing says where it would go.

    It belongs when it is relative, under ``home``, or under its agent's own
    dotdir (an agent dir configured outside ``$HOME``). Otherwise it moves
    from ``old_home`` when it sits under that, or — for a snapshot that never
    recorded its home — from wherever its agent's dotdir appears in it, since
    ``/old/home/.claude/CLAUDE.md`` is ``.claude/CLAUDE.md`` under any home.
    """
    adir = dirs.get(agent)
    dot = adir.parent if adir is not None else None
    if (not Path(p).is_absolute() or _under(p, home)
            or (dot is not None and _under(p, dot))):
        return p
    base = _root_of(p, old_home) if old_home else None
    if base is None:
        base = _dot_home(p, agent, home, dirs)
    if base is None:
        return None
    return os.path.join(str(home), os.path.relpath(p, base))


def _infer_home(lock: dict, home, dirs: dict) -> str | None:
    """The one home a snapshot with no recorded home was saved under, read
    off the rows whose agent dotdir places them; None unless they agree.

    Without it a row no dotdir names — Gemini's ``~/.gemini/GEMINI.md``,
    whose skills dir is the canonical store, or a row with no agent — was
    unplaceable, and every such snapshot was refused on another machine.
    """
    seen = set()
    for _kind, entry in _user_rows(lock):
        for m in _row_paths(entry):
            p = m["path"]
            if Path(p).is_absolute() and not _under(p, home):
                guess = _dot_home(p, m.get("agent"), home, dirs)
                if guess is not None:
                    seen.add(guess)
    return seen.pop() if len(seen) == 1 else None


def _user_rows(lock: dict):
    """``(label, entry)`` for each user-scope rule/workflow row of ``lock``."""
    from . import scopes
    for kind, section in SECTIONS:
        if kind == "skill":
            continue
        for name, entry in sorted((lock.get(section) or {}).items()):
            if isinstance(entry, dict) and entry.get("scope") != scopes.SCOPE_PROJECT:
                yield "%s %s" % (kind, name), entry


def _row_paths(entry: dict):
    """The materialization/foreign records of ``entry`` that carry a path."""
    for m in (*(entry.get("materializations") or ()),
              *(entry.get("foreign") or ())):
        if isinstance(m, dict) and isinstance(m.get("path"), str):
            yield m


def rehome(lock: dict, home, old_home: str | None = None,
           dirs: dict | None = None) -> tuple[list[str], list[str]]:
    """Move a user-scope rule/workflow row's absolute paths onto ``home``.

    A snapshot carries the lock of the machine that saved it, whose
    ``materializations[].path`` and ``foreign[].path`` are absolute under
    *that* ``$HOME``. Restored as they were, every row pointed at the first
    home: doctor read the other home's files as this one's and called them
    fully materialized, and `boost uninstall` deleted them. Rehomed, the row
    names the file this machine's agent reads, and `boost sync` writes it
    when it is missing. ``old_home`` is the home the snapshot was saved
    under, when its sidecar says; ``dirs`` maps an agent to its skills dir
    here (:func:`agents.known_agents`). A project-scope row is the repo's
    and is left alone.

    Mutates ``lock``; returns ``(moved, unplaced)`` as ``kind name`` labels
    — a row with a path neither ``old_home`` nor its agent's dotdir places
    is unplaced, and keeps the path it had. With no ``old_home`` it is
    inferred from the rows a dotdir places, when they agree on one.
    """
    dirs = dirs or {}
    if not old_home:
        old_home = _infer_home(lock, home, dirs)
    moved: list[str] = []
    unplaced: list[str] = []
    for label, entry in _user_rows(lock):
        for m in _row_paths(entry):
            new = _rehome(m["path"], m.get("agent"), old_home, home, dirs)
            if new is None:
                if label not in unplaced:
                    unplaced.append(label)
            elif new != m["path"]:
                m["path"] = new
                if label not in moved:
                    moved.append(label)
    return moved, unplaced


def _portable_path(p, want: str | None) -> str:
    """``p`` relative to the repo ``want`` when it sits inside it, else ``~``-contracted."""
    if want is not None and isinstance(p, str) and os.path.isabs(p):
        real = os.path.realpath(p)
        if real.startswith(want.rstrip(os.sep) + os.sep):
            return real[len(want.rstrip(os.sep)) + 1:].replace(os.sep, "/")
    return paths.tilde(p)


def agent_names(kind: str, entry: dict | None) -> list[str]:
    """Sorted, deduplicated agent names an installed item of ``kind`` reaches.

    A skill's lock entry records a flat ``agents`` list; a rule or workflow
    instead records one ``materializations`` entry per agent, so the name
    lives at ``m["agent"]``. Sorting both the same way is the point: before
    this helper existed, `boost stats`' rule/workflow branch sorted its
    agents line while the skill branch printed raw lock/install order —
    two presentations of the same fact that happened to disagree.

    A workflow's skill copy (:func:`is_skill_copy`) is a row too, and names no
    agent: it sits in the canonical store, reached by whichever agents read
    that. It is left out here, because ``None`` sorted beside agent names
    raises, and printing it as ``?`` names an agent that does not exist.
    """
    if not entry:
        return []
    if kind == "skill":
        return sorted(entry.get("agents") or [])
    return sorted({m.get("agent", "?") for m in entry.get("materializations") or []
                   if not is_skill_copy(m)})


def is_skill_copy(m: dict) -> bool:
    """Whether materialization row ``m`` is a workflow's copy in the skill store.

    Its ``slot`` is :data:`workflows.SLOT_SKILL` and its ``agent`` is None.
    """
    from . import workflows
    return m.get("slot") == workflows.SLOT_SKILL


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
    _put(_section(kind), name, entry)


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
        data = jsonstate.read_object(p)[0]
        if data is None:
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
    the entry exists but is not a JSON object whose sections are maps of
    records.
    """
    from ..errors import BoostError
    p = paths.lock_history_dir() / ("lock-%s.json" % hist_id)
    data, err = jsonstate.read_object(p)
    if err is not None:
        raise BoostError("lock history entry %s is unreadable: %s" % (hist_id, err),
                         hint="list other entries with `boost replay`")
    if data is None:
        raise BoostError("no lock history entry %s" % hist_id,
                         hint="list entries with `boost replay`")
    # `replay show` and `rollback` call `.get` on every record of every
    # section; a section that is not a map of objects is refused here, before
    # either acts, rather than dropped — a snapshot read as holding no skills
    # would have rollback uninstall every skill installed now.
    for _kind, section in SECTIONS:
        bad = jsonstate.object_map_error(data, section)
        if bad is not None:
            raise BoostError("lock history entry %s is unreadable: %s: %s"
                             % (hist_id, p, bad),
                             hint="list other entries with `boost replay`")
    return data
