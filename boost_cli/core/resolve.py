# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Skill dependency resolution — turn a set of requested skills into the full,
correctly-ordered install list by following each skill's ``requires:`` closure.

boost skills declare relationships in frontmatter (``requires:`` /
``conflicts:``); until now those were only *displayed* (``boost info`` /
``boost deps``). This module is the resolver that makes ``boost install`` act on
them — the "Homebrew installs dependencies" behavior — as a pure, dependency-
injected function so it is unit- and mutation-testable with no catalog or
filesystem access.

The caller supplies two lookups so the core stays I/O-free:

* ``requires_of(name) -> list[str]`` — the skills ``name`` declares it needs.
* ``conflicts_of(name) -> list[str]`` — the skills ``name`` declares it clashes
  with (optional; defaults to none).

and, optionally, ``known(name) -> bool`` to tell a resolvable dependency from a
dangling one (a ``requires:`` naming a skill in no tap). Everything else is
plain graph work.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

__all__ = ["Resolution", "resolve"]


@dataclass
class Resolution:
    """The outcome of resolving a set of requested skills.

    * ``order`` — the install order, dependencies before dependents, with
      already-installed skills that were only pulled in as dependencies dropped.
      A *requested* skill stays in ``order`` even when already installed (so an
      explicit ``boost install x`` still reinstalls/upgrades it, matching the
      pre-resolver behavior).
    * ``added`` — the transitive dependencies that were pulled in (``order``
      minus the requested roots), in install order — what to tell the user got
      added on their behalf.
    * ``conflicts`` — ``(skill, clashes_with)`` pairs where a skill in the plan
      declares a ``conflicts:`` against something already installed or also
      being installed. Advisory (a warning), never a hard failure.
    * ``unresolved`` — required skill names with no known source (a dangling
      ``requires:``); surfaced so the caller can warn rather than crash.
    """

    order: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    conflicts: list[tuple[str, str]] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)


def _norm(names: Sequence[str]) -> list[str]:
    """De-dupe a name sequence preserving first-seen order."""
    seen: list[str] = []  # noqa: FURB138  the guard below reads `seen` itself — not expressible as a comprehension
    for n in names:
        if n and n not in seen:
            seen.append(n)
    return seen


def resolve(
    roots: Sequence[str],
    requires_of: Callable[[str], Sequence[str]],
    conflicts_of: Callable[[str], Sequence[str]] | None = None,
    *,
    installed: frozenset[str] = frozenset(),
    known: Callable[[str], bool] | None = None,
) -> Resolution:
    """Resolve ``roots`` plus their ``requires:`` closure into an install plan.

    Post-order depth-first traversal yields dependencies before the skills that
    need them. The traversal is cycle-safe (a skill on the current DFS stack is
    not re-entered) and each skill is visited once. A dependency that is already
    ``installed`` is not re-added; a *requested* root is always kept so an
    explicit reinstall/upgrade still happens. Unknown dependencies (per
    ``known``) are recorded in ``unresolved`` and not traversed further.
    """
    conflicts_of = conflicts_of or (lambda _n: [])
    known = known or (lambda _n: True)
    roots = _norm(roots)
    root_set = set(roots)

    order: list[str] = []
    done: set = set()      # fully-processed (post-order emitted)
    on_stack: set = set()  # currently being visited — cycle guard
    unresolved: list[str] = []

    def visit(name: str, is_root: bool) -> None:
        if name in done or name in on_stack:
            return  # already emitted, or a cycle — stop
        # An already-installed skill pulled in only as a dependency is assumed
        # satisfied — don't re-traverse or re-emit its subtree. (A requested root
        # is still walked so an explicit reinstall re-checks its deps; gap-filling
        # of a broken installed skill is `boost heal`'s job, not install's.)
        if name in installed and not is_root:
            done.add(name)
            return
        on_stack.add(name)
        for dep in _norm(list(requires_of(name) or [])):
            if dep == name:
                continue  # a self-require is a no-op, never a cycle error
            if not known(dep):
                if dep not in unresolved:
                    unresolved.append(dep)
                continue
            visit(dep, is_root=False)
        on_stack.discard(name)
        done.add(name)
        # Emit unless it is an already-installed skill pulled in only as a dep;
        # a requested root is always emitted (reinstall/upgrade semantics).
        if is_root or name not in installed:
            order.append(name)

    for r in roots:
        visit(r, is_root=True)

    added = [n for n in order if n not in root_set]

    # Conflict scan: anything in the plan (being installed) OR already installed
    # is a live presence; flag a declared conflict against any live presence.
    live = set(order) | set(installed)
    conflicts: list[tuple[str, str]] = []
    seen_pairs: set = set()
    for skill in order:
        for clash in _norm(list(conflicts_of(skill) or [])):
            if clash == skill or clash not in live:
                continue
            key = (skill, clash)
            if key not in seen_pairs:
                seen_pairs.add(key)
                conflicts.append(key)

    return Resolution(order=order, added=added,
                      conflicts=conflicts, unresolved=unresolved)
