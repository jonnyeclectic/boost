# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Shared extractor for imperative ("normative") rules in skill Markdown.

Skill bodies encode rules as *Always / Never / Must (not) / Do not* lines, and
three commands need to find them: ``explain`` (info), ``simulate`` (intelligence)
and ``conflict`` (quality). Each used to carry its own near-identical regex; this
module is the single home for the canonical matcher, so there is one definition
to reason about and mutation-test.

``RULE_RE`` captures the modal (group 1) and the rest of the line (group 2) and
tolerates a leading list marker, which is what the conflict detector needs.
``imperative_rules`` is the higher-level helper the summarizers use: it returns
cleaned, de-duplicated rule strings, treating a numbered step as a ``follow: …``
rule.
"""
from __future__ import annotations

import re
from re import Match

# An "always / never / must (not) / do not / don't" line, optionally preceded by
# a list marker. Group 1 = the modal, group 2 = everything after it.
RULE_RE = re.compile(
    r"(?i)^\s*(?:[-*+>]|\d+[.)])?\s*"
    r"(never|always|must\s+not|must|do\s+not|don'?t)\b(.*)$")

# A bare leading list marker ("- ", "* ", "1. ", "2) "), for callers that strip
# it before matching.
LIST_RE = re.compile(r"^([-*+]|\d+[.)])\s+")

_NUMBERED_RE = re.compile(r"^\d+[.)]\s+")

# A fenced-code delimiter: up to three spaces of indent, then a run of three
# or more backticks or tildes (CommonMark).
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def prose_lines(body: str) -> list[str]:
    """The lines of ``body`` outside fenced code blocks, fences excluded.

    A shell ``# comment`` in a ```` ```bash ```` block is not a heading, and a
    heredoc's ``1. …`` is not a step: read raw, both surfaced in ``explain``'s
    outline and as ``simulate``'s ``follow:`` rules. A block closes on a run
    of its own character at least as long as the one that opened it, with
    nothing after it; an unclosed block runs to the end of ``body``.
    """
    kept: list[str] = []
    fence = ""
    for line in body.splitlines():
        m = _FENCE_RE.match(line)
        if fence:
            if (m and m.group(1)[0] == fence[0]
                    and len(m.group(1)) >= len(fence) and not m.group(2).strip()):
                fence = ""
            continue
        if m:
            fence = m.group(1)
            continue
        kept.append(line)
    return kept


def match(line: str) -> Match | None:
    """Return the ``RULE_RE`` match for ``line`` (modal + rest), or ``None``."""
    return RULE_RE.match(line)


def norm_rule(text: str) -> str:
    """Strip Markdown emphasis and a trailing period; lowercase the leading modal.

    So ``**Always** run tests.`` and ``Always run tests`` normalize to the same
    ``always run tests`` — a stable, comparable rule string. The whole modal
    token is lowercased, not just its first character: skill prose commonly
    shouts a modal in caps (``NEVER mock without understanding dependencies``),
    and lowercasing only the leading ``N`` left the rest — ``nEVER`` — shouting
    back. Text after the modal is untouched, so an embedded acronym there
    (``Always use TDD``) keeps its case.
    """
    t = re.sub(r"[*_`]", "", text).strip().rstrip(".")
    if not t:
        return t
    m = RULE_RE.match(t)
    end = m.end(1) if m else 1
    return t[:end].lower() + t[end:]


def imperative_rules(body: str) -> list[str]:
    """Cleaned, de-duplicated imperative rules from a skill ``body``.

    A line that reads as a rule is normalized; a numbered step (``1. …``) with
    at least two words becomes ``follow: …``. Fenced code is skipped
    (:func:`prose_lines`). Order is preserved and exact duplicates are
    dropped.
    """
    rules: list[str] = []
    for raw in prose_lines(body):
        line = raw.strip()
        stripped = LIST_RE.sub("", line)
        numbered = bool(_NUMBERED_RE.match(line))
        if RULE_RE.match(stripped):
            rule = norm_rule(stripped)
        elif numbered and len(stripped.split()) >= 2:
            rule = "follow: " + norm_rule(stripped)
        else:
            continue
        if rule and rule not in rules:
            rules.append(rule)
    return rules
