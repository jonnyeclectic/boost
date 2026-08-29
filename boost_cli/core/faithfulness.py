# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""A runtime faithfulness check for AI-generated skill explanations.

``boost explain`` asks the model for a plain-English summary of a ``SKILL.md``.
The offline eval (``scripts/eval_explain.py``, ragas) grades whether such
summaries stay grounded in their source — but only *after the fact*, so a
hallucinated explanation is still shown to the user in the moment.

This is the runtime half: a cheap, deterministic, stdlib grounding check that
runs on every live explanation, no second model call. It does not try to judge
prose quality — only whether the summary invented **specific, checkable things**
the source never mentions. A model paraphrasing freely in general English is
fine; a model that names a command, flag, tool, or file the ``SKILL.md`` does
not contain is the failure mode worth catching, because that is what a
fabricated capability looks like.

So the signal is *salient* tokens — the code-shaped, acronym, and quoted terms a
faithful summary can only have gotten from the source:

  * anything in `backticks`
  * tokens with code punctuation or digits (``--local``, ``skill_md``, ``v1.2``)
  * multi-letter ALL-CAPS acronyms (``SKILL``, ``MCP``)

The score is the fraction of the summary's salient terms that also appear in the
source. General words are ignored on both sides, so ordinary paraphrase never
lowers the score; only an ungrounded specific term does. ``cmd_explain`` uses
the score to fall back to its deterministic extractive summary when a live
explanation looks fabricated.
"""
from __future__ import annotations

import re

# Terms a faithful summary can only have gotten from the source. Ordered as they
# are searched; each capture group is the term itself.
_BACKTICK = re.compile(r"`([^`]+)`")
_CODEISH = re.compile(r"[A-Za-z][\w./-]*(?:[_./-]\w+|\d)[\w./-]*")
_ACRONYM = re.compile(r"\b[A-Z]{2,}\b")
# CLI flags — --project, -v, --dry-run. A leading dash is the whole tell, and
# it is exactly the kind of specific the model likes to invent ("pass --force").
_FLAG = re.compile(r"(?<![\w-])--?[A-Za-z][\w-]*")

# Very common ALL-CAPS words that are not really acronyms — flagging them would
# punish an emphatic but perfectly grounded sentence.
_STOP_ACRONYMS = {"A", "I", "AN", "THE", "AND", "OR", "IF", "IT", "IS", "TO",
                  "OK", "NO", "YES", "ON", "OFF", "AI"}


def salient_terms(s: str) -> set[str]:
    """The set of checkable, source-derived terms in ``s`` (lower-cased).

    Backtick spans are split on whitespace so `boost install x` contributes
    three terms, not one — each is grounded independently.
    """
    out: set[str] = set()
    for m in _BACKTICK.findall(s):
        for tok in m.split():
            tok = tok.strip("`.,:;()[]{}\"'")
            if tok:
                out.add(tok.lower())
    out.update(m.lower() for m in _CODEISH.findall(s))
    out.update(m.lower() for m in _FLAG.findall(s))
    for m in _ACRONYM.findall(s):
        if m not in _STOP_ACRONYMS:
            out.add(m.lower())
    return out


def _source_vocab(source: str) -> set[str]:
    """Every salient term the source contains, plus its plain word vocabulary.

    A summary term counts as grounded if it appears anywhere in the source —
    inside a code span, as a bare word, or as a substring token — so the check
    never rejects a term the author actually wrote, however they formatted it.
    """
    vocab = salient_terms(source)
    vocab.update(w.lower() for w in re.findall(r"[A-Za-z][\w./-]*", source))
    return vocab


def score(summary: str, source: str) -> float:
    """Faithfulness of ``summary`` to ``source`` in ``[0.0, 1.0]``.

    The fraction of the summary's salient terms that are grounded in the source.
    A summary with no salient terms scores ``1.0`` — it asserts nothing specific
    to be wrong about. An empty summary scores ``0.0``: there is nothing to show,
    which should trip the fallback, not pass as faithful.
    """
    if not summary.strip():
        return 0.0
    terms = salient_terms(summary)
    if not terms:
        return 1.0
    vocab = _source_vocab(source)
    grounded = sum(1 for t in terms if _is_grounded(t, vocab))
    return grounded / len(terms)


def _is_grounded(term: str, vocab: set[str]) -> bool:
    """A term is grounded if the source vocab contains it, or a token of it.

    Handles ``boost-install`` vs a source that writes ``boost install``: the
    hyphen/slash/dot-separated pieces are checked too, so a faithful term whose
    punctuation the model normalized differently is not counted as invented.
    """
    if term in vocab:
        return True
    parts = [p for p in re.split(r"[./_-]", term) if len(p) > 1]
    return bool(parts) and all(p in vocab for p in parts)


def ungrounded_terms(summary: str, source: str) -> list[str]:
    """The salient terms in ``summary`` absent from ``source`` — for the caveat."""
    vocab = _source_vocab(source)
    return sorted(t for t in salient_terms(summary) if not _is_grounded(t, vocab))
