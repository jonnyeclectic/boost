# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Install scope: ``user`` (your machine) vs ``project`` (this repo).

boost was user-global by construction — one canonical store at
``~/.agents/skills`` symlinked out into ``~/.claude/skills`` and friends. That is
right for the skills *you* work with everywhere, and wrong for the ones a *team*
agrees on: those want to live in the repo, be reviewed in a PR, and arrive with a
``git clone`` rather than a setup doc nobody runs.

Project scope is the npm ``--save`` half of that pair. It materializes real
directories under the repo's own agent dirs (``<repo>/.claude/skills/<name>``),
never symlinks — a symlink into ``~/.agents/skills`` is meaningless on a
teammate's machine, so committing one would ship a dangling pointer.

This module is the pure logic: which directory is "the project", and where a
given scope puts a given skill. ``store`` owns the filesystem writes and
``projectlock`` owns the per-repo lock record.
"""
from __future__ import annotations

import os
import re
from contextlib import suppress
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import cast

from ..errors import BoostError
from . import paths, projectlock

SCOPE_USER = "user"
SCOPE_PROJECT = "project"
SCOPES = (SCOPE_USER, SCOPE_PROJECT)

# What makes a directory "the project root", cheapest and most decisive first.
# ``.git`` is a directory in a normal clone but a *file* inside a git worktree or
# submodule, so both are accepted.
#
# Deliberately version-control markers only. ``.boost`` looks tempting — a repo
# boost has already written into would keep resolving to the same root — but
# boost's own state dir is ``~/.boost``, so it would make ``$HOME`` a project
# root for everybody, and ``--local`` from any non-repo directory would quietly
# write into the user's real ``~/.claude/skills`` and collide with their
# user-scope installs. The project marker has to be something only a project
# has.
PROJECT_MARKERS = (".git", ".hg", ".svn")

# A skill name becomes a path component under someone's repo, so it is validated
# before it is ever joined — the same rule the canonical store applies.
_SAFE_NAME = re.compile(r"[A-Za-z0-9._-]+")

# How :func:`project_base` decided, so a caller can tell the two apart without
# walking the tree a second time and risking a different answer than the walk
# that actually chose the directory.
BASE_VCS = "vcs"            # a PROJECT_MARKERS entry at or above the start
BASE_UNMARKED = "unmarked"  # none — the start directory becomes a project


def project_root(start=None) -> Path | None:
    """Nearest enclosing project root at or above ``start`` (default: cwd).

    Walks up until a :data:`PROJECT_MARKERS` entry is found, returning ``None``
    if the filesystem root is reached without one. Walking up is the whole point:
    ``boost install --local`` run from ``src/deep/nested`` must write into the
    repo's ``.claude/skills``, not create a stray one three levels down.

    **This is the marker walk, not the answer to "where is the project".** That
    is :func:`resolve_base`, which adds the unmarked-directory fallback on top
    of it, and it is what every caller should use — a command that asks this one directly
    disagrees with ``install --local`` about whether an unmarked directory is a
    project, which is how ``verify``/``list``/``doctor``/``uninstall`` came to
    deny skills that ``install`` had just written and ``sync`` could still see.

    ``$HOME`` is never a project, even when it is itself a repo (dotfile setups
    do this). A "project" install into ``$HOME`` would write to exactly the
    directories user scope owns — ``~/.claude/skills`` and friends — so the two
    scopes would silently be the same place, which is the one outcome the split
    exists to prevent.
    """
    try:
        here = Path(start).resolve() if start is not None else Path.cwd().resolve()
    except OSError:
        return None
    try:
        home = Path(paths.home()).resolve()
    except OSError:
        home = None
    for d in (here, *here.parents):
        if home is not None and d == home:
            return None
        for marker in PROJECT_MARKERS:
            if (d / marker).exists():
                return d
    return None


def project_lock_root(start=None) -> Path | None:
    """Nearest ancestor at or above ``start`` that already holds a project lock.

    **This does not decide where anything is written.** It is an advisory
    answer to "is there already a boost project up there?", used by
    ``install --local`` to name it in the warning it prints when it is about
    to start a new one. :func:`project_base` is what decides the directory,
    and it consults version control markers and nothing else.

    It is deliberately not in the resolution path, and the reason is worth
    recording because the roadmap card that produced this function proposed
    putting it there. Moving the resolved base *up* to an ancestor lock
    orphans every rule and workflow already recorded *below* it: those are
    kept in the **user** lock tagged with an absolute ``base``
    (``store._install_rule``), and ``--local`` eligibility is
    :func:`owns` against the base resolved right now. So one
    ``install <skill> --local`` at ``proj`` would make a rule installed at
    ``proj/src`` invisible to ``list --local`` and unremovable by
    ``uninstall --local`` — from ``proj/src`` as much as from ``proj`` — with
    ``uninstall`` saying "installed in proj/src, not in this project" to
    somebody standing in ``proj/src``. Verification reproduced that end to
    end. The walk also only ever engages for skills: ``_install_rule`` and
    ``_install_workflow`` write no project lock at all, so it would fix one
    kind of three.

    **The marker is the lock file, not the ``.boost`` directory**, and that is
    the whole reason this can exist beside the note on :data:`PROJECT_MARKERS`
    refusing ``.boost``. boost's own state dir is ``~/.boost`` and it holds a
    ``config.json``, a ``cache/`` and a ``state/`` — never a
    ``skill-lock.json``, which only :mod:`.projectlock` writes and only into a
    project. So the one directory a ``.boost`` marker would have wrongly
    claimed is the one this never matches, and ``$HOME`` is refused outright
    below regardless.
    """
    try:
        here = Path(start).resolve() if start is not None else Path.cwd().resolve()
    except OSError:
        return None
    try:
        home = Path(paths.home()).resolve()
    except OSError:
        home = None
    for d in (here, *here.parents):
        if home is not None and d == home:
            return None
        if projectlock.exists(d):
            return d
    return None


def project_base(start=None) -> tuple[Path | None, str | None]:
    """Where project scope materializes, **and how that was decided**.

    One walk, one answer. ``install --local`` has to warn when it is the call
    that creates the project, and re-deriving *that* in the command layer
    would mean a second walk that can disagree with the one that chose the
    directory — the exact shape of the reader/writer split ``fix(scope)``
    closed. So the decision is made once, here, and the reason travels with
    it. (The command layer does call :func:`project_lock_root` afterwards, to
    name an existing project in the warning text. That one decides no
    destination, so it cannot disagree with anything.)

    Returns ``(None, None)`` when there is nowhere to put a project — standing
    in ``$HOME``, or with no working directory at all.
    """
    found = project_root(start)
    if found is not None:
        return found, BASE_VCS
    if start is not None:
        here = Path(start)
    else:
        try:
            here = Path.cwd()
        except OSError:
            # No cwd to fall back to — a working directory deleted out from
            # under the process. `project_root` has always answered None here;
            # this must too, or the readers that now come through this function
            # crash where they used to print a user-scope answer and exit 0.
            return None, None
    with suppress(OSError):
        if here.resolve() == Path(paths.home()).resolve():
            return None, None
    return here, BASE_UNMARKED


def resolve_base(scope: str, base=None, start=None) -> Path | None:
    """Directory a scope materializes under — ``None`` for user scope.

    An explicit ``base`` always wins, so a re-materialization driven by a lock
    record (``update``, ``sync``) lands where the original install did rather
    than in whatever directory the command happens to be run from.

    Project scope with no explicit base defers to :func:`project_base`: the
    nearest version control root, else ``start``/cwd — an unmarked directory
    is still a perfectly good place to put a project's skills, and refusing would only be
    pedantry. The one directory that is never an acceptable fallback is
    ``$HOME``: writing "project" files there means writing into the very dirs
    user scope owns, so callers get ``None`` and can say so.

    This keeps the path and drops the kind. A caller that needs to know
    *which* of the three answered — ``install --local`` warns when it is the
    call that creates the project — takes the pair from :func:`project_base`
    rather than walking again.
    """
    if base:
        return Path(base)
    if scope != SCOPE_PROJECT:
        return None
    return project_base(start)[0]


def owned_by(entries: dict, base) -> dict:
    """The entries of ``entries`` this project owns — ``{}`` when ``base`` is None.

    Rules and workflows installed with ``--local`` materialize into the repo but
    are recorded in the *user* lock, tagged ``scope``/``base``, because a project
    lock holds skills and nothing else. So "what has this repo got?" is a filter
    over the user lock, not a different file, and a caller that skips the filter
    reports another checkout's rules as this one's.

    Both sides are resolved before comparing. ``base`` reaches the lock as a
    string written by whichever call installed it, and on macOS a ``$HOME``
    under ``/var/folders`` resolves to ``/private/var/...`` — comparing one
    resolved path against one nominal one never matches, the same trap
    :func:`store.resolves_into_store` documents. ``realpath`` rather than
    ``Path.resolve``: it answers for a path that does not exist or loops
    instead of raising, so there is no error branch here that no input can
    reach and no test can cover.
    """
    if base is None:
        return {}
    want = os.path.realpath(base)
    return {n: e for n, e in entries.items() if _owns(e, want)}


def owns(entry: dict, base) -> bool:
    """Does one user-lock entry belong to the project rooted at ``base``?

    The single-entry form of :func:`owned_by`, and the same predicate rather
    than a second opinion about it — ``list --local`` decides what a repo has
    with the filter, and ``uninstall --local`` decides what it may remove with
    this, so the two cannot disagree about one row.

    **Both halves are load bearing, and the ``scope`` half defends a shape
    boost's own install path does not write.** ``_install_rule`` and
    ``_install_workflow`` emit ``scope`` and ``base`` in one dict, so the two
    agree on every row an install produces. Two things read a row back and do
    not: a hand-edited lock — the project lock is a *committed* file — and
    ``update``/``reinstall``, which rebuild the install from
    ``lk.get("scope", "user")`` and ``lk.get("base")`` *independently*
    (``commands/pkg.py``), so a row carrying a ``base`` and no ``scope`` comes
    back as user scope with the base intact. Dropping the ``scope`` test would
    hand ``--local`` that row, which lives in the user's own config.

    ``False`` for ``base is None`` — a caller standing outside any project
    owns nothing — which is answered before ``realpath``, since resolving
    ``None`` is a TypeError rather than an answer.
    """
    if base is None:
        return False
    return _owns(entry, os.path.realpath(base))


def _owns(entry: dict, want: str) -> bool:
    """:func:`owns` over an already-resolved ``want``, for the bulk filter."""
    return entry.get("scope") == SCOPE_PROJECT and _claims(entry.get("base"), want)


def _claims(recorded, want: str) -> bool:
    """Does a lock entry's recorded ``base`` name the directory ``want``?

    A lock is a file on disk that anything can write, so this takes what it
    finds rather than what it expects: a `base` that is missing, empty, not a
    string, or *relative* is not a claim on any particular directory. Relative
    is the one that looks harmless and is not — `realpath` would resolve it
    against whatever directory the user happens to be standing in, so `"."`
    would make one entry belong to every repo at once.
    """
    if not names_a_directory(recorded):
        return False
    return os.path.realpath(recorded) == want


def names_a_directory(recorded) -> bool:
    """Is a recorded ``base`` a claim on *some* directory at all?

    The half of :func:`_claims` that needs no directory to compare against,
    split out because one caller has none to offer: ``store`` decides whether
    a removal result may *name* the repo it came from, where the question is
    only whether the lock recorded a directory. Sharing the predicate is the
    point — a base this rejects is one no project claims, so a result that
    named it would print a repo that owns nothing.

    The three clauses are **ordered, not independent**. ``isabs`` raises
    ``TypeError: expected str, bytes or os.PathLike object, not dict`` on a
    hand-edited lock's ``{"base": {}}``, so the ``isinstance`` test has to
    come first and is what makes the last one safe to call at all. ``bool``
    first is for reading, not for filtering: ``isabs("")`` is already False,
    so the empty case would be caught anyway, and saying so up front is
    cheaper than making the reader work it out.

    What it rejects that a plain truthiness check does not is therefore two
    things: a *truthy* non-string, and a *relative* path — which ``realpath``
    would resolve against wherever the user happens to be standing, making
    one entry belong to whichever repo is read from.
    """
    return (bool(recorded) and isinstance(recorded, str | os.PathLike)
            and os.path.isabs(recorded))


def stranded(entry: dict) -> bool:
    """Is a user-lock row a ``--local`` install whose repo no longer exists?

    Rules and workflows installed with ``--local`` are recorded in the *user*
    lock against an absolute ``base`` (see :func:`owned_by`), and the
    materialization rows under it are absolute too — so a reader standing in
    any other directory can still grade a sibling checkout's rule, and does so
    correctly. What it cannot do is grade one whose checkout has been
    deleted: every artifact reads as missing, and every remedy that answers
    "missing" (`boost reinstall`, `boost sync`, `boost heal`, `boost update`)
    re-materializes into the recorded ``base`` and so *recreates the deleted
    directory* with a ``.cursor/`` and a ``CLAUDE.local.md`` in it. The record
    is the fault, and ``boost uninstall <name>`` — which drives off the rows
    and never creates anything — is its one remedy.

    Both halves are the same as :func:`owns`'s, for the same reason: a row
    with a ``base`` and no ``scope`` is user scope, and a ``base`` that names
    no directory (missing, relative, not a string) is not a claim on one, so
    neither can be stranded. ``isdir`` on the *recorded* path, not
    ``realpath``: the question is whether the directory is there, not which
    one it is.
    """
    base = entry.get("base")
    return (entry.get("scope") == SCOPE_PROJECT and names_a_directory(base)
            and not os.path.isdir(cast(str, base)))


def check_scope(scope: str) -> str:
    """Return ``scope`` if it is one boost knows, else raise BoostError."""
    if scope not in SCOPES:
        raise BoostError("unknown scope %r" % scope,
                         hint="use one of: %s" % ", ".join(SCOPES))
    return scope


def agent_root(skills_dir, base=None, dotdir=None) -> Path:
    """The agent's config root for a scope (``~/.claude`` or ``<base>/.claude``).

    The dotdir name is taken from the agent's *configured* skills dir rather than
    hardcoded, so an agent someone added by hand in ``config.json`` lands in the
    project under the same name it uses at home. ``dotdir`` overrides that for
    an agent whose user dir can move at runtime while its repo-scope path
    cannot — pass :func:`agents.project_dotdir`, which knows which is which.
    User scope never consults it: there the answer is the real parent.
    """
    skills_dir = Path(skills_dir)
    if base is None:
        return skills_dir.parent
    return Path(base) / (dotdir or skills_dir.parent.name)


def skill_target(skills_dir, name: str, base=None, dotdir=None) -> Path:
    """Where skill ``name`` materializes for one agent under a scope.

    User scope (``base=None``) is the agent's own skills dir — that is where the
    canonical store's symlink goes. Project scope is the matching directory
    inside the repo: ``<base>/.claude/skills/<name>``. The leaf directory name is
    carried over from the configured path, so a non-standard ``skills`` folder
    name survives into the project.
    """
    # `name or ""` is load-bearing: a name can arrive as None from a committed
    # lock record, and fullmatch(None) raises TypeError instead of the BoostError
    # this path-safety guard exists to raise.
    if not _SAFE_NAME.fullmatch(name or "") or name in {".", ".."}:  # noqa: FURB143
        raise BoostError("invalid skill name %r" % name)
    skills_dir = Path(skills_dir)
    return agent_root(skills_dir, base, dotdir) / skills_dir.name / name


def describe(scope: str, base=None) -> str:
    """Short human phrase for a scope, used in confirmations and dry runs."""
    if scope == SCOPE_PROJECT:
        return "this project (%s)" % (Path(base).name if base else "cwd")
    return "your user config"


def relative_to_base(base, path) -> str:
    """``path`` as a ``/``-separated path relative to ``base``.

    The project lock is committed and read on other people's machines, so an
    absolute path in it is wrong the moment it leaves the author's laptop —
    a different clone directory, a different OS, a different username. Records
    store the relative form and re-derive the absolute one at use time.
    Separators are normalized to ``/`` so a lock written on Windows resolves on
    macOS and Linux.
    """
    rel = Path(path).relative_to(Path(base))
    return str(rel).replace(os.sep, "/")


def resolve_in_base(base, rel: str) -> Path | None:
    """A lock-recorded relative path, re-anchored under ``base``.

    Returns ``None`` for anything that does not land inside ``base`` — an empty
    string, an absolute path, or one that climbs out with ``..``. This is the
    single place a committed record turns back into a filesystem path, so it is
    where a doctored one gets refused rather than at each call site.
    """
    if not rel or not isinstance(rel, str):
        return None
    candidate = Path(base) / rel
    if Path(rel).is_absolute() or not contains(base, candidate):
        return None
    return candidate


def parent_matches_spelling(base, rel: str) -> bool:
    """True when walking to ``rel``'s parent is not redirected on the way.

    The third question about a committed path, and the one the other two miss.
    :func:`contains` resolves and answers "does this end up inside the repo?".
    :func:`resolve_in_base` returns the path *unresolved*, so an identity check
    can compare the strings an install writes. Between them sits a row that is
    contained, and spelled exactly like a legal path, and still points
    somewhere else: a committed ``<repo>/.claude/skills -> ../src`` makes the
    row ``.claude/skills/<name>`` string-equal to the legal target while
    denoting ``src/<name>``. The leaf is honest and an ancestor is not, so a
    guard that only inspects the leaf walks straight through it and
    ``rmtree`` takes the victim.

    So the parent is walked for real and compared against where the spelling
    says it should be, anchored on the **real** base. ``realpath`` on both
    sides, because a repo can sit *under* a symlink without containing one —
    a checkout below ``/tmp`` on macOS, a home directory behind an automount,
    a worktree reached through a convenience link. Resolve the walk and not
    the base and every row of such a repo is compared real-against-nominal,
    matches nothing, and is refused. The symlinked-base test builds that
    link itself rather than relying on the runner's ``$TMPDIR``, which pytest
    resolves before a test ever sees it.

    The leaf itself is deliberately left unresolved. A materialization that
    *is* a symlink is boost's own, and ``util.remove_path`` unlinks it without
    following it — judging it by what it points at is the bug one layer down.

    **Absolute is asked of both platforms, not of the one running.** A plain
    ``Path(rel)`` is a ``WindowsPath`` on Windows, where ``/etc/passwd``
    carries no drive and ``is_absolute()`` is therefore ``False``. The join
    then yields ``C:\\etc\\passwd`` — outside the base — and *both sides of
    comparison leave it the same way*, so the walk agrees with itself and this
    answers True for a path that is not in the repo at all. All three
    ``tests (windows-latest, 3.1x)`` jobs said so the first time these clauses
    were tested directly. The mirror case is a drive letter or a UNC path,
    which ``PurePosixPath`` does not call absolute either. A lock is a
    committed file and the machine that wrote a row need not be the one
    reading it, so the spelling to refuse is whatever is absolute *anywhere*.
    A posix directory genuinely named ``C:`` is refused as collateral, which
    is the safe direction for a guard whose other answer hands ``rmtree`` a
    target.

    **The NUL is refused by name, on both arguments.** Relying on ``realpath``
    to raise is relying on the half of the behaviour that differs: posix
    raises ``ValueError`` and the ``except`` catches it, Windows does not
    raise and the guard returned True. ``base`` is checked as well as ``rel``
    because it has the same provenance — ``store`` derives it from the lock's
    own recorded ``base`` — and none of the ``rel`` clauses can see it.
    """
    if not rel or not isinstance(rel, str):
        return False
    if PurePosixPath(rel).is_absolute() or PureWindowsPath(rel).is_absolute():
        return False
    try:
        if "\x00" in rel or "\x00" in os.fspath(base):
            return False
        anchor = Path(os.path.realpath(base))
        return Path(os.path.realpath((Path(base) / rel).parent)) == (
            anchor / rel).parent
    except (OSError, TypeError, ValueError):
        return False


def contains(base, path) -> bool:
    """True when ``path`` sits inside ``base`` — the guard before any delete.

    A project uninstall removes directories recorded in a lock file that lives in
    a repo and is meant to be committed, so the paths in it are attacker-adjacent
    in a way the user-scope store's never are: anyone who can land a PR can edit
    them. Every removal is therefore re-derived and checked against the base
    before it happens, so a doctored record cannot walk boost out of the project.

    Fails closed on every error. ``commonpath`` raises ``ValueError`` for paths
    with no common root — on Windows that is any two different drives, so a repo
    on ``C:`` weighed against a record pointing at ``D:`` would otherwise crash
    out of the delete guard rather than answer "outside".

    **A spelling mismatch is settled by the disk, not by folding case.**
    ``resolve()`` does not canonicalize case on macOS's case-insensitive APFS:
    ``/users/jonny/.claude`` comes back as spelled, and against a ``$HOME`` of
    ``/Users/jonny`` the string test says "outside" for a directory that is
    inside. ``os.path.normcase`` cannot fix that — it is the identity on posix
    — and folding by hand would be wrong on a case-sensitive disk, where
    ``/home/A`` and ``/home/a`` are two directories. So when, and only when,
    the string test answers "outside", each existing ancestor of ``path`` is
    asked whether it *is* ``base`` (same ``st_dev`` and ``st_ino``). That
    answer comes from the filesystem, so it folds case exactly where the disk
    does. ``path`` itself is not asked, so ``base`` still does not contain
    itself; a ``ValueError`` from ``commonpath`` still answers "outside"
    without consulting it (two drives cannot be case variants of one
    directory); and an inode of 0 — what a filesystem with no stable inode
    reports — matches nothing.
    """
    try:
        base_r = Path(base).resolve()
        path_r = Path(path).resolve()
        if base_r == path_r:
            return False
        if os.path.commonpath([str(base_r), str(path_r)]) == str(base_r):
            return True
        return _ancestor_is(path_r, base_r)
    except (OSError, ValueError):
        return False


def _ancestor_is(path_r: Path, base_r: Path) -> bool:
    """True when some proper ancestor of ``path_r`` is the directory ``base_r``.

    Identity is ``(st_dev, st_ino)``, never the spelling — see :func:`contains`.
    An ancestor that does not exist (the tail of a file not yet written) is
    skipped; a ``base`` that cannot be stat'ed, or reports no inode, matches
    nothing.
    """
    base_st = os.stat(base_r)
    if not base_st.st_ino:
        return False
    for anc in path_r.parents:
        try:
            st = os.stat(anc)
        except OSError:
            continue
        if os.path.samestat(st, base_st):
            return True
    return False


def ensure_in_base(base, path):
    """Raise if ``path`` would resolve outside ``base`` — the guard before any
    project-scope WRITE, the mirror of :func:`contains` before every delete.

    A project destination is built from directory names committed in the repo
    (``.claude/skills`` and its per-agent siblings). A hostile repo can ship one
    of those as a symlink pointing outside the tree — at ``~/.ssh``, say — and
    the ``mkdir(parents=True)`` + ``os.replace`` that materializes a skill would
    then run on the far side, escaping the project entirely. The squatter check
    (refuse to overwrite a path boost did not create) does not stop this:
    dropping a *new* name like ``authorized_keys`` collides with nothing, and
    ``--force`` waives it regardless. ``contains`` resolves symlinks on both
    ends, so re-deriving containment here — before the write, independent of
    existence or force — is the boundary that actually holds. Returns ``path``
    so a caller can wrap the target inline.
    """
    if not contains(base, path):
        raise BoostError(
            "refusing to install %s: it resolves outside this project" % path,
            hint="a directory such as .claude/skills in this repo is a symlink "
                 "pointing outside it — remove or replace it, then reinstall")
    return Path(path)


def ensure_spelled(base, path):
    """Raise if the walk to ``path`` is bent by a symlink inside ``base``.

    The write-side twin of the check ``store.uninstall_project`` makes before
    every delete, and the same predicate (:func:`parent_matches_spelling`) on
    purpose, so install and uninstall cannot disagree about one row again.
    They did: :func:`ensure_in_base` is containment only, so a committed
    ``<repo>/.cursor -> config/cursor`` let ``install --local`` write
    ``config/cursor/skills/<name>`` and record ``.cursor/skills/<name>`` —
    a row uninstall then refuses, because that layout is byte-identical to
    the attack ``.claude/skills -> ../src``. The copy was orphaned and the
    lock entry went anyway.

    The other two ways to make them agree both loosen the delete guard.
    Recording the *resolved* path puts a row outside the derived set
    uninstall accepts, so it would have to start resolving — the hole its
    docstring names — and the row is meaningless on a teammate's clone whose
    link points elsewhere. Recording both widens it further. So the install
    refuses, before anything is written, and the hint names the two ways out.

    A symlink *above* ``base`` is not a redirect: the predicate anchors on the
    real base, so a checkout under ``/tmp`` on macOS still installs. Returns
    ``path`` so a caller can wrap the target inline.
    """
    rel = relative_to_base(base, path)
    if not parent_matches_spelling(base, rel):
        raise BoostError(
            "refusing to install into %s: a symlink inside this project "
            "redirects it to %s, and `boost uninstall --local` will not delete "
            "through a symlink it did not create"
            # Relative to the real base: `ensure_in_base` runs first, so the
            # far side is inside the repo, and that is the spelling a user
            # recognises from their own tree.
            % (rel, os.path.relpath(os.path.realpath(str(path)),
                                    os.path.realpath(str(base))).replace(os.sep, "/")),
            hint="replace the symlinked directory with a real one, or leave "
                 "that agent out with `--agent`")
    return Path(path)
