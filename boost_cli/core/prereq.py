# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unmet prerequisites — :mod:`.deps`' pure rules, composed against this machine.

:mod:`.deps` answers "what does this frontmatter declare, and which of those
values could be an item name". This module is the half that needs the catalog
and the lock file to answer "and is it here?", so the two stay separately
testable: every rule below is exercised through an injected ``index``/
``installed`` rather than through ``$HOME``.

Why it exists at all: ``boost install`` has followed ``requires:`` since the
resolver landed, and a census of 461 tapped registries (62,310 entries) says
``requires:`` is the *narrowest* real spelling in use — 101 declared values
across 6 taps. The two that carry the signal were invisible to boost:
``skills:`` (1,323 values, 18 taps) and ``dependencies:`` (1,065 values, 17
taps). A user installing ``athola/claude-night-market``'s
``architecture-paradigms`` got no hint that it names five siblings it cannot
run without, because it spells them under ``dependencies:``.

**Report, never install.** The widened keys are surfaced as a line, and the
``requires:`` closure ``boost install`` already resolves stays the only thing
that auto-installs. Three measurements decide that:

* fan-out reaches 19 direct prerequisites (``nWave-ai/nWave``'s
  ``nw-functional-software-crafter``) and the transitive closure reaches 35
  items, so "install what it needs" can quietly become a 35-item install;
* the graph has cycles — ``pr-review`` ⇄ ``review-chamber`` and
  ``code-refinement`` ⇄ ``safety-critical-patterns`` — so any traversal needs
  the seen-set a report does not;
* ``sparesparrow/cursor-rules`` lists **rules** under ``dependencies:``, and
  installing a rule edits a file the user reads every session (see the
  CLAUDE.md note on ``rules.CONTEXT_FILES``). Auto-installing those on the
  back of someone else's frontmatter is the most invasive thing boost can do
  from the least reliable input it has.

The floor this has to clear is silence, and that is why
:func:`deps.unmet_prerequisites` drops anything it cannot resolve without
comment rather than warning about it.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from itertools import chain
from typing import NamedTuple

from . import catalog, deps, lockfile, projectlock


class ItemPrereqs(NamedTuple):
    """One installed/requested item and the prerequisites it is missing."""

    name: str
    tap: str
    kind: str
    unmet: list[deps.Unmet]


def name_index(entries: Iterable[Mapping] | None = None,
               names: Iterable[str] | None = None) -> dict[str, list[str]]:
    """``{item name: [one tap per installable candidate]}``, in one pass.

    Built once and handed to every lookup rather than calling
    ``catalog.find`` per prerequisite: ``find`` is a scan of the whole corpus,
    which is ~62k rows on a real machine, and a single install can declare 19
    of them.

    The default corpus is :func:`catalog.cached_entries`, not
    ``all_entries()``: this is an advisory read bolted onto ``install`` and
    ``doctor``, and it must not rebuild a tap cache as a side effect of
    printing a hint (see that function). A tap whose cache is missing is
    invisible here, which usually costs an advisory line and nothing else.

    It can cost a *wrong* one, and the honest statement of the limit is that
    this index and ``catalog.resolve_one`` can read different corpora. A
    cache that is stale rather than absent — after a ``CACHE_FORMAT`` bump,
    or when ``~/.boost/cache`` is not writable — is served as-is here while
    the install path rescans. A name the stale rows show in one tap and the
    fresh scan shows in two then yields an unqualified ``spec`` that
    ``resolve_one`` refuses as ambiguous. The hint is wrong; the install it
    is printed beside is not, which is the trade this corpus is chosen for.

    The taps are **not** de-duplicated: the list has one entry per candidate
    ``catalog.distinct_candidates`` says a resolver would still have to
    choose between, so a name one registry ships twice under differing
    content appears twice and :func:`deps.unmet_prerequisites` can tell that
    ``boost install <name>`` would refuse it. Collapsing to a set of taps
    reported a one-command fix for exactly the case that has none.
    """
    wanted = None if names is None else frozenset(names)
    rows: dict[str, list] = defaultdict(list)
    for entry in (catalog.cached_entries() if entries is None else entries):
        name = entry.get("name")
        if name and (wanted is None or name in wanted):
            rows[name].append(entry)
    # The entries go through uncopied: `distinct_candidates` only reads them
    # (`test_it_does_not_mutate_what_it_is_handed`), and a `dict(entry)` per
    # row was 62k shallow copies on a real corpus for one `.get("tap")`.
    return {name: sorted(str(e.get("tap") or "")
                         for e in catalog.distinct_candidates(matches))
            for name, matches in rows.items()}


def installed_names(pbase=None) -> frozenset[str]:
    """Every installed skill, rule and workflow name, from one lock read.

    All three sections, matching ``pkg._expand_dependencies``: a prerequisite
    satisfied by an installed *rule* is satisfied.

    ``pbase`` adds a project's own lock (``projectlock.installed``). It is not
    optional polish: a ``--local`` install records nothing in the user lock,
    so ``boost install needy --local`` after ``boost install helper --local``
    named ``helper`` as missing when it was sitting in the same repo. A
    project install can also be satisfied by a user-scope one, so the two are
    unioned rather than switched between.
    """
    names = set(chain.from_iterable(lockfile.all_installed().values()))
    if pbase is not None:
        names |= set(projectlock.installed(pbase))
    return frozenset(names)


def for_entries(entries: Sequence[Mapping], *, installed=None, pbase=None,
                index: Mapping[str, Sequence[str]] | None = None,
                corpus: Iterable[Mapping] | None = None,
                ) -> list[ItemPrereqs]:
    """Unmet prerequisites for each catalog entry that has any.

    Entries with nothing missing are left out rather than returned empty, the
    same way :func:`installscan.scan` expresses a clean result. An item in
    ``entries`` counts as present for its siblings — installing three skills
    in one command must not report them as each other's missing prerequisite.

    ``corpus`` is the catalog to index against when ``index`` is not supplied,
    so a caller that has already read every entry (:func:`for_installed`) does
    not pay for a second read.
    """
    if not entries:
        return []
    # Read the frontmatter before touching the catalog or the lock. Most
    # installs declare nothing at all, and `name_index()` over a real 62k-row
    # corpus is pure CPU paid by the two commands run most often — so the
    # index is built only for names something actually asked for, and not at
    # all when nothing did.
    asked = [(e, deps.declared_prerequisites(e.get("meta"), e.get("name") or ""))
             for e in entries]
    asked = [(e, d) for e, d in asked if d]
    if not asked:
        return []
    if index is None:
        index = name_index(corpus,
                           names={p.name for _, ds in asked for p in ds})
    if installed is None:
        installed = installed_names(pbase)
    have = set(installed) | {e["name"] for e in entries if e.get("name")}
    rows: list[ItemPrereqs] = []
    for entry, declared in asked:
        name = entry.get("name") or ""
        tap = entry.get("tap") or ""
        unmet = deps.unmet_prerequisites(
            declared, tap=tap, installed=have,
            taps_for=lambda n: index.get(n, ()))
        if unmet:
            rows.append(ItemPrereqs(name, tap, entry.get("kind") or "skill",
                                    unmet))
    return rows


def for_installed() -> list[ItemPrereqs]:
    """Unmet prerequisites across everything currently installed.

    The catalog entry is looked up by name, preferring the tap the lock
    recorded, so the declaration read is the one the installed copy came
    from. An installed item whose tap is gone is skipped — there is no
    frontmatter left to read, and guessing from a same-named entry in another
    registry would report a prerequisite the user never declared.
    """
    entries = catalog.cached_entries()
    installed = lockfile.all_installed()
    have = frozenset(chain.from_iterable(installed.values()))
    picked: dict[tuple[str, str], dict] = {}
    for kind, section in installed.items():
        for name, rec in section.items():
            lk = rec if isinstance(rec, dict) else {}
            if not lk.get("tap"):
                # No recorded source, so there is no frontmatter this copy
                # provably came from. `catalog.find(name)` would take
                # `matches[0]` from whichever registry sorts first and report
                # a prerequisite the user never declared.
                continue
            matches = catalog.find(name, lk["tap"], entries)
            if not matches:
                continue
            # Not `matches[0]`: one tap can vendor a name into several
            # directories with *different* frontmatter, and scan order is not
            # what got installed. The lock says which copy it was, and
            # `select_lock_source` is the same resolution `boost sync` uses.
            # Its warning is dropped on purpose — this is a hint, and it
            # already falls back to `matches[0]` when the lock cannot say.
            chosen, _ = catalog.select_lock_source(matches, lk)
            entry = dict(chosen or matches[0])
            entry["kind"] = entry.get("kind") or kind
            # Keyed by kind as well as name: a rule and a skill may share a
            # name, and one `by_name` slot silently dropped whichever section
            # came first along with its declarations.
            picked[(kind, name)] = entry
    return for_entries(list(picked.values()), installed=have, corpus=entries)


def install_hint(rows: Sequence[ItemPrereqs]) -> str:
    """The single ``boost install`` command that would meet every unmet row.

    De-duplicated and ordered, so two items missing the same sibling name it
    once. Each spec is already qualified when the name is ambiguous, because
    boost refuses an unqualified name carried by more than one tap.

    Nothing unmet is the empty string, not ``"boost install "``: callers
    interpolate this into a line they are already printing, and a bare
    ``boost install`` is a usage error, not a fix.
    """
    specs: list[str] = []
    for row in rows:
        for miss in row.unmet:
            if miss.spec not in specs:
                specs.append(miss.spec)
    return ("boost install %s" % " ".join(specs)) if specs else ""
