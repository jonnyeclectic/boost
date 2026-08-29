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
    here = Path(start) if start is not None else Path.cwd()
    with suppress(OSError):
        if here.resolve() == Path(paths.home()).resolve():
            return None
    return here


def check_scope(scope: str) -> str:
    """Return ``scope`` if it is one boost knows, else raise BoostError."""
    if scope not in SCOPES:
        raise BoostError("unknown scope %r" % scope,
                         hint="use one of: %s" % ", ".join(SCOPES))
    return scope


def agent_root(skills_dir, base=None) -> Path:
    """The agent's config root for a scope (``~/.claude`` or ``<base>/.claude``).

    The dotdir name is taken from the agent's *configured* skills dir rather than
    hardcoded, so an agent someone added by hand in ``config.json`` lands in the
    project under the same name it uses at home.
    """
    skills_dir = Path(skills_dir)
    if base is None:
        return skills_dir.parent
    return Path(base) / skills_dir.parent.name


def skill_target(skills_dir, name: str, base=None) -> Path:
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
    return agent_root(skills_dir, base) / skills_dir.name / name


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
