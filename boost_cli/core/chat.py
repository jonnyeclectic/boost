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
from typing import Dict, List, NamedTuple, Optional, Sequence, Set, Tuple

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
    """One exchange, kept so a follow-up can refer back to it."""

    question: str
    answer: str


class Reply(NamedTuple):
    """What :func:`answer` produces.

    ``grounded`` is False only when the AI path was tried and rejected — the
    caller may want to say so, since a silently downgraded answer looks the same
    as a confident one.
    """

    text: str
    skills: List[dict]      # the catalogue entries the answer draws on
    engine: str             # which retrieval engine ran, for attribution
    source: str             # "ai" | "extractive"
    grounded: bool


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
    if len(question.split()) > 6:
        return question
    return "%s %s" % (history[-1].question, question)


def retrieve(question: str, history: Sequence[Turn] = (),
             k: int = TOP_K) -> Tuple[List[dict], str]:
    """Candidate catalogue entries for ``question``, best first.

    Returns ``(entries, engine_label)``. Uses :func:`rag.retrieve_any` so chat
    gets whatever the machine has — hybrid, dense, or BM25 — rather than pinning
    an engine of its own, and falls back to the frontmatter scan when no index
    exists at all so a fresh install still answers.
    """
    query = expand_query(question, history)
    entries = catalog.all_entries()
    hits, engine = rag.retrieve_any(query, k=k, entries=entries)
    if hits is None:
        # No index of any kind: catalog.search is the documented floor.
        scored = catalog.search(query)
        return [e for e, _score in scored[:k]], "frontmatter scan"
    return [h["entry"] for h in hits[:k]], engine


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


def _describe(entry: dict, ref: Optional[str] = None) -> str:
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


def ungrounded_names(reply: str, entries: Sequence[dict]) -> List[str]:
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
                 in enumerate(zip(entries, citations(entries)), 1))
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
        return Reply(extractive, entries.copy(), engine, "extractive", True)

    reply = reply.strip()
    invented = ungrounded_names(reply, entries)
    if invented:
        # A manufactured name is unrecoverable — there is no honest way to show
        # prose that points at a skill which does not exist.
        return Reply(extractive, entries.copy(), engine, "extractive", False)
    if faithfulness.score(reply, grounding_text(entries)) < MIN_FAITHFULNESS:
        return Reply(extractive, entries.copy(), engine, "extractive", False)
    return Reply(reply, entries.copy(), engine, "ai", True)


def multi_tap_names(names: Set[str]) -> Set[str]:
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
    seen: Dict[str, Set[str]] = {}
    for e in catalog.all_entries():
        name = str(e.get("name", ""))
        if name in names:
            seen.setdefault(name, set()).add(str(e.get("tap", "")))
    return {name for name, taps in seen.items() if len(taps) > 1}


def citations(entries: Sequence[dict]) -> List[Dict[str, str]]:
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


def suggest_followups(entries: Sequence[dict]) -> List[str]:
    """Concrete next questions, drawn from what was actually retrieved.

    Generic prompts ("ask me anything!") teach nothing; naming a real retrieved
    skill shows the user the shape of a question that works.
    """
    if not entries:
        return ["what skills do I have installed?"]
    top: Optional[dict] = entries[0]
    name = str(top.get("name", "")) if top else ""
    out: List[str] = []
    if name:
        out.extend(("what does %s actually do?" % name,
                    "how is %s different from the others?" % name))
    out.append("which of these should I install first?")
    return out
