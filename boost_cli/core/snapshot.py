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
"""
from __future__ import annotations

import contextlib
import os
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from ..errors import BoostError
from . import util

UNTOUCHED_HINT = ("the store was left untouched — "
                  "see `boost snapshot list` for other snapshots")


@dataclass
class ArchiveResult:
    """What :func:`archive` did with store children that were symlinks."""

    dereferenced: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def archive(root: Path, tar_path: Path) -> ArchiveResult:
    """Write every child of ``root`` into a gzip tarball at ``tar_path``.

    A symlinked child is archived as its target's content (a restore brings it
    back as a real copy); a dangling one is skipped. Raises BoostError, and
    leaves no archive behind, when a member would be refused on restore.
    """
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
                src = child
                if child.is_symlink():
                    if not child.exists():
                        res.skipped.append(child.name)
                        continue
                    src = child.resolve()
                    res.dereferenced.append(child.name)
                tf.add(str(src), arcname=child.name, filter=_check)
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
    is in place, and moved back if any move fails.
    """
    old = sorted(root.iterdir())
    moved_out: list[Path] = []
    moved_in: list[Path] = []
    try:
        for child in old:
            os.replace(child, scratch / child.name)
            moved_out.append(child)
        for child in sorted(staging.iterdir()):
            target = root / child.name
            os.replace(child, target)
            moved_in.append(target)
    except OSError as e:
        for p in moved_in:
            with contextlib.suppress(OSError):
                if p.is_dir() and not p.is_symlink():
                    util.rmtree(p)
                else:
                    p.unlink()
        for child in moved_out:
            with contextlib.suppress(OSError):
                os.replace(scratch / child.name, child)
        raise BoostError("restore failed while swapping the store: %s" % e,
                         hint="the previous store contents were put back") from e


def restore(tar_path: Path, root: Path, snap_id: str) -> None:
    """Replace the contents of ``root`` with the archive at ``tar_path``.

    Raises BoostError — with ``root`` exactly as it was — when the archive
    cannot be opened, is corrupt, or holds an entry the ``data`` filter refuses.
    """
    try:
        tf = tarfile.open(str(tar_path), "r:gz")  # noqa: SIM115  (opened in a try to translate the error; used via `with tf:` below)
    except (tarfile.TarError, OSError, EOFError) as e:
        raise BoostError("snapshot %s is unreadable: %s" % (snap_id, e),
                         hint=UNTOUCHED_HINT) from e
    # Next to the real store, so the swap is a rename on one filesystem.
    parent = root.resolve().parent
    staging = Path(tempfile.mkdtemp(dir=str(parent), prefix=".boost-restore-"))
    scratch = Path(tempfile.mkdtemp(dir=str(parent), prefix=".boost-restore-old-"))
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
        _swap_in(staging, root, scratch)
    finally:
        for d in (staging, scratch):
            with contextlib.suppress(OSError):
                util.rmtree(d)
