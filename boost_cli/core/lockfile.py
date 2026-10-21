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
  entries written before it was recorded: `drift` re-taps from it)
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
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
    lock.setdefault("version", SCHEMA_VERSION)
    lock.setdefault("skills", {})
    lock.setdefault("rules", {})       # rules install alongside skills (v3+)
    lock.setdefault("workflows", {})   # workflows too (v3+)
    return lock


def corrupt_backup(p=None):
    """Where :func:`read` keeps the bytes of a lock it could not parse."""
    p = p or paths.lockfile_path()
    return p.with_name(p.name + ".corrupt")


def _preserve_corrupt(p) -> None:
    """Copy an unparseable lock file aside as ``<lock>.corrupt`` and warn.

    Best effort: a read must still succeed (returning the skeleton) even if the
    sidecar cannot be written, so failures here are swallowed after logging.
    The warning goes to stderr, once per process: read-only commands such as
    `boost list` otherwise answered "no skills installed" with nothing on the
    terminal to say the record had broken rather than emptied.
    """
    global _WARNED_CORRUPT
    backup = corrupt_backup(p)
    try:
        shutil.copy(p, backup)
    except OSError:
        backup = None
    with suppress(Exception):
        from . import logs
        logs.get_logger().warning(
            "lock file %s is corrupt; preserved %s and continuing with an "
            "empty lock", p, backup or "(backup failed)")
    if not _WARNED_CORRUPT:
        _WARNED_CORRUPT = True
        output.warn("the lock file %s is corrupt, so boost sees nothing "
                    "installed — `boost replay rollback <id>` restores it as "
                    "it was before its last change%s"
                    % (paths.tilde(p), "; the newest record is only in %s"
                       % paths.tilde(backup) if backup else ""),
                    stream=sys.stderr, wrap=True)


def refuse_corrupt() -> None:
    """Raise while the lock on disk is corrupt, so nothing writes over it.

    :func:`read` hands a corrupt lock's callers an empty skeleton, so the next
    write would replace every record with whatever one change added to it — a
    fresh `boost install` did exactly that and reported "lock updated". A
    missing lock is a fresh install and passes; so does one in another schema,
    which still parses (an older one is migrated by being rewritten).
    """
    p = paths.lockfile_path()
    if jsonstate.read_object(p)[1] is None:
        return
    raise BoostError("lock file is corrupt — boost will not write over it",
                     hint=ROLLBACK_HINT % paths.tilde(corrupt_backup(p)),
                     wrap=True)


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
        if p.exists() and jsonstate.read_object(p)[1] is not None:
            with suppress(OSError):
                shutil.copy(p, corrupt_backup(p))
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
    backup = corrupt_backup()
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


def check() -> Integrity:
    """Report whether the lock file itself parses as the current schema.

    Does not touch the store — a missing lock file with an empty store is a
    fresh install, not a fault; callers that care about that distinction
    combine this with a store-content check of their own.
    """
    raw, err = jsonstate.read_object(paths.lockfile_path())
    if err is not None:
        return Integrity(False, "corrupt")
    if raw is None:
        return Integrity(False, "missing")
    version = raw.get("version")
    if version == SCHEMA_VERSION:
        return Integrity(True, None, version)
    # The sections an older lock holds must be the ones :func:`read` hands
    # on, or every reader that walks one would trip over what it holds.
    if migratable(version) and all(isinstance(raw.get(section, {}), dict)
                                   for _kind, section in SECTIONS):
        return Integrity(True, "older", version)
    return Integrity(False, "schema", version)


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
    if integ.version is None:
        # "older" with no version; "schema" with none is a section that is
        # not a mapping, which no schema boost wrote holds.
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
