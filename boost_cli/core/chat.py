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
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

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


def _describe(entry: dict) -> str:
    """One catalogue entry as a line of prompt/answer text."""
    return "%s (%s) — %s" % (entry.get("name", "?"), entry.get("tap", "?"),
                             (entry.get("description") or "").strip() or "no description")


def source_text(entries: Sequence[dict]) -> str:
    """The numbered candidate list the model is allowed to answer from."""
    return "\n".join("%d. %s" % (i, _describe(e)) for i, e in enumerate(entries, 1))


def ungrounded_names(reply: str, entries: Sequence[dict]) -> List[str]:
    """Skill-shaped tokens in ``reply`` that name nothing in ``entries``.

    Catalogue names are lowercase hyphenated words (``code-reviewer``,
    ``pdf``), which is a distinctive enough shape to spot in prose. Anything
    matching that shape and not present in the candidate set is a name the model
    supplied itself — the exact failure that sends a user hunting for a skill
    that does not exist.

    Deliberately narrow: it only flags *hyphenated* tokens. A single ordinary
    word cannot be told apart from prose, so this under-reports rather than
    firing on innocent sentences, and the faithfulness score covers the rest.
    """
    known = {str(e.get("name", "")).lower() for e in entries}
    candidates = set(re.findall(r"\b[a-z][a-z0-9]*(?:-[a-z0-9]+)+\b", reply.lower()))
    return sorted(c for c in candidates if c not in known)


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
    lines.extend("  " + _describe(entry) for entry in entries)
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
    if faithfulness.score(reply, source) < MIN_FAITHFULNESS:
        return Reply(extractive, entries.copy(), engine, "extractive", False)
    return Reply(reply, entries.copy(), engine, "ai", True)


def citations(entries: Sequence[dict]) -> List[Dict[str, str]]:
    """Name/tap pairs for the entries an answer drew on.

    Shown under every answer so a claim can be checked against the source, which
    matters more here than in an ordinary chatbot: the next step is installing
    code that will run inside the user's agent.
    """
    return [{"name": str(e.get("name", "")), "tap": str(e.get("tap", "")),
             "kind": str(e.get("kind", "skill"))} for e in entries]


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
