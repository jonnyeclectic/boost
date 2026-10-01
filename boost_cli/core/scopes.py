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
from pathlib import Path

from ..errors import BoostError
from . import paths

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


def project_root(start=None) -> Path | None:
    """Nearest enclosing project root at or above ``start`` (default: cwd).

    Walks up until a :data:`PROJECT_MARKERS` entry is found, returning ``None``
    if the filesystem root is reached without one. Walking up is the whole point:
    ``boost install --local`` run from ``src/deep/nested`` must write into the
    repo's ``.claude/skills``, not create a stray one three levels down.

    **This is the marker walk, not the answer to "where is the project".** That
    is :func:`resolve_base`, which adds the unmarked-directory fallback, and it
    is what every caller should use — a command that asks this one directly
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


def resolve_base(scope: str, base=None, start=None) -> Path | None:
    """Directory a scope materializes under — ``None`` for user scope.

    An explicit ``base`` always wins, so a re-materialization driven by a lock
    record (``update``, ``sync``) lands where the original install did rather
    than in whatever directory the command happens to be run from.

    Project scope with no explicit base resolves the nearest project root, and
    falls back to ``start``/cwd when there is none — an unmarked directory is
    still a perfectly good place to put a project's skills, and refusing would
    only be pedantry. The one directory that is never an acceptable fallback is
    ``$HOME``: writing "project" files there means writing into the very dirs
    user scope owns, so callers get ``None`` and can say so.
    """
    if base:
        return Path(base)
    if scope != SCOPE_PROJECT:
        return None
    found = project_root(start)
    if found is not None:
        return found
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
            return None
    with suppress(OSError):
        if here.resolve() == Path(paths.home()).resolve():
            return None
    return here


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
    """
    if not rel or not isinstance(rel, str) or Path(rel).is_absolute():
        return False
    try:
        anchor = Path(os.path.realpath(base))
        return Path(os.path.realpath((Path(base) / rel).parent)) == (
            anchor / rel).parent
    except (OSError, ValueError):
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
    """
    try:
        base_r = Path(base).resolve()
        path_r = Path(path).resolve()
        if base_r == path_r:
            return False
        return os.path.commonpath([str(base_r), str(path_r)]) == str(base_r)
    except (OSError, ValueError):
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
