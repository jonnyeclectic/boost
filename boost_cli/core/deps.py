# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Requirement & conflict *facts* for ``boost deps``/``boost info`` — what is
declared, and whether it is currently satisfied.

Distinct from :mod:`boost_cli.core.resolve`, which turns ``requires:`` into an
install *order*. This module never decides what to install; it answers "given
what is installed right now, is this skill's declared graph satisfied?" — the
question ``boost deps`` renders and scores an exit code on. Pure and I/O-free,
like :mod:`boost_cli.core.mcpdecl`: callers read frontmatter and pass the
parsed value in, so every branch here is unit- and mutation-testable with no
lock file or filesystem access.

The bug this closes: ``boost deps <name>`` used to test only *that skill's own*
``requires:`` against the installed set, then separately render one level of
*its dependencies'* own unmet requirements underneath — so a transitively unmet
requirement printed a "✗ not installed" line the exit code never counted.
:func:`has_unmet` is the one place that walks the same nesting the renderer
does, so the two can never disagree again.
"""
from __future__ import annotations

from collections.abc import Sequence


def as_list(value) -> list[str]:
    """Normalize a frontmatter value to a list of non-empty names.

    Accepts a YAML list, a comma-separated string, or a blank/``False``
    value ("declares nothing") — the shared contract ``requires:`` and
    ``conflicts:`` both use.
    """
    if value in (None, "", False):
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [s.strip() for s in str(value).split(",") if s.strip()]


def requirement_names(meta: dict | None) -> list[str]:
    """The plain skill/rule/workflow names a ``requires:`` frontmatter value
    lists.

    Deliberately blind to the MCP-server shape a ``requires:`` block can also
    carry (``requires: {mcp: [...]}`` in an author's source) — boost's
    stdlib-only frontmatter parser has no nested-mapping support, so a value
    written that way never survives parsing as a mapping at all: it is
    hoisted, leaving the *parsed* ``requires`` empty and the MCP names on the
    top-level ``mcp`` key instead (see :mod:`boost_cli.core.mcpdecl`'s module
    docstring). That is precisely why a plain ``requires:`` reader must not
    also expect a mapping here — there is never one to find — and why an MCP
    requirement is a separate fact, read from ``mcp`` via
    :mod:`boost_cli.core.mcpdecl`, not from this function.
    """
    return as_list((meta or {}).get("requires"))


def conflict_names(meta: dict | None) -> list[str]:
    """The names a ``conflicts:`` frontmatter value lists."""
    return as_list((meta or {}).get("conflicts"))


def requirement_row(name: str, have: set, sub_names: Sequence[str] = ()) -> dict:
    """One ``{name, installed, requires}`` record.

    The shape both ``boost deps <name>`` (top level and nested, one level
    deep) and ``boost deps`` (all-installed) now emit for a requirement, so a
    ``--json`` consumer reads the same fields regardless of nesting depth —
    the nested form used to be a bare string with no ``installed`` flag,
    which is what let a genuinely unmet transitive requirement render
    invisibly to any JSON consumer. ``requires`` is always present (``[]``
    when ``sub_names`` is empty) rather than omitted, matching the envelope
    shape this command already committed to.
    """
    return {"name": name, "installed": name in have,
            "requires": [requirement_row(n, have) for n in sub_names]}


def conflict_row(name: str, have: set) -> dict:
    """One ``{name, installed}`` conflict record."""
    return {"name": name, "installed": name in have}


def has_unmet(rows) -> bool:
    """True if any requirement row, at any nesting depth, is unmet.

    Walks ``row["requires"]`` the same way the renderer does, so a skill whose
    own direct requirement is installed but whose requirement's requirement
    is not still reports a problem — the exit-code bug this module exists to
    close.
    """
    for row in rows:
        if not row["installed"] or has_unmet(row.get("requires") or []):
            return True
    return False


def active_conflicts(rows) -> bool:
    """True if any conflict row names something actually installed."""
    return any(row["installed"] for row in rows)


def unmet_names(rows) -> list[str]:
    """Every unmet name across requirement rows, flattened and de-duplicated,
    sorted for deterministic output — the ``boost install <name>`` hint reads
    straight off this list.
    """
    names: list[str] = []
    seen: set = set()
    for row in rows:
        if not row["installed"] and row["name"] not in seen:
            seen.add(row["name"])
            names.append(row["name"])
        for sub in row.get("requires") or []:
            if not sub["installed"] and sub["name"] not in seen:
                seen.add(sub["name"])
                names.append(sub["name"])
    return sorted(names)
