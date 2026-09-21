# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""What `boost compact` will free, worked out before anything is freed.

`compact` has two modes and they remove different things, which is the whole
reason this module exists rather than one `rglob` in the command layer:

* the default narrows in place — `git sparse-checkout reapply`, which walks the
  **index**. A path git has never heard of is not in the index, so `reapply`
  leaves it exactly where it is. Counting the working tree therefore promised
  bytes the run could not free: a 1 MiB untracked `scripts/junk.bin` made
  `compact --dry-run` print "would free 1.0MB" and the live run print
  "every tap is already compact", with the file still on disk.
* `--reclone` is `rmtree` + a fresh blobless clone, so it removes the untracked
  freight *and* the clone's whole `.git` — and then re-downloads a `.git` whose
  size only the remote decides. So it frees strictly more than the default and
  its net figure is unknowable; see :class:`Plan`.

It lives in `core/` because deciding what a run removes is behavior, and the
mutation gate only sees `core/`. It is a module of its own rather than part of
`gitutil` because the question is not a git question: it mixes the cone (which
`gitutil` owns, derived in turn from catalog's constants — `gitutil` cannot
import `catalog`, catalog imports gitutil) with the lock file's `source_dir`
entries, which `gitutil` has no business knowing about. Nothing imports this
module, so it is free to sit above both.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from . import gitutil, util


@dataclass(frozen=True)
class Plan:
    """What one `compact` run will do to one tap clone.

    ``net`` is ``None`` for a reclone on purpose. The bytes removed are known
    (``freight`` + ``git_bytes``); the bytes that come back are whatever the
    remote sends for a fresh `--filter=blob:none --sparse` clone, which boost
    cannot know without making the clone it is only previewing. A dry run may
    not be more confident than the real run can be, so `--reclone` predicts the
    *action* and names its two measured components instead of inventing a total.
    """

    freight: int      #: working-tree bytes this run removes
    git_bytes: int    #: `.git` bytes this run removes (0 unless reclone)
    reclone: bool

    @property
    def net(self) -> int | None:
        """Bytes the clone will shrink by, or None when that is unknowable."""
        return None if self.reclone else self.freight

    @property
    def removes(self) -> int:
        """Bytes this run deletes, before anything is downloaded back."""
        return self.freight + self.git_bytes


def in_cone(rel: str | PurePosixPath, ignorecase: bool = False) -> bool:
    """True when the sparse cone keeps `rel` (a path relative to the clone).

    Derived from `gitutil.SPARSE_PATTERNS` rather than restating `*.md` here,
    for the same reason those patterns are derived from catalog's constants
    (`tests/unit/test_gitutil_sparse.py`): three literal lists of the same set
    drift, and the one that drifts silently is the one in a preview.

    A `--no-cone` pattern is gitignore syntax, so it is tested against every
    component of the path, not only the leaf. git matches a file and then each
    directory above it, and keeps the file if any of them matches. An
    unanchored `*.md` or `.clinerules` names a directory as readily as a file,
    and everything under a matched directory stays: a tracked
    `.clinerules/state/x.json` or `docs.md/run.py` survives `reapply`. Matching
    the leaf alone promised those bytes, and the live run freed none of them.
    The anchored `/.boost/*` is the exception. It matches only below a root
    `.boost` directory, so a root *file* called `.boost` is not kept.

    ``ignorecase`` is the clone's `core.ignorecase` (:func:`folds_case`), which
    git's own sparse matching follows: on macOS `*.md` keeps a `README.MD`, on
    Linux it drops it. The patterns are lowercase literals, so folding the path
    alone is enough.
    """
    parts = PurePosixPath(str(rel).lower() if ignorecase else rel).parts
    for pattern in gitutil.SPARSE_PATTERNS:
        if pattern.startswith("/") and pattern.endswith("/*"):
            if len(parts) > 1 and parts[0] == pattern[1:-2]:
                return True
        elif pattern.startswith("*"):
            if any(part.endswith(pattern[1:]) for part in parts):
                return True
        elif pattern in parts:
            return True
    return False


def folds_case(repo: Path) -> bool:
    """True when git matches paths in `repo` case-insensitively.

    git records `core.ignorecase = true` at clone time on a case-insensitive
    filesystem, and unset means false. Read with ``check=False`` so a clone git
    cannot open answers "no" here and fails in :func:`tracked_files` instead.
    """
    proc = gitutil.run(["-C", str(repo), "config", "--bool", "core.ignorecase"],
                       check=False)
    return proc.stdout.strip() == "true"


def tracked_files(repo: Path) -> set[str]:
    """Every path in `repo`'s index, as posix strings relative to the clone.

    Raises `BoostError` when git cannot read the directory — the same failure
    the real run takes one step later, so the preview reports it rather than
    answering "nothing to free" for a clone it never managed to read.
    """
    out = gitutil.run(["-C", str(repo), "ls-files", "-z"]).stdout
    return {p for p in out.split("\0") if p}


def _kept_prefixes(keep_dirs: list[str]) -> tuple[str, ...]:
    """`source_dir` entries as directory prefixes, e.g. `skills/demo/`."""
    return tuple("%s/" % d.strip("/") for d in keep_dirs)


def _off_cone_files(repo: Path, keep_dirs: list[str]):
    """Yield (rel, size) for each on-disk file the cone does not keep.

    `source_dir` keeps an installed skill's own assets on disk — `compact`
    re-materializes them after narrowing — so they are never freight, in either
    mode. `.git` is walked by neither: the default never touches it, and
    `--reclone` accounts for it whole through `util.dir_size`.
    """
    kept = _kept_prefixes(keep_dirs)
    fold = folds_case(repo)
    for f in Path(repo).rglob("*"):
        if not f.is_file() or f.is_symlink():
            continue
        # Relative to the tap, never absolute: every clone lives *under*
        # ~/.boost, so testing the absolute parts for ".boost" excluded every
        # file in every tap and reported that nothing could be freed.
        rel = f.relative_to(repo)
        if ".git" in rel.parts:
            continue
        posix = rel.as_posix()
        if in_cone(posix, fold) or posix.startswith(kept):
            continue
        yield posix, f.stat().st_size


def freight_bytes(repo: Path, keep_dirs: list[str]) -> int:
    """Bytes `git sparse-checkout reapply` will drop from `repo`.

    The index is the filter: `reapply` removes a path only if it is tracked.
    An untracked file outside the cone survives and must not be promised — the
    defect this function was rewritten to fix.

    It is an upper bound in one case left uncorrected: git also declines to
    remove a tracked path with local modifications. Chasing that would cost a
    `git status` over the clone for a state a tap should never be in (boost
    only ever reads a tap's tree), and it fails safe — over-promising by the
    size of a file the user edited by hand, not by a megabyte of build output.
    """
    tracked = tracked_files(repo)
    return sum(size for rel, size in _off_cone_files(repo, keep_dirs)
               if rel in tracked)


def worktree_freight_bytes(repo: Path, keep_dirs: list[str]) -> int:
    """Bytes a `--reclone` removes from the working tree — tracked or not.

    `--reclone` is `util.rmtree` followed by a fresh clone, so whether git knows
    about a file has no bearing on whether it survives. This is the count the
    default path used to use, and it was right only for this mode.
    """
    return sum(size for _rel, size in _off_cone_files(repo, keep_dirs))


def plan(repo: Path, keep_dirs: list[str], reclone: bool = False) -> Plan:
    """What `compact` will do to one clone, without doing any of it."""
    if reclone:
        return Plan(freight=worktree_freight_bytes(repo, keep_dirs),
                    git_bytes=util.dir_size(Path(repo) / ".git"),
                    reclone=True)
    return Plan(freight=freight_bytes(repo, keep_dirs), git_bytes=0,
                reclone=False)
