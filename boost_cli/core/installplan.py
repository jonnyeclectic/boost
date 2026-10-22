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

from collections.abc import Iterable
from typing import NamedTuple

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


def pick_dependency(token: str, declaring_tap: str | None = None
                    ) -> dict | None:
    """The catalog entry a ``requires:`` token names, or ``None``.

    **Same tap first**, as :func:`deps.unmet_prerequisites` already resolves
    for the prerequisite line: a bare ``newdep`` declared by a skill in
    ``alpha`` is alpha's ``newdep`` when alpha ships exactly one, even if
    ``beta`` ships another. Without that the resolver announced "pulling in
    newdep", skipped it as ambiguous, and the prerequisite line a few lines
    below named ``alpha:newdep`` — the same output disagreeing with itself.
    Two differing copies inside the declaring tap stay unresolved, as they do
    there. Otherwise the token goes to :func:`catalog.resolve_one`, which
    honours a ``tap:`` qualifier and refuses a cross-tap guess.
    """
    if declaring_tap:
        own = catalog.distinct_candidates(
            catalog.find(token, tap=declaring_tap))
        if len(own) == 1:
            return own[0]
        if own:
            return None
    try:
        return catalog.resolve_one(token)
    except BoostError:
        return None


def dependency_label(entry: dict) -> str:
    """How to name ``entry`` in a line the user may copy into `boost install`.

    Bare when the name is unambiguous, ``tap:name`` when several taps ship
    distinct copies — the bare name would be refused there.
    """
    name = str(entry.get("name") or "")
    cands = catalog.distinct_candidates(catalog.find(name))
    if len({e.get("tap") for e in cands}) > 1:
        return "%s:%s" % (entry.get("tap"), name)
    return name


def install_spec(token: str, declaring_tap: str | None = None) -> str:
    """A ``boost install`` argument that installs what ``token`` requires.

    :func:`pick_dependency` then :func:`dependency_label`, falling back to the
    token as written when nothing resolves (the command then fails with the
    resolver's own explanation rather than a different one).
    """
    entry = pick_dependency(token, declaring_tap)
    return dependency_label(entry) if entry is not None else token


def expand_dependencies(entries: list[dict], pbase=None, *,
                        also_installed: Iterable[str] = (),
                        ) -> tuple[list[dict], resolve.Resolution]:
    """Grow the requested entries into their full `requires:` closure.

    Returns ``(ordered_entries, resolution)`` — the entries to install in
    dependency-first order (roots plus any pulled-in dependencies that are not
    already installed), and the :class:`resolve.Resolution` carrying what was
    added, any advisory conflicts, and unresolved (dangling) requirements.
    ``resolution.added`` names only entries in ``ordered_entries``, labelled
    by :func:`dependency_label`, so "pulling in" never names an item the plan
    then skips.

    ``pbase`` is the project a ``--local`` install targets. Its lock counts as
    installed too: without it, ``install --local needy`` re-planned a ``helper``
    already in the repo, the forced-off reinstall refused it, and the command
    exited 1 over a requirement that was met. ``also_installed`` names items
    to treat as present that the lock does not hold yet.
    """
    # All three lock sections, not just skills: a rule or workflow already
    # installed under a required name must not be re-added to the plan. Tap
    # aware, so a met `requires: [alpha:base]` is not re-planned.
    installed = prereq.installed_set(pbase, also=also_installed)
    # One entry per token in the plan — the roots as the caller chose them, a
    # dependency as `pick_dependency` picks it — and every relation is read
    # off that entry, so the item whose `requires:` was walked is the item
    # that gets installed.
    picked: dict[str, dict | None] = {e["name"]: e for e in entries}
    # The tap of the first entry that declared each token: the resolver asks
    # for a parent's requirements before it visits them, so this is set by the
    # time `entry_for` needs it.
    declared_in: dict[str, str] = {}

    def entry_for(name: str) -> dict | None:
        if name not in picked:
            picked[name] = pick_dependency(name, declared_in.get(name))
        return picked[name]

    def relations(name: str, key: str) -> list[str]:
        entry = entry_for(name)
        if entry is None:
            return []
        found = entry_relations(entry, key)
        if key == "requires":
            for dep in found:
                declared_in.setdefault(dep, str(entry.get("tap") or ""))
        return found

    res = resolve.resolve(
        [e["name"] for e in entries],
        lambda n: relations(n, "requires"),
        lambda n: relations(n, "conflicts"),
        installed=installed,
        # Installed counts as known: a met requirement whose tap has since
        # been removed is met, not "in no tap".
        known=lambda n: n in installed or entry_for(n) is not None,
    )
    ordered: list[dict] = []
    seen: set[tuple] = set()
    for name in res.order:
        entry = entry_for(name)
        # `base` (a root) and `alpha:base` (a dependency) are two tokens and
        # one item: install it once.
        if entry is not None and _item_key(entry) not in seen:
            seen.add(_item_key(entry))
            ordered.append(entry)
    roots = {_item_key(e) for e in entries}
    res.added = [dependency_label(e) for e in ordered
                 if _item_key(e) not in roots]
    return ordered, res


def _item_key(entry: dict) -> tuple:
    """Which catalogued file an entry is — two lookups can return two dicts."""
    return (entry.get("tap"), entry.get("name"), entry.get("skill_md"))


def missing_dependencies(entries: list[dict], pbase=None, *,
                         also_installed: Iterable[str] = (),
                         ) -> tuple[list[dict], resolve.Resolution]:
    """Only the dependencies :func:`expand_dependencies` would add.

    For a caller that installs ``entries`` itself (``boost update`` after an
    upgrade, a Boostfile line, the browse TUI) and needs the rest of the
    closure, in install order, without the roots it already handles.
    """
    ordered, res = expand_dependencies(entries, pbase,
                                       also_installed=also_installed)
    roots = {_item_key(e) for e in entries}
    return [e for e in ordered if _item_key(e) not in roots], res


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


class InstallPlan(NamedTuple):
    """What installing ``roots`` means, before anything is written.

    ``entries`` is the dependency-first install order; the rest are the words
    every front end says about it, in the order ``boost install`` says them.
    """
    entries: list[dict]
    confusions: list[str]
    added: str | None
    dep_warnings: list[str]

    def notes(self) -> list[tuple[str, str]]:
        """``(role, text)`` pairs — ``warn`` or ``info`` — in print order, for
        a surface that renders them itself (the browse pane, an MCP reply)."""
        return ([("warn", line) for line in self.confusions]
                + ([("info", self.added)] if self.added else [])
                + [("warn", line) for line in self.dep_warnings])


def plan(roots: list[dict], *, pbase=None, deps: bool = True) -> InstallPlan:
    """The one install plan: look-alike warnings, then the ``requires:``
    closure (unless ``deps`` is off), then what the closure left out.

    ``boost install``, the MCP ``boost_install`` tool and the browse TUI all
    call this. The TUI used to call ``store.install`` on the highlighted row
    alone, so a skill whose `requires:` the CLI pulled in installed without
    its prerequisite, and no look-alike warning was ever shown.
    """
    confusions = confusion_lines(roots)
    if not deps or not roots:
        return InstallPlan(roots.copy(), confusions, None, [])
    entries, res = expand_dependencies(roots, pbase=pbase)
    return InstallPlan(entries, confusions, added_line(res),
                       dependency_warnings(res))


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
