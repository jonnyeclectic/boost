# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Archive and restore the canonical skill store for `boost snapshot`.

Kept in core (not commands/pkg.py) so the mutation gate covers the two rules
that keep a snapshot honest:

* **A successful save can always be restored.** A store child that is a
  symlink — a hand-made dev skill linked in, say — used to be archived as an
  absolute symlink, which ``extractall(filter="data")`` refuses. Save now
  archives the link's *target* under the link's name, skips a dangling link,
  and checks every member against the same ``data`` filter restore applies, so
  an entry restore would refuse is refused at save time instead.
* **A restore never empties the store before the archive is known good.** The
  archive is extracted into a staging directory next to the store first; only
  when that has fully succeeded are the store's children swapped out, and a
  failure part-way through the swap puts the old children back.
* **A held copy rides along.** A quarantined or sidelined skill's copy sits
  outside the store (``paths.held_skills_dir``), while its lock row — which
  says ``held_at`` — is inside it. Archiving the store alone restored rows
  pointing at copies that existed nowhere, so a save during `boost focus`
  lost every sidelined skill's content. Held copies are archived under
  :data:`HELD_ARC` and restored to the held dir, never into the store.
* **An interrupt is a failure like any other.** The swap rolls back on any
  exception, Ctrl-C included, and the dir the old children are parked in is
  only deleted once the swap has succeeded or they are all back: a parked
  store left by a kill is reported by `boost doctor`, never removed unasked.
* **The archived lock is checked before it replaces the live one.** A lock
  that does not parse, or is another schema, emptied every install; one
  written under another ``$HOME`` is rehomed (:func:`lockfile.rehome`).
  Save applies the same check to the live store (:func:`lock_problem`), so a
  snapshot save reports as saved is one restore accepts.
* **A restore replaces skills, not what boost kept for the user.** Store
  children the caller names in ``carry`` — the lock's ``.corrupt`` backups,
  a dir the live lock does not record — are carried across the swap. One the
  archive also holds is moved to ``backup_dir`` and named, never deleted.
"""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import tarfile
import tempfile
from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from pathlib import Path

from ..errors import BoostError
from . import lockfile, util

UNTOUCHED_HINT = ("the store was left untouched — "
                  "see `boost snapshot list` for other snapshots")


#: The archive directory held copies go under: a dot name nothing boost
#: writes into the store uses, and restore takes it out of the staging dir
#: before anything is swapped into the store. A store child of this name is
#: refused at save, so it can never be mistaken for the held copies.
HELD_ARC = ".boost-held"

#: The ``mkdtemp`` prefixes :func:`restore` makes beside the store, longest
#: first: staging (the archive), the parked previous children, the held
#: copies. A kill leaves them; ``store.stale_temps`` names them.
PARKED_PREFIX = ".boost-restore-old-"
HELD_PREFIX = ".boost-restore-held-"
STAGING_PREFIX = ".boost-restore-"
RESTORE_PREFIXES = (PARKED_PREFIX, HELD_PREFIX, STAGING_PREFIX)

TAR_SUFFIX = ".tar.gz"
META_SUFFIX = ".json"


@dataclass(frozen=True)
class Unit:
    """One snapshot as `boost snapshot list` counts it: ``<id>.tar.gz`` and
    its ``<id>.json`` sidecar are one thing, with one age.

    `clean --deep` used to age and count each file on its own, so one old
    snapshot was prompted as "2 snapshot(s)", and a tarball and its sidecar
    could fall on opposite sides of the cutoff — one removed, one orphaned.
    Anything else in the directory is a unit of its own.
    """

    id: str
    #: Tarball first, sidecar last: if the tarball goes and the sidecar
    #: cannot, the orphan sidecar is still aged by its ``created`` next time.
    files: tuple[Path, ...]
    created: float            #: Unix time
    sizes: tuple[int, ...]    #: one per file, in ``files`` order


def _unit_key(name: str) -> str:
    for suffix in (TAR_SUFFIX, META_SUFFIX):
        if name.endswith(suffix):
            return name[:-len(suffix)]
    return name


def _created(meta: Path | None) -> float | None:
    """The sidecar's ``created`` stamp — what `snapshot list` shows."""
    if meta is None:
        return None
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return util.epoch_from_iso(data.get("created")) if isinstance(data, dict) else None


def units(snap_dir: Path) -> list[Unit]:
    """Every snapshot unit in ``snap_dir``, sorted by id."""
    groups: dict[str, list[Path]] = {}
    for entry in sorted(snap_dir.iterdir()):
        groups.setdefault(_unit_key(entry.name), []).append(entry)
    found = []
    for key, members in sorted(groups.items()):
        tar = next((m for m in members if m.name == key + TAR_SUFFIX), None)
        meta = next((m for m in members if m.name == key + META_SUFFIX), None)
        files = sorted(members, key=lambda m: (m is not tar, m is meta, m.name))
        created = _created(meta)
        if created is None:
            created = files[0].lstat().st_mtime
        sizes = tuple(util.dir_size(m) if m.is_dir() and not m.is_symlink()
                      else m.lstat().st_size for m in files)
        found.append(Unit(id=key, files=tuple(files), created=created,
                          sizes=sizes))
    return found


def older_than(snap_dir: Path, cutoff: float) -> list[Unit]:
    """The units of ``snap_dir`` created before ``cutoff`` (a Unix time)."""
    return [u for u in units(snap_dir) if u.created < cutoff]


@dataclass
class ArchiveResult:
    """What :func:`archive` did with store children that were symlinks."""

    dereferenced: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    #: Held copies archived beside the store, by skill name.
    held: list[str] = field(default_factory=list)


def archive(root: Path, tar_path: Path,
            held: dict[str, Path] | None = None) -> ArchiveResult:
    """Write every child of ``root`` into a gzip tarball at ``tar_path``.

    A symlinked child is archived as its target's content (a restore brings it
    back as a real copy); a dangling one is skipped. ``held`` maps a skill name
    to its held copy, archived under :data:`HELD_ARC`; one not on disk is
    skipped. Raises BoostError, and leaves no archive behind, when a member
    would be refused on restore, or when the store's lock would
    (:func:`check_save`).
    """
    check_save(root)
    res = ArchiveResult()
    # Checked against an empty directory — what restore extracts into — not
    # the live store: `data_filter` realpaths each member's destination, and
    # in the store `mydev` is the very symlink being archived.
    probe = tempfile.TemporaryDirectory(prefix=".boost-snapcheck-")
    dest = probe.name

    def _check(ti: tarfile.TarInfo) -> tarfile.TarInfo:
        try:
            tarfile.data_filter(ti, dest)
        except tarfile.FilterError as e:
            raise BoostError(
                "cannot snapshot %s: %s" % (ti.name, e),
                hint="restore would refuse this entry — replace the link "
                     "with a relative one inside the skill, or a real file") from e
        return ti   # the check only; the archive keeps the original metadata

    try:
        with tarfile.open(str(tar_path), "w:gz") as tf:
            for child in sorted(root.iterdir()):
                if child.name == HELD_ARC:
                    raise BoostError(
                        "cannot snapshot %s: the name is reserved for held "
                        "copies" % child.name,
                        hint="move it out of the store, then save again")
                src = child
                if child.is_symlink():
                    if not child.exists():
                        res.skipped.append(child.name)
                        continue
                    src = child.resolve()
                    res.dereferenced.append(child.name)
                tf.add(str(src), arcname=child.name, filter=_check)
            for name, hdir in sorted((held or {}).items()):
                if hdir.is_dir() and not hdir.is_symlink():
                    tf.add(str(hdir), arcname="%s/%s" % (HELD_ARC, name),
                           filter=_check)
                    res.held.append(name)
    except BaseException:
        with contextlib.suppress(OSError):
            tar_path.unlink()
        raise
    finally:
        probe.cleanup()
    return res


def _swap_in(staging: Path, root: Path, scratch: Path) -> None:
    """Replace ``root``'s children with ``staging``'s, all or nothing.

    ``root`` itself is kept (agents' symlinks path into it, and it may be a
    symlink); its old children are parked in ``scratch`` until every new one
    is in place, and moved back if anything — a failed move, or Ctrl-C —
    stops the swap first. Only an OSError becomes a BoostError; anything
    else is re-raised once the old children are back.
    """
    old = sorted(root.iterdir())
    new = sorted(c.name for c in staging.iterdir())
    try:
        for child in old:
            os.replace(child, scratch / child.name)
        for name in new:
            os.replace(staging / name, root / name)
    except BaseException as e:
        _roll_back(root, staging, scratch, {c.name for c in old}, new)
        if isinstance(e, OSError):
            raise BoostError("restore failed while swapping the store: %s" % e,
                             hint="the previous store contents were put back") from e
        raise


def _roll_back(root: Path, staging: Path, scratch: Path, old: set[str],
               new: list[str]) -> None:
    """Undo a part-done :func:`_swap_in`, reading what moved off the disk.

    Every old child moves out before any new one moves in, so a new name in
    ``root`` whose old namesake is parked — or that ``root`` never had — came
    from the archive and goes back to ``staging``; then whatever is parked
    returns. Read from the disk, not a list of finished moves: an interrupt
    between a rename and its bookkeeping would leave a child no list names.
    """
    parked = {c.name for c in scratch.iterdir()}
    for name in new:
        target = root / name
        if (name in parked or name not in old) and os.path.lexists(target):
            with contextlib.suppress(OSError):
                os.replace(target, staging / name)
    for name in sorted(parked):
        with contextlib.suppress(OSError):
            os.replace(scratch / name, root / name)


def _put_held(src: Path, held_root: Path | None) -> list[str]:
    """Move each held copy under ``src`` into ``held_root``, replacing any
    copy already there; the names moved. Without ``held_root``, none."""
    if held_root is None or not src.is_dir():
        return []
    moved = []
    held_root.mkdir(parents=True, exist_ok=True)
    for child in sorted(src.iterdir()):
        target = held_root / child.name
        if os.path.lexists(target):
            util.remove_path(target)
        shutil.move(str(child), str(target))
        moved.append(child.name)
    return moved


#: The lock file's name inside the store (``paths.lockfile_path``).
LOCK_NAME = ".skill-lock.json"


@dataclass
class RestoreResult:
    """What :func:`restore` did besides swapping the archive in."""

    #: Held copies put back in the held dir, by skill name.
    held: list[str] = field(default_factory=list)
    #: Store children carried across the swap, by name.
    carried: list[str] = field(default_factory=list)
    #: Where each carried child the archive also held was moved to.
    backed_up: list[Path] = field(default_factory=list)


def _free_name(d: Path, name: str) -> Path:
    """``d/name``, or ``d/name.2``, ``.3``, … — the first that is free."""
    dest, n = d / name, 2
    while os.path.lexists(dest):
        dest, n = d / ("%s.%d" % (name, n)), n + 1
    return dest


def _held_back(p: Path) -> bool:
    """Whether ``p`` is something :func:`_carry` would carry: present, and
    not a dangling symlink, which holds nothing."""
    return os.path.lexists(p) and not (p.is_symlink() and not p.exists())


def _stranded(scratch: Path, names: Collection[str]) -> list[str]:
    """The names in ``names`` still parked in ``scratch``."""
    return [n for n in sorted(names) if _held_back(scratch / n)]


def _carry(scratch: Path, root: Path, carry: Collection[str],
           keep_live: Collection[str], set_aside: Collection[str],
           backup_dir: Path | None, res: RestoreResult) -> None:
    """Bring each parked child named in ``carry`` back into ``root``, and
    move each one in ``set_aside`` to ``backup_dir``.

    A carried child the archive did not hold goes back as it was. One it did
    is the archive's to fill, unless it is in ``keep_live`` (the live copy
    wins and the archive's, still in the tarball, is dropped); the live one
    is then set aside too. A dangling symlink holds nothing and is not kept.
    Without ``backup_dir`` nothing is set aside: it stays parked.
    """
    for name in sorted({*carry, *set_aside}):
        src = scratch / name
        if not _held_back(src):
            continue
        dst = root / name
        clash = os.path.lexists(dst)
        if clash and name in keep_live and name not in set_aside:
            util.remove_path(dst)
        elif clash or name in set_aside:
            if backup_dir is not None:
                backup_dir.mkdir(parents=True, exist_ok=True)
                dest = _free_name(backup_dir, name)
                shutil.move(str(src), str(dest))
                res.backed_up.append(dest)
            continue
        os.replace(src, dst)
        res.carried.append(name)


def lock_problem(root: Path) -> tuple[str, lockfile.Integrity] | None:
    """Why the lock in ``root`` would empty the store it describes, or None.

    A lock that does not parse, has sections that are not maps, or is a
    schema this boost does not read; or no lock at all beside store entries.
    A dir holding nothing but held copies, or nothing, is an empty store.
    Returns the reason, worded to follow "it", and the lock's integrity.
    """
    integ = lockfile.check(root / LOCK_NAME)
    if integ.ok:
        return None
    if integ.problem == "missing":
        if not any(c.name != HELD_ARC for c in root.iterdir()):
            return None
        why = "holds skills but no lock file to say which are installed"
    elif integ.problem == "schema":
        why = "has a lock file in schema %r, which this boost does not read" % (
            integ.version,)
    elif integ.problem == "unreadable":
        why = "has a lock file boost cannot read"
    else:
        why = "has a corrupt lock file"
    return why, integ


def check_lock(staging: Path, snap_id: str) -> None:
    """Refuse an extracted archive whose lock file would empty the store.

    A bad lock (:func:`lock_problem`) replaced a good one, and every install
    vanished from it: links swept, the restore reported success. So did an
    archive holding store dirs and no lock at all.
    """
    problem = lock_problem(staging)
    if problem is not None:
        raise BoostError("snapshot %s cannot be restored: it %s"
                         % (snap_id, problem[0]), hint=UNTOUCHED_HINT)


def check_save(root: Path) -> None:
    """Refuse to archive a store whose lock :func:`check_lock` would refuse.

    The save and restore contracts are one rule: a save over a corrupt or
    missing lock reported "saved" and how to restore it, and the restore
    then refused that same snapshot.
    """
    problem = lock_problem(root)
    if problem is not None:
        why, integ = problem
        raise BoostError("cannot snapshot the store: it %s" % why,
                         hint="%s, then save again — a snapshot of it could "
                              "not be restored" % lockfile.remedy(integ),
                         wrap=True)


def _vet_lock(staging: Path, snap_id: str,
              rehome: Callable[[dict], bool] | None) -> None:
    """:func:`check_lock`, then ``rehome`` over the staged lock, which is
    restamped ``updated`` now and rewritten in staging.

    The restamp is what keeps lock history chronological: the next write
    archives this lock under its ``updated`` (``lockfile._archive_stamp``),
    and the archive's own, older stamp put the restored state in history
    beside the state it was saved from, under a colliding id, sorted above
    entries written after it.
    """
    check_lock(staging, snap_id)
    lock = staging / LOCK_NAME
    if not lock.exists():
        return
    data = json.loads(lock.read_text(encoding="utf-8-sig"))
    if rehome is not None:
        rehome(data)
    data["updated"] = util.now_iso()
    # Staging is boost's own scratch dir, swapped in whole or not at all, so
    # a plain write is as safe here as an atomic one.
    lock.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def restore(tar_path: Path, root: Path, snap_id: str,
            held_root: Path | None = None,
            rehome: Callable[[dict], bool] | None = None,
            before_swap: Callable[[], object] | None = None,
            carry: Collection[str] = (), keep_live: Collection[str] = (),
            set_aside: Collection[str] = (),
            backup_dir: Path | None = None) -> RestoreResult:
    """Replace the contents of ``root`` with the archive at ``tar_path``.

    Held copies in the archive go to ``held_root`` once the store swap has
    succeeded, never into ``root``. The children of ``root`` named in
    ``carry`` are carried across the swap (:func:`_carry`), into
    ``backup_dir`` when the archive holds that name too; those named in
    ``set_aside`` always go there. ``rehome`` is given
    the archived lock, parsed, before the swap: it may rewrite it in place
    or raise BoostError to refuse. The staged lock is stamped ``updated``
    now. ``before_swap`` runs once the archive has been vetted, just before
    ``root`` changes: `snapshot restore` passes
    :func:`lockfile.record_history`, so the lock it replaces stays in lock
    history like every other lock change's. It is a parameter, not a call
    made here, because lock history is the real store's and ``root`` need
    not be.

    Raises — with ``root`` exactly as it was — when the archive cannot be
    opened, is corrupt, holds an entry the ``data`` filter refuses or a lock
    :func:`check_lock` refuses, or the swap is interrupted.
    """
    try:
        tf = tarfile.open(str(tar_path), "r:gz")  # noqa: SIM115  (opened in a try to translate the error; used via `with tf:` below)
    except (tarfile.TarError, OSError, EOFError) as e:
        raise BoostError("snapshot %s is unreadable: %s" % (snap_id, e),
                         hint=UNTOUCHED_HINT) from e
    # Next to the real store, so the swap is a rename on one filesystem.
    parent = root.resolve().parent
    staging = Path(tempfile.mkdtemp(dir=str(parent), prefix=STAGING_PREFIX))
    scratch = Path(tempfile.mkdtemp(dir=str(parent), prefix=PARKED_PREFIX))
    parked = Path(tempfile.mkdtemp(dir=str(parent), prefix=HELD_PREFIX))
    swapped = False
    done = False
    try:
        with tf:
            try:
                members = tf.getmembers()
            except (tarfile.TarError, OSError, EOFError) as e:
                raise BoostError("snapshot %s is corrupt: %s" % (snap_id, e),
                                 hint=UNTOUCHED_HINT) from e
            try:
                tf.extractall(str(staging), members=members, filter="data")
            except (tarfile.TarError, OSError, EOFError) as e:
                raise BoostError("snapshot %s cannot be restored: %s"
                                 % (snap_id, e), hint=UNTOUCHED_HINT) from e
        _vet_lock(staging, snap_id, rehome)
        # Out of staging first: everything left there is swapped into the store.
        if os.path.lexists(staging / HELD_ARC):
            os.replace(staging / HELD_ARC, parked / HELD_ARC)
        # Last thing before the swap, once the archive is known good: the
        # caller keeps the lock about to be replaced in history here.
        if before_swap is not None:
            before_swap()
        _swap_in(staging, root, scratch)
        swapped = True
        res = RestoreResult(held=_put_held(parked / HELD_ARC, held_root))
        try:
            _carry(scratch, root, carry, keep_live, set_aside, backup_dir,
                   res)
        except OSError as e:
            raise BoostError(
                "restored %s, but could not carry everything boost kept "
                "beside the skills back into the store: %s" % (snap_id, e),
                hint="what was not carried is still in %s" % scratch) from e
        done = not _stranded(scratch, {*carry, *set_aside})
        return res
    finally:
        for d in (staging, parked):
            with contextlib.suppress(OSError):
                util.rmtree(d)
        # The previous store, until the swap is done: removed whole only
        # then, and otherwise only when empty — a rollback that was itself
        # cut short leaves the user's skills here, not in a deleted dir.
        # A carry that failed or was declined leaves its child parked: the
        # parked dir goes whole only once nothing asked for is still in it.
        with contextlib.suppress(OSError):
            if swapped and done:
                util.rmtree(scratch)
            else:
                scratch.rmdir()
