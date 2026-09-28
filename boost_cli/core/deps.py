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

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass


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

    Values that cannot be an item name are dropped by
    :func:`classify_token`. That is a fix rather than tidying: of the 101
    ``requires:`` values in the tapped corpus, 37 are prose ("GitHub CLI (gh)
    installed and authenticated") and several more are package coordinates
    (``dspy>=0.34.0``, ``python3``) — and every one was rendered by ``boost
    deps`` as a skill that is "✗ not installed" and warned about by ``boost
    install`` as "in no tap". Both were naming a missing skill that was never
    a skill.

    Tokens come back **as written** (:func:`item_tokens`, not
    :func:`item_names`) because this feeds a resolver: a qualified
    ``acme/skills:brainstorming`` has to stay qualified all the way to
    ``catalog.find``.
    """
    return item_tokens(as_list((meta or {}).get("requires")))


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


# ── prerequisite declarations ────────────────────────────────────────────
#
# `requires:` is the spelling boost has always read, and a census of the 461
# tapped registries on a real machine (62,310 entries) says it is the
# *narrowest* real one: 101 declared values across 6 taps. The two that carry
# almost all of the signal were invisible — `skills:` (1,323 values, 18 taps)
# and `dependencies:` (1,065 values, 17 taps). So the key set is widened here
# rather than in a caller, and the two keys that merely *look* like
# declarations are excluded by name:
#
#   `required:`       130 entries, and not a dependency list at all — it is an
#                     argument-schema field, valued `true`/`false` or naming
#                     parameters (`["task_type", "requirements"]`, `["type:
#                     file"]`). Reading it would invent 130 prerequisites.
#   `tools_required:` names Claude *tool permissions* (`Bash`, `Read`,
#                     `mcp__github__*`), which are not installable items.
#   `requires_tools:` names PATH binaries (`kubectl`, `terraform`).
#   `requires-extras:` names Python extras (`dspy[optuna]`, `faiss-cpu`).
#
# `requirements:` and `dependency:` are listed for the same reason even though
# every occurrence measured empty: a key that is skipped on purpose should say
# so, so the next census does not have to re-derive it.
PREREQUISITE_KEYS = ("requires", "dependencies", "depends-on", "depends_on",
                     "prerequisites", "uses", "skills", "needs")

NON_PREREQUISITE_KEYS = ("required", "tools_required", "requires_tools",
                         "requires-extras", "requirements", "dependency")

# A declared value is not automatically a name. Over the same corpus the 2,658
# values under those keys split four ways, and only the first is addressable:
# 1,944 resolve to a catalogued item, 193 are package specs (`torch>=2.0.0`,
# `dspy[mcp]`, `actions/upload-artifact@v7.0.1`), 62 are prose sentences
# ("GitHub CLI (gh) installed and authenticated") and 42 are file paths
# (`01-base-agentic.rules.md`). Classification is therefore per *value*, never
# per key: `dependencies:` is packages in `Galaxy-Dawn/claude-scholar` and
# sibling skills in `athola/claude-night-market`.
ITEM = "item"
PACKAGE = "package"
PROSE = "prose"
FILE = "file"

_FILE_SUFFIXES = (".md", ".mdc", ".py", ".sh", ".json", ".yml", ".yaml", ".txt")
# A version constraint, an extras bracket or an `@ref` — every shape that
# makes a token a package coordinate rather than an item name.
_PACKAGE = re.compile(r"(>=|<=|==|~=|!=|@|\[)|(?<=[A-Za-z0-9])\s*[<>]\s*\d")
# Namespaced forms are real and common: `imbue:proof-of-work`,
# `superpowers:writing-skills`, `marketing-skill/skills/aeo`. 380 of the 1,944
# resolvable values arrive this way, and in every measured case the item lives
# in the *declaring* tap — which is also what keeps a GitHub-Actions `uses:`
# such as `actions/checkout` from resolving against an unrelated registry.
_NAMESPACE = re.compile(r"[:/]")
_MAX_NAME_WORDS = 4


def item_names(tokens: Sequence[str]) -> list[str]:
    """The bare item names among ``tokens``, in order, keeping duplicates.

    A namespaced token is reduced to its tail, which is what the *report*
    path wants: :func:`declared_prerequisites` pairs that tail with
    ``same_tap_only`` and resolves it inside the declaring tap. See
    :func:`item_tokens` for the caller that must not do that.
    """
    names = []
    for token in tokens:
        kind, name = classify_token(token)
        if kind == ITEM:
            names.append(name)
    return names


def item_tokens(tokens: Sequence[str]) -> list[str]:
    """The item-naming tokens among ``tokens``, **exactly as written**.

    The same filter as :func:`item_names` without the namespace split, for
    the one caller that feeds a resolver rather than a message.
    ``owner/repo:x`` is boost's own qualified form and
    ``pkg._expand_dependencies`` hands it straight to ``catalog.find``:
    reducing it to ``x`` there would turn an unambiguous spec into a bare
    name two taps can carry, which boost refuses rather than guesses.
    Dropping the qualifier is only safe once something else supplies the tap.
    """
    return [t for t in tokens if classify_token(t)[0] == ITEM]


@dataclass(frozen=True)
class Prerequisite:
    """One declared value that names an installable item.

    ``key`` is the frontmatter key it came from (so a message can say which
    spelling it read), ``token`` the value as written, ``name`` the bare name
    to look up, and ``same_tap_only`` marks a namespaced token, which may only
    resolve inside the tap that declared it.
    """

    key: str
    token: str
    name: str
    same_tap_only: bool


def classify_token(token: str) -> tuple[str, str]:
    """Classify one declared value as ``(class, bare_name)``.

    ``bare_name`` is meaningful only for :data:`ITEM`; the other classes
    return the token unchanged so a caller can report what it skipped. Order
    matters: `dspy[mcp]` is a package before it is a short name, and
    `01-base-agentic.rules.md` is a file before it is either.

    A URL is checked before anything else because it defeats every later
    rule at once: `https://docs.example.com/hooks` has no file suffix, no
    package marker and one word, so the namespace split would hand back
    `hooks` — a plausible skill name in almost any registry.
    """
    tok = token.strip()
    if not tok:
        return PROSE, tok
    if "://" in tok:
        return PROSE, tok
    if tok.lower().endswith(_FILE_SUFFIXES):
        return FILE, tok
    if _PACKAGE.search(tok):
        return PACKAGE, tok
    if len(tok.split()) > _MAX_NAME_WORDS or tok.endswith(".") or "(" in tok:
        return PROSE, tok
    if _NAMESPACE.search(tok):
        tail = _NAMESPACE.split(tok)[-1].strip()
        return (ITEM, tail) if tail else (PROSE, tok)
    return ITEM, tok


def declared_prerequisites(meta: dict | None,
                           own_name: str | None = None) -> list[Prerequisite]:
    """Every value under :data:`PREREQUISITE_KEYS` that names an item.

    Package specs, prose and file paths are dropped, as is a self-reference —
    31 entries in the corpus list their own name, and "install x before x" is
    never a useful line. De-duplicated on the resolved name, first key wins,
    so a skill declaring the same sibling under both `requires:` and `skills:`
    is one prerequisite rather than two.
    """
    found: list[Prerequisite] = []
    seen: set[str] = set()
    for key in PREREQUISITE_KEYS:
        for token in as_list((meta or {}).get(key)):
            kind, name = classify_token(token)
            if kind != ITEM or name == own_name or name in seen:
                continue
            seen.add(name)
            found.append(Prerequisite(key, token, name,
                                      bool(_NAMESPACE.search(token))))
    return found


@dataclass(frozen=True)
class Unmet:
    """A prerequisite that resolves to a real catalogued item nobody installed.

    ``spec`` is what to hand `boost install`: qualified as ``tap:name`` when
    the name exists in more than one tap, because boost refuses an unqualified
    name in that case — 422 of the resolvable values are ambiguous that way,
    so an unqualified hint would be a command that does not run.
    """

    name: str
    tap: str
    spec: str
    key: str


def unmet_prerequisites(prereqs: Sequence[Prerequisite], *, tap: str,
                        installed, taps_for: Callable[[str], Sequence[str]],
                        ) -> list[Unmet]:
    """Which declared prerequisites name a catalogued item that is not installed.

    ``taps_for(name)`` returns **one tap per candidate boost would still have
    to choose between** — so a name a single registry ships twice under
    different content appears twice, because that is what
    ``catalog.resolve_one`` refuses. Resolution is **same tap first** —
    measured against the 422 ambiguous values, the declaring tap also carries
    the name in 326 of them (77%) — then a unique other tap.

    Anything else is dropped *silently*, and that is the load-bearing
    decision: 413 of the declared values are bare tokens matching nothing in
    any tap (`chromadb`, `torch`, `litgpt`), so a line reading "required skill
    'chromadb' is in no tap" would be wrong far more often than saying
    nothing. Silence is the floor this has to beat — and it is why a row only
    survives when the ``spec`` it carries is a command that runs. Two
    differing copies inside the declaring tap make ``boost install <name>``
    exit 1 with "matches 2 different skills", so that row is dropped rather
    than turned into advice the user cannot follow.
    """
    out_rows: list[Unmet] = []
    for pre in prereqs:
        if pre.name in installed:
            continue
        candidates = list(taps_for(pre.name) or ())
        own = [c for c in candidates if c == tap]
        if len(own) == 1:
            source = tap
        elif own or pre.same_tap_only or len(candidates) != 1:
            continue
        else:
            source = candidates[0]
        spec = ("%s:%s" % (source, pre.name) if len(set(candidates)) > 1
                else pre.name)
        out_rows.append(Unmet(pre.name, source, spec, pre.key))
    return out_rows
