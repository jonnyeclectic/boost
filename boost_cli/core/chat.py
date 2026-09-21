# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Conversational search over the tapped catalogue.

``boost chat`` sits on top of machinery that already exists — ``rag.retrieve_any``
for finding candidates, ``ai.ask`` for prose, ``faithfulness.score`` for checking
that prose against its source — and adds the one thing they do not do together:
turn a question into an answer that names specific skills and says why.

THE FAILURE THIS IS BUILT AROUND. boost is a package manager. A chatbot that
invents a plausible-sounding skill name is not a cosmetic bug: the user goes
looking for ``docker-compose-expert``, does not find it, and either concludes the
catalogue is broken or — worse — installs something adjacent from an untrusted
tap. Typosquatting is a real hazard in this ecosystem (``core/typosquat.py``
exists for it), so an assistant that manufactures names is actively dangerous
rather than merely unhelpful.

Two defences, in order:

* **Retrieval decides what may be discussed.** The model is never asked "what
  skill does X?" — it is asked to summarise a specific, retrieved set. Nothing
  outside that set can be recommended because nothing outside it is in the
  prompt.
* **The reply is checked before it is shown.** Every skill name in the answer
  must appear in the retrieved set (:func:`ungrounded_names`), and the prose as a
  whole must score against the source text (:func:`faithfulness.score`, the same
  gate ``boost explain`` uses). A reply that fails either is discarded, not
  patched — and the extractive answer below is shown instead.

Degrading rather than failing is the house contract: with ``BOOST_NO_AI=1``, no
API key, or no ``claude`` CLI, :func:`answer` still returns a useful grounded
answer assembled from the retrieved descriptions. The AI path improves the prose;
it is never load-bearing for correctness.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from typing import NamedTuple

from . import ai, catalog, faithfulness, rag

# How many candidates reach the prompt. Small on purpose: the model summarises
# rather than searches, and a long tail of weak hits invites it to reach for
# whichever one sounds closest to the question rather than the one that ranked.
TOP_K = 5

# Minimum groundedness for AI prose, matching `boost explain`'s default. Below
# this the reply names specifics its sources never did, which is the observable
# shape of a fabricated capability.
MIN_FAITHFULNESS = 0.60

# A conversation is kept this short deliberately. `chat` is a lookup assistant,
# not an agent: more history means more chances for the model to answer from the
# conversation instead of from what retrieval actually returned.
HISTORY_TURNS = 4

# A catalogue-name shape: lowercase, hyphenated, e.g. `code-reviewer`.
_NAME = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)+"
_TOKEN = re.compile(r"\b%s\b" % _NAME)

# Emphasis around a name-shaped token: `x`, **x**, *x*.
_EMPHASISED = re.compile(r"`(%(n)s)`|\*\*(%(n)s)\*\*|\*(%(n)s)\*" % {"n": _NAME}, re.IGNORECASE)

# Verbs that introduce a recommendation. What follows one is a claim about what
# to install, which is the phrasing a reader acts on.
_RECOMMENDS = re.compile(
    r"\b(?:use|using|install|try|run|pick|choose|recommends?)\b", re.IGNORECASE)

_SYSTEM = (
    "You help a developer pick an AI coding-agent skill from a catalogue. "
    "Answer ONLY from the numbered skills provided. Never invent a skill name. "
    "If none fit, say so plainly. Be concrete and brief: 3-5 sentences, no "
    "markdown, no bullet lists. Name the skills you recommend exactly as given."
)


class Turn(NamedTuple):
    """One exchange, kept so a follow-up can refer back to it.

    ``skills`` is what the answer drew on, in the order it was shown. A
    follow-up like "which of these should I install first?" points at exactly
    that list, and the list cannot be rebuilt from the question — re-querying
    the catalogue with it retrieved skills the user had never been shown.
    """

    question: str
    answer: str
    skills: Sequence[dict] = ()


class Reply(NamedTuple):
    """What :func:`answer` produces.

    ``grounded`` is False only when the AI path was tried and rejected — the
    caller may want to say so, since a silently downgraded answer looks the same
    as a confident one.

    ``ai_failed`` is True only when :func:`ai.available` said yes but
    :func:`ai.ask` came back with nothing — a backend that ran and failed,
    not one that was never tried. Kept separate from ``grounded``: an
    invented name or an unfaithful reply is a *rejection*, with its own
    warning already shown by the caller, while this is a call that produced
    no reply to reject in the first place and would otherwise fail silently.
    """

    text: str
    skills: list[dict]      # the catalogue entries the answer draws on
    engine: str             # which retrieval engine ran, for attribution
    source: str             # "ai" | "extractive"
    grounded: bool
    ai_failed: bool = False


def _history_context(history: Sequence[Turn]) -> str:
    """Recent turns, oldest first, as plain text for the prompt."""
    recent = list(history)[-HISTORY_TURNS:]
    if not recent:
        return ""
    lines = ["Earlier in this conversation:"]
    for turn in recent:
        lines.extend(("Q: %s" % turn.question, "A: %s" % turn.answer))
    return "\n".join(lines) + "\n\n"


def expand_query(question: str, history: Sequence[Turn]) -> str:
    """The string actually sent to retrieval.

    A follow-up like "what about the second one?" carries almost no searchable
    terms, so retrieving on it alone returns noise. Appending the previous
    question restores the subject without needing the model to rewrite it — a
    rewrite would be another place for the assistant to drift off-topic.

    Only the immediately preceding question is used: two turns back is usually a
    different subject, and blending them retrieves for neither.
    """
    question = question.strip()
    if not history:
        return question
    # Long questions carry their own context; short ones are the follow-ups.
    # This is also the fresh search a pointer ("which of these…") runs
    # alongside the rows it points at, so it must stay the query main sends:
    # that is what keeps a misread pointer from losing main's answer.
    if len(question.split()) > 6:
        return question
    return "%s %s" % (history[-1].question, question)


# Phrases that point back at the list the previous answer showed. Kept narrow,
# though a false match now costs order rather than the answer (see
# :func:`retrieve`): "those flaky tests" is a new subject, "those skills" is a
# reference; "which one is best for linting?" asks the catalogue, "which one of
# these" asks the list; "the other SKILL.md field" is a new subject, "from the
# others" is not; "this one-liner" and "best of both worlds" are English.
_REFERS = re.compile(
    r"\b(?:(?:of|between|among|from|compare)\s+(?:these|those|them)"
    r"|(?:of|between|among|from|than|to|about|vs\.?|versus|compared?)\s+the\s+others"
    r"|(?:these|those)\s+(?:ones?|skills?|options?|results?|matches)"
    r"|(?:that|this)\s+one\b(?!-))\b", re.IGNORECASE)

# "the second one", "the 2nd skill?" — one row of the previous list. The
# ordinal needs a pointer in front ("the", "that", "this", or nothing but the
# ordinal in the whole question): "my first skill" is a new subject. With a
# noun rather than "one" it must also end the clause, because "the last skill I
# should install for linting" is a new question that happens to say "the last",
# and "one" must not start a compound: "the first one-shot prompt".
_ORDINAL = re.compile(
    r"(?:\b(?:the|that|this)\s+|^\W*(?:and\s+)?)"
    r"(?P<word>first|second|third|fourth|fifth|last|1st|2nd|3rd|4th|5th)\s+"
    r"(?:one\b(?!-)|(?:skill|option|result|match)\b(?=\s*(?:[?.!,;]|$)))",
    re.IGNORECASE)

# "#3", "number 2" — only where a row number can stand: the whole question, a
# question that opens "and #3" / "is number 1", or after a verb or preposition
# that takes one ("about #3", "try #2"). "is", "and" and "or" count only at the
# start: mid-question they join numbers that count something else ("which
# skill is #1 for security?", "PRs #2 and #3").
_ROW_NUMBER = re.compile(
    r"(?:^\W*(?:(?:and|or|is)\s+)?|\b(?:about|try|install|use|pick|choose|vs|than|with)\s+)"
    r"(?:#\s*|number\s+)(?P<n>\d+)\b", re.IGNORECASE)
# A number after one of these numbers that thing, and so does every number in
# a question that has one: "compare PR #2 with #3" is two pull requests.
_TRACKED = re.compile(
    r"\b(?:prs?|pull\s+requests?|issues?|bugs?|tickets?)\s*(?:#\s*|number\s+)?\d",
    re.IGNORECASE)
_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
             "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5}


def _row_number(question: str) -> int | None:
    """The row a "#N" / "number N" in ``question`` names, if it names one."""
    if _TRACKED.search(question):
        return None
    m = _ROW_NUMBER.search(question)
    return int(m.group("n")) if m else None


def is_referential(question: str) -> bool:
    """Whether ``question`` points back at the previous answer's list."""
    return bool(_REFERS.search(question) or _ORDINAL.search(question)
                or _row_number(question) is not None)


def referenced(question: str, previous: Sequence[dict]) -> list[dict] | None:
    """The previous answer's rows if ``question`` points at them, else None.

    An ordinal or a row number moves its row to the front, numbered as the
    answer numbered it, and keeps the others after it: the pointer might be a
    misreading, and the rest of the list costs nothing to keep. A word ordinal
    past the end still points at the list. A number past the end does not:
    "what about #42?" is not a row of five, and gets an ordinary search.
    """
    if not previous or not is_referential(question):
        return None
    word = _ORDINAL.search(question)
    number = _row_number(question)
    if word:
        w = word.group("word").lower()
        n = len(previous) if w == "last" else _ORDINALS[w]
    elif number is not None:
        n = number
    else:
        return list(previous)
    if 1 <= n <= len(previous):
        return [previous[n - 1], *previous[:n - 1], *previous[n:]]
    # Past the end, a word ordinal still points at the list; a number numbers
    # something else unless the question also points back.
    if word or _REFERS.search(question):
        return list(previous)
    return None


def _name(entry: dict) -> str:
    return str(entry.get("name", "")).lower()


def _row(entry: dict) -> tuple:
    """Row identity (``rag.entry_key``'s fields), tolerant of synthesised rows.

    Equality rather than ``is``: the previous turn's rows and this turn's hits
    can be equal dicts from two catalogue loads, and must not be listed twice.
    """
    return (entry.get("tap"), entry.get("skill_md"), entry.get("name"))


def promote_named(question: str, ranked: Sequence[dict],
                  previous: Sequence[dict] = (),
                  catalogue: Sequence[dict] = ()) -> list[dict]:
    """``ranked`` with any skill the question names moved to the front.

    Asking "what does orch-review actually do?" is a lookup, and a ranker can
    score a sibling that repeats the query terms above the skill it names — the
    audit saw ``orch-refine-code`` outrank ``orch-review`` for exactly that
    question. A name counts when it is catalogue-shaped (hyphenated), or when
    it is any word naming a skill the previous answer showed: "teach" in an
    arbitrary question is English, but not right after the user was shown a
    skill called ``teach``.

    For each name the row the user was just shown wins, then the best-ranked
    hit, then the catalogue — so a name several taps carry resolves to the one
    the conversation is about. Namesakes are kept, ranked after.
    """
    shown = {_name(e) for e in previous}
    words = re.findall(r"[a-z0-9][a-z0-9-]*[a-z0-9]|[a-z0-9]", question.lower())
    # dict.fromkeys: each name once, in the order the question gives them.
    names = dict.fromkeys(w for w in words if _TOKEN.fullmatch(w) or w in shown)
    pools = (previous, ranked, catalogue)
    found = (next((e for pool in pools for e in pool if _name(e) == n), None)
             for n in names)
    front = [e for e in found if e is not None]
    placed = {_row(e) for e in front}
    return front + [e for e in ranked if _row(e) not in placed]


def _search(query: str, k: int, entries: list[dict]) -> tuple[list[dict], str]:
    """The top ``k`` for ``query`` from whichever engine the machine has."""
    hits, engine = rag.retrieve_any(query, k=k, entries=entries)
    if hits is None:
        # No index of any kind: catalog.search is the documented floor.
        return [e for e, _score in catalog.search(query)[:k]], "frontmatter scan"
    return [h["entry"] for h in hits[:k]], engine


def retrieve(question: str, history: Sequence[Turn] = (),
             k: int = TOP_K) -> tuple[list[dict], str]:
    """Candidate catalogue entries for ``question``, best first.

    Returns ``(entries, engine_label)``. Uses :func:`rag.retrieve_any` so chat
    gets whatever the machine has — hybrid, dense, or BM25 — rather than pinning
    an engine of its own, and falls back to the frontmatter scan when no index
    exists at all so a fresh install still answers.

    A follow-up that points back at the previous answer ("which of these…",
    "the second one") leads with that answer's rows, the row it names first:
    the audit measured "which of these should I install first?" coming back
    with nothing from the turn before. It never *replaces* the search, though.
    The same search runs, and its results follow the carried rows, so a
    question misread as a pointer ("this one-liner", "PRs #2 and #3") loses
    order, not the answer. That makes such a turn longer than ``k``: ``k``
    carried rows (plus any the question names that fell past ``k``), then a
    skill named but never shown, then the search's ``k``.

    A skill the question names is ranked first on an ordinary search, and may
    come from the catalogue: "is pre-commit better than those skills?" names a
    skill the list never showed, and an answer about it is only grounded if
    it is among the sources. On a pointer it goes after the carried rows,
    which are what the question is about.
    """
    previous = list(history[-1].skills) if history else []
    entries = catalog.all_entries()
    found, engine = _search(expand_query(question, history), k, entries)
    carried = referenced(question, previous)
    if carried is None:
        return promote_named(question, found, previous, entries)[:k], engine
    head = carried[:k]
    # Search hits before the rest of the catalogue, so a name several taps
    # carry resolves to the copy the search ranked.
    lead = promote_named(question, head, previous, [*found, *entries])
    shown = {_row(e) for e in previous}
    placed = {_row(e) for e in lead}
    return ([e for e in lead if _row(e) in shown]
            + [e for e in lead if _row(e) not in shown]
            + [e for e in found if _row(e) not in placed],
            "previous answer + %s" % engine)


# Catalogue descriptions are untrusted upstream text and some are enormous:
# measured over a real 71,655-entry catalogue, 22.7% exceed 300 characters and
# the longest is 5,771. One entry rendered as a screenful of embedded
# `<example>` blocks — a correct answer nobody could read.
DESC_CHARS = 200


def _one_line(text: str) -> str:
    """Collapse a description to a single line of plain text.

    Handles real newlines *and* the literal two-character ``\\n`` that 635
    entries carry from double-escaped upstream frontmatter — those reach a
    terminal as visible backslash-n noise rather than as line breaks.
    """
    return " ".join(text.replace("\\n", " ").replace("\\t", " ").split())


def _describe(entry: dict, ref: str | None = None) -> str:
    """One catalogue entry as a line of prompt/answer text.

    Truncation is marked with an ellipsis rather than silent: the reader needs
    to know there is more to the description before deciding, and `boost info
    <name>` is where the full text lives.

    ``ref`` replaces the bare name with something that resolves — see
    :func:`citations`. It is passed on the *answer* path and deliberately NOT
    on the prompt path: the system prompt tells the model to name skills
    "exactly as given", and :func:`ungrounded_names` grades its reply against
    the entries' bare names, so handing it qualified names would make a
    correctly-quoted recommendation look invented and throw the answer away.
    """
    desc = _one_line(entry.get("description") or "")
    if len(desc) > DESC_CHARS:
        # Cut on a word boundary so the tail is not a severed token.
        desc = desc[:DESC_CHARS].rsplit(" ", 1)[0] + " …"
    name = str(entry.get("name", "?"))
    # A qualified ref already names the tap, so repeating it is noise.
    head = ref if ref and ref != name else "%s (%s)" % (name, entry.get("tap", "?"))
    return "%s — %s" % (head, desc or "no description")


def source_text(entries: Sequence[dict]) -> str:
    """The numbered candidate list the model is allowed to answer from."""
    return "\n".join("%d. %s" % (i, _describe(e)) for i, e in enumerate(entries, 1))


def grounding_text(entries: Sequence[dict]) -> str:
    """The text a reply is checked against — untruncated, unlike the prompt.

    These must be different strings. The prompt is trimmed to keep an answer
    readable, but checking a reply against the *trimmed* text would score a
    faithful sentence as unfaithful purely because its evidence fell past
    :data:`DESC_CHARS` — the truncation would manufacture the very failure the
    check exists to detect.
    """
    return "\n".join(
        "%s %s" % (e.get("name", ""), _one_line(e.get("description") or ""))
        for e in entries)


def claimed_names(reply: str) -> set:
    """Name-shaped tokens the reply presents *as skills to install*.

    Not every hyphenated word is a claim. Descriptions in this catalogue are
    thick with ordinary compounds — "read-only", "multi-agent", "single-pass",
    "security-focused" — and treating each as a possible fabricated skill name
    rejected essentially every real answer (reported from live use). The harm
    this guards against is specific: a reader acting on a recommendation and
    hunting for a package that does not exist. So a token counts as claimed when
    it is emphasised, or when it sits in the clause a recommending verb
    introduces — "try code-reviewer or docker-compose-expert" claims both.

    Scanning the whole clause rather than just the next word is what catches the
    second item in a list, which is exactly where an invention tends to hide.
    Prose that merely *describes* ("a read-only multi-agent review") claims
    nothing and is left to :func:`faithfulness.score`, the second gate.
    """
    out = {next(g for g in m.groups() if g).lower()
           for m in _EMPHASISED.finditer(reply)}
    for verb in _RECOMMENDS.finditer(reply):
        # Stop at the sentence end: a later sentence is a new statement, not
        # part of this recommendation.
        clause = re.split(r"[.;!?\n]", reply[verb.end():], maxsplit=1)[0]
        out |= {t.lower() for t in _TOKEN.findall(clause)}
    return out


def ungrounded_names(reply: str, entries: Sequence[dict]) -> list[str]:
    """Skill-shaped tokens in ``reply`` that appear nowhere in ``entries``.

    Catalogue names are lowercase hyphenated words (``code-reviewer``), which is
    a distinctive enough shape to spot in prose. A token of that shape that
    appears in neither the retrieved names nor the retrieved *text* is one the
    model supplied itself — the failure that sends a user hunting for a skill
    which does not exist, or toward a typosquat (see ``core/typosquat.py``).

    THE SOURCES GROUND THE REPLY, NOT JUST THE NAMES. An earlier version checked
    only against the name list, so ordinary hyphenated English quoted straight
    out of a description — "read-only", "multi-agent", "pre-deployment" — scored
    as fabricated. In this catalogue those compounds are everywhere, so a
    faithful reply was rejected almost every time and the AI path silently
    degraded to extractive for nearly every real query. Reported from live use.

    Deliberately narrow in the other direction too: it only flags *hyphenated*
    tokens, because a single ordinary word cannot be told apart from prose. This
    under-reports rather than firing on innocent sentences, and
    :func:`faithfulness.score` covers the rest.
    """
    # Whole tokens, not a substring scan. `x in "…"` would treat an invented
    # `code-review` as grounded because `code-reviewer` contains it — precisely
    # the near-miss shape a typosquat has.
    grounded = set(_TOKEN.findall(grounding_text(entries).lower()))
    grounded |= {str(e.get("name", "")).lower() for e in entries}
    return sorted(c for c in claimed_names(reply) if c not in grounded)


def _extractive(question: str, entries: Sequence[dict]) -> str:
    """A grounded answer with no model involved.

    This is what every keyless, offline or AI-disabled install gets, so it has to
    be genuinely useful rather than an apology: the top candidates with their
    descriptions and where they came from, which is the information the user
    needs to decide.
    """
    if not entries:
        return ("Nothing in the tapped catalogue matches that. Try `boost tap "
                "--defaults` for more registries, or rephrase with the concrete "
                "terms you would expect in the skill's own description.")
    lines = ["Closest matches in your tapped catalogue:"]
    # Numbered to match what the AI path is shown, so the two answer shapes
    # refer to the same rows the same way; and named by `ref`, because this
    # block's whole closing instruction is to go run a command with one of
    # these names, and a name several taps carry is not one.
    lines.extend("  %d. %s" % (n, _describe(entry, ref=cite["ref"]))
                 for n, (entry, cite)
                 in enumerate(zip(entries, citations(entries), strict=True), 1))
    lines.extend(("", "Run `boost info <name>` for the full skill, or "
                      "`boost install <name>` to add it."))
    return "\n".join(lines)


def answer(question: str, history: Sequence[Turn] = (),
           k: int = TOP_K) -> Reply:
    """Answer ``question`` from the tapped catalogue.

    The AI path is attempted only when :func:`ai.available`; its reply is used
    only when it passes both grounding checks. Otherwise the extractive answer is
    returned, which is the same information in a plainer shape.
    """
    entries, engine = retrieve(question, history, k=k)
    extractive = _extractive(question, entries)
    if not entries or not ai.available():
        return Reply(extractive, entries.copy(), engine, "extractive", True)

    source = source_text(entries)
    prompt = "%s%s\n\nCandidate skills:\n%s\n\nQuestion: %s" % (
        _history_context(history),
        "Answer the question using only the numbered skills below.",
        source, question)
    reply = ai.ask(prompt, system=_SYSTEM)
    if not reply:
        # AI was available and was tried — this is a call that failed, not a
        # call that was never made, so the caller gets to say so rather than
        # showing the extractive answer as if AI had never been in the loop.
        return Reply(extractive, entries.copy(), engine, "extractive", True,
                    ai_failed=True)

    reply = reply.strip()
    invented = ungrounded_names(reply, entries)
    if invented:
        # A manufactured name is unrecoverable — there is no honest way to show
        # prose that points at a skill which does not exist.
        return Reply(extractive, entries.copy(), engine, "extractive", False)
    if faithfulness.score(reply, grounding_text(entries)) < MIN_FAITHFULNESS:
        return Reply(extractive, entries.copy(), engine, "extractive", False)
    return Reply(reply, entries.copy(), engine, "ai", True)


def multi_tap_names(names: set[str]) -> set[str]:
    """Which of ``names`` more than one tap carries.

    This is exactly the condition :func:`catalog.resolve_one` refuses on, so it
    is the condition under which a bare name is not a usable argument. A name
    repeated *inside* one tap is deliberately not included: resolve_one picks a
    canonical row for that case, so qualifying it would add noise without
    fixing anything.

    One pass for the whole citation block rather than a :func:`catalog.find`
    per name — k scans of a catalogue that runs to tens of thousands of rows on
    a real install. Measured, that is a small win rather than a decisive one
    (``load_tap`` is mtime-cached in-process, so a repeat ``all_entries`` is
    0.3 ms over 10,152 entries and this whole function is ~1 ms); the reason to
    prefer it is that "which names are ambiguous" is one question about the
    catalogue, not k independent ones.
    """
    if not names:
        return set()
    seen: dict[str, set[str]] = {}
    for e in catalog.all_entries():
        name = str(e.get("name", ""))
        if name in names:
            seen.setdefault(name, set()).add(str(e.get("tap", "")))
    return {name for name, taps in seen.items() if len(taps) > 1}


def citations(entries: Sequence[dict]) -> list[dict[str, str]]:
    """Name/tap pairs for the entries an answer drew on, each with a usable ref.

    Shown under every answer so a claim can be checked against the source, which
    matters more here than in an ordinary chatbot: the next step is installing
    code that will run inside the user's agent.

    ``ref`` is the invariant worth keeping: **whatever is in it can be pasted
    into `boost info` or `boost install` and will resolve.** For most skills
    that is just the name. For a name several taps carry it cannot be — the
    answer would be recommending something whose follow-up command errors with
    an ambiguity — so ``ref`` carries the ``owner/repo:name`` form instead.
    That form is only worth emitting because ``info`` now accepts it; before
    that it would have traded one dead end for another.
    """
    ambiguous = multi_tap_names({str(e.get("name", "")) for e in entries})
    out = []
    for e in entries:
        name = str(e.get("name", ""))
        tap = str(e.get("tap", ""))
        out.append({
            "name": name,
            "tap": tap,
            "kind": str(e.get("kind", "skill")),
            "ref": "%s:%s" % (tap, name) if name in ambiguous and tap else name,
        })
    return out


def suggest_followups(entries: Sequence[dict], with_ai: bool = True) -> list[str]:
    """Concrete next questions, drawn from what was actually retrieved.

    Generic prompts ("ask me anything!") teach nothing; naming a real retrieved
    skill shows the user the shape of a question that works.

    ``with_ai=False`` offers only what the extractive answer can answer: a
    lookup of one named skill, which :func:`promote_named` puts first. A
    comparison or a "which first" needs prose that path does not write, so
    suggesting one invites a question whose answer is the same list again.
    """
    if not entries:
        return ["what skills do I have installed?"] if with_ai else []
    top: dict | None = entries[0]
    name = str(top.get("name", "")) if top else ""
    out: list[str] = []
    if name:
        out.append("what does %s actually do?" % name)
    if with_ai:
        if name:
            out.append("how is %s different from the others?" % name)
        out.append("which of these should I install first?")
    return out
