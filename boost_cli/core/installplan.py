# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""What an install means beyond the item named: its look-alikes, its
``requires:`` closure, and the prerequisites it declares but boost will not
install.

Every line here is a plain string, so two surfaces print the same words.
``boost install`` (``commands/pkg``) and the MCP ``boost_install`` tool used
to hold two separate opinions about what installing a name does: the CLI
pulled in ``requires:`` dependencies and warned about a typosquat, while the
MCP path, where an agent picks and installs with nobody watching a terminal,
did neither. Keeping the logic in ``core`` and the presentation in the
callers is what stops that drifting again.
"""
from __future__ import annotations

from ..errors import BoostError
from . import catalog, deps, prereq, resolve, typosquat


def _plural(n: int, word: str) -> str:
    return "%d %s%s" % (n, word, "" if n == 1 else "s")


def confusion_lines(entries: list[dict]) -> list[str]:
    """One warning per look-alike from a *different* tap (core.typosquat).

    Quiet by default: it only speaks up when a near-identical name resolves to
    another owner, which is exactly the fat-finger-into-a-look-alike case. An
    empty request never touches the catalog.
    """
    if not entries:
        return []
    corpus = catalog.all_entries()
    # One target scans the catalogue once (~60 ms at 63k entries), which is
    # cheaper than indexing it (~0.5 s); from two on, index once and look up.
    index = typosquat.build_index(corpus) if len(entries) > 1 else None
    return ["%s (%s) closely resembles %s (%s) — double-check you meant this "
            "one" % (e["name"], e["tap"], other["name"], other["tap"])
            for e in entries
            for other in typosquat.find_confusions(e, corpus,
                                                   index=index)[:3]]


def rel_list(meta: dict, key: str) -> list[str]:
    """A skill's `requires:`/`conflicts:` frontmatter as a clean name list."""
    val = meta.get(key)
    if val in (None, "", False) or isinstance(val, dict):
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    return [s.strip() for s in str(val).split(",") if s.strip()]


def skill_relations(name: str, key: str) -> list[str]:
    """`requires:`/`conflicts:` for a skill by name, from its catalog entry.

    ``requires:`` goes through :func:`deps.requirement_names`, the same
    filter ``boost deps`` applies, so the two cannot disagree about what a
    requirement *is*. Without it this path still fed prose and package
    coordinates to the resolver: `requires: ["gh (GitHub CLI)", "python3"]`
    printed "required skill 'gh (GitHub CLI)' is in no tap — skipped" while
    `boost deps` on the same skill, post-filter, listed nothing. A qualified
    `tap:name` survives the filter verbatim, because this feeds
    ``catalog.find``.
    """
    matches = catalog.find(name)
    if not matches:
        return []
    return entry_relations(matches[0], key)


def entry_relations(entry: dict, key: str) -> list[str]:
    """`requires:`/`conflicts:` read off one catalog entry's own frontmatter.

    Keyed by entry rather than by name because a name is not an item: with
    `jira-integration` in two taps, ``install beta:jira-integration`` planned
    alpha's `requires:` (the first ``find`` row) and skipped beta's.
    """
    meta = entry.get("meta") or {}
    if key == "requires":
        return deps.requirement_names(meta)
    return rel_list(meta, key)


def expand_dependencies(entries: list[dict], pbase=None
                        ) -> tuple[list[dict], resolve.Resolution]:
    """Grow the requested entries into their full `requires:` closure.

    Returns ``(ordered_entries, resolution)`` — the entries to install in
    dependency-first order (roots plus any pulled-in dependencies that are not
    already installed), and the :class:`resolve.Resolution` carrying what was
    added, any advisory conflicts, and unresolved (dangling) requirements.

    ``pbase`` is the project a ``--local`` install targets. Its lock counts as
    installed too: without it, ``install --local needy`` re-planned a ``helper``
    already in the repo, the forced-off reinstall refused it, and the command
    exited 1 over a requirement that was met.
    """
    # All three lock sections, not just skills: a rule or workflow already
    # installed under a required name must not be re-added to the plan.
    installed = prereq.installed_names(pbase)
    # One entry per name in the plan — the roots as the caller chose them, a
    # dependency as `resolve_one` picks it — and every relation is read off
    # that entry, so the item whose `requires:` was walked is the item that
    # gets installed.
    picked: dict[str, dict | None] = {e["name"]: e for e in entries}

    def entry_for(name: str) -> dict | None:
        if name not in picked:
            try:
                picked[name] = catalog.resolve_one(name)
            except BoostError:
                picked[name] = None
        return picked[name]

    def relations(name: str, key: str) -> list[str]:
        entry = entry_for(name)
        return entry_relations(entry, key) if entry is not None else []

    res = resolve.resolve(
        [e["name"] for e in entries],
        lambda n: relations(n, "requires"),
        lambda n: relations(n, "conflicts"),
        installed=installed,
        known=lambda n: bool(catalog.find(n)),
    )
    ordered: list[dict] = []
    for name in res.order:
        entry = entry_for(name)
        if entry is not None:
            ordered.append(entry)
        elif name not in res.unresolved:
            # A dep that resolves nowhere unambiguously is reported via
            # res.unresolved; skip it here rather than abort the whole install.
            res.unresolved.append(name)
    return ordered, res


def added_line(res: resolve.Resolution) -> str | None:
    """The line naming dependencies pulled in on the caller's behalf."""
    if not res.added:
        return None
    n = len(res.added)
    return ("pulling in %d %s required by your selection: %s"
            % (n, "dependency" if n == 1 else "dependencies",
               ", ".join(res.added)))


def dependency_warnings(res: resolve.Resolution) -> list[str]:
    """Warnings for requirements left out of the plan, then declared clashes."""
    lines: list[str] = []
    for name in res.unresolved:
        # "in no tap" is only true when the catalog has no row for it.
        # `expand_dependencies` also lands here when `resolve_one` refuses a
        # name *several* taps carry, and calling that absent contradicted the
        # prerequisite line printed a few lines below, which names a tap and
        # gives a command that works. 77% of the ambiguous values in the
        # census resolve this way, so the contradiction was the common case,
        # not the corner.
        cands = catalog.distinct_candidates(catalog.find(name))
        if not cands:
            lines.append("required skill %r is in no tap — skipped (install it "
                         "manually or `boost tap` its source)" % name)
            continue
        taps = sorted({str(e.get("tap") or "") for e in cands})
        # Only offer `tap:name` when that would actually disambiguate: one tap
        # vendoring the same name twice is ambiguous too, and there `tap:name`
        # is as unresolvable as the bare name.
        fix = ("name one of %s" % ", ".join("%s:%s" % (t, name) for t in taps)
               if len(taps) == len(cands)
               else "`boost search %s` and install the one you want" % name)
        lines.append("required skill %r matches %d catalog entries — skipped "
                     "(%s)" % (name, len(cands), fix))
    lines.extend("%s declares a conflict with %s (also present)" % pair
                 for pair in res.conflicts)
    return lines


def prerequisite_lines(entries: list[dict], *, pbase=None,
                       would: bool = False) -> tuple[list[str], str | None]:
    """``(warnings, hint)`` for the prerequisites an install declares.

    Advisory and after the fact: the ``requires:`` closure is installed for
    you, and everything the wider spellings declare — ``skills:``,
    ``dependencies:``, ``prerequisites:``, … — is reported instead. See
    :mod:`boost_cli.core.prereq` for why reporting rather than installing is
    the answer.

    ``pbase`` is the project base for a ``--local`` install, so a sibling
    installed into *this repo* counts as present.
    """
    try:
        rows = prereq.for_entries(entries, pbase=pbase)
    except BoostError:
        # A missing or unreadable catalog must not fail an install that has
        # already happened; the prerequisite line is advice, not a step.
        return [], None
    if not rows:
        return [], None
    warnings = ["%s declares %s boost cannot see installed: %s"
                % (row.name, _plural(len(row.unmet), "prerequisite"),
                   ", ".join("%s (%s)" % (m.name, m.tap) for m in row.unmet))
                for row in rows]
    hint = (("would meet them with: %s" if would else "meet them with: %s")
            % prereq.install_hint(rows))
    return warnings, hint
