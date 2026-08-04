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


def match(line: str) -> Match | None:
    """Return the ``RULE_RE`` match for ``line`` (modal + rest), or ``None``."""
    return RULE_RE.match(line)


def norm_rule(text: str) -> str:
    """Strip Markdown emphasis and a trailing period; lowercase the first char.

    So ``**Always** run tests.`` and ``Always run tests`` normalize to the same
    ``always run tests`` — a stable, comparable rule string.
    """
    t = re.sub(r"[*_`]", "", text).strip().rstrip(".")
    return (t[:1].lower() + t[1:]) if t else t


def imperative_rules(body: str) -> list[str]:
    """Cleaned, de-duplicated imperative rules from a skill ``body``.

    A line that reads as a rule is normalized; a numbered step (``1. …``) with
    at least two words becomes ``follow: …``. Order is preserved and exact
    duplicates are dropped.
    """
    rules: list[str] = []
    for raw in body.splitlines():
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
