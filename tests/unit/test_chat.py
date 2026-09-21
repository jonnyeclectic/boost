# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost chat` — grounded conversational search.

The engine is thin; the interesting part is what it *refuses* to say. boost is a
package manager, so an assistant that invents a plausible skill name sends a user
hunting for something that does not exist — or installing something adjacent from
an untrusted tap. Most of these tests are therefore about rejection paths rather
than happy-path prose.

No network and no model: `ai.available` / `ai.ask` are stubbed throughout, so
these run identically with `BOOST_NO_AI=1`, on a machine with a key, and on CI.
"""
from __future__ import annotations

import re

import pytest

from boost_cli.core import ai, catalog, chat
from boost_cli.errors import BoostError


def _entry(name: str, desc: str = "", tap: str = "acme/skills",
           kind: str = "skill") -> dict:
    return {"name": name, "tap": tap, "kind": kind, "description": desc,
            "skill_md": "%s/SKILL.md" % name}


CANDIDATES: list[dict] = [
    _entry("code-reviewer", "Reviews a diff for bugs and style"),
    _entry("security-auditor", "Finds injection flaws and leaked secrets"),
    _entry("pdf", "Extract text from a scanned document"),
]


@pytest.fixture()
def retrieved(monkeypatch):
    """Pin retrieval so these tests measure the answer, not the ranker."""
    monkeypatch.setattr(chat, "retrieve",
                        lambda q, history=(), k=chat.TOP_K: (CANDIDATES, "test engine"))
    return CANDIDATES


@pytest.fixture()
def no_ai(monkeypatch):
    monkeypatch.setattr(ai, "available", lambda: False)


def _with_ai(monkeypatch, reply):
    monkeypatch.setattr(ai, "available", lambda: True)
    monkeypatch.setattr(ai, "ask", lambda prompt, system=None, **kw: reply)


class TestRefusesInventedNames:
    """The failure that matters: a skill name the catalogue does not contain."""

    def test_an_invented_name_falls_back_to_the_grounded_answer(
            self, sandbox, retrieved, monkeypatch):
        _with_ai(monkeypatch, "You want docker-compose-expert for that.")
        reply = chat.answer("how do I debug containers?")
        assert reply.source == "extractive"
        assert reply.grounded is False, "an invented name must be reported, not hidden"
        assert "docker-compose-expert" not in reply.text

    def test_a_reply_naming_only_real_skills_is_kept(
            self, sandbox, retrieved, monkeypatch):
        _with_ai(monkeypatch,
                 "Use code-reviewer to check the diff for bugs and style, and "
                 "security-auditor to find injection flaws and leaked secrets.")
        reply = chat.answer("review my diff")
        assert reply.source == "ai"
        assert reply.grounded is True

    def test_ungrounded_names_finds_the_invented_one(self):
        found = chat.ungrounded_names(
            "try code-reviewer or docker-compose-expert", CANDIDATES)
        assert found == ["docker-compose-expert"]

    def test_ungrounded_names_ignores_ordinary_prose(self):
        # Under-reporting is deliberate: a single unhyphenated word cannot be
        # told from prose, so only skill-shaped tokens are checked and the
        # faithfulness score covers the rest.
        assert chat.ungrounded_names("this reviews your code for bugs", CANDIDATES) == []

    def test_ungrounded_names_is_case_insensitive(self):
        assert chat.ungrounded_names("Use Code-Reviewer.", CANDIDATES) == []


class TestRefusesUngroundedProse:
    """A reply can name only real skills and still describe them wrongly."""

    def test_a_low_faithfulness_reply_is_rejected(
            self, sandbox, retrieved, monkeypatch):
        _with_ai(monkeypatch,
                 "It provisions Kubernetes clusters and rotates TLS certificates "
                 "across your fleet automatically every night.")
        reply = chat.answer("review my diff")
        assert reply.source == "extractive"
        assert reply.grounded is False

    def test_an_empty_model_reply_degrades_quietly(
            self, sandbox, retrieved, monkeypatch):
        # Nothing was claimed, so nothing was rejected — grounded stays True.
        # But AI *was* tried and produced nothing, which is a distinct cause
        # from "no backend" — ai_failed is how the caller tells them apart.
        _with_ai(monkeypatch, "")
        reply = chat.answer("review my diff")
        assert reply.source == "extractive"
        assert reply.grounded is True
        assert reply.ai_failed is True

    def test_an_invented_name_is_a_rejection_not_a_failure(
            self, sandbox, retrieved, monkeypatch):
        # The model answered — it was rejected, not silent. Conflating the two
        # would print "AI call failed" about a call that plainly succeeded.
        _with_ai(monkeypatch, "You want docker-compose-expert for that.")
        reply = chat.answer("how do I debug containers?")
        assert reply.ai_failed is False

    def test_a_grounded_ai_reply_is_not_marked_failed(
            self, sandbox, retrieved, monkeypatch):
        _with_ai(monkeypatch,
                 "Use code-reviewer to check the diff for bugs and style, and "
                 "security-auditor to find injection flaws and leaked secrets.")
        reply = chat.answer("review my diff")
        assert reply.ai_failed is False


class TestWorksWithoutAI:
    """The keyless/offline path has to be useful, not an apology."""

    def test_it_answers_with_the_retrieved_skills(self, sandbox, retrieved, no_ai):
        reply = chat.answer("review my diff")
        assert reply.source == "extractive"
        assert "code-reviewer" in reply.text
        assert "Reviews a diff for bugs and style" in reply.text

    def test_no_backend_is_not_reported_as_a_failed_call(
            self, sandbox, retrieved, no_ai):
        # AI was never tried here — distinct from ai_failed, which means it
        # was tried and came back empty. Conflating them would tell a keyless
        # user their (nonexistent) AI call failed.
        reply = chat.answer("review my diff")
        assert reply.ai_failed is False

    def test_it_names_the_next_command(self, sandbox, retrieved, no_ai):
        assert "boost install" in chat.answer("review my diff").text

    def test_no_matches_says_what_to_do(self, sandbox, monkeypatch, no_ai):
        monkeypatch.setattr(chat, "retrieve",
                            lambda q, history=(), k=chat.TOP_K: ([], "test engine"))
        reply = chat.answer("something nothing matches")
        assert "boost tap" in reply.text
        assert reply.skills == []

    def test_the_ai_path_is_skipped_entirely_without_ai(
            self, sandbox, retrieved, monkeypatch):
        monkeypatch.setattr(ai, "available", lambda: False)
        called = []
        monkeypatch.setattr(ai, "ask", lambda *a, **kw: called.append(1) or "x")
        chat.answer("review my diff")
        assert called == [], "asked the model despite ai.available() being False"


class TestFollowUps:
    """Short follow-ups have to inherit their subject or retrieval returns noise."""

    def test_a_short_followup_borrows_the_previous_question(self):
        history = [chat.Turn("how do I review a diff for security bugs", "...")]
        expanded = chat.expand_query("what about the second one?", history)
        assert "security" in expanded and "second" in expanded

    def test_a_long_question_stands_on_its_own(self):
        history = [chat.Turn("how do I review a diff", "...")]
        question = "which skill helps me extract text from a scanned pdf document"
        assert chat.expand_query(question, history) == question

    def test_the_first_question_is_unchanged(self):
        assert chat.expand_query("review my diff", []) == "review my diff"

    def test_history_is_bounded(self, sandbox, retrieved, monkeypatch):
        # An unbounded transcript invites answering from the conversation
        # instead of from what retrieval returned.
        seen = {}
        monkeypatch.setattr(ai, "available", lambda: True)
        monkeypatch.setattr(ai, "ask",
                            lambda prompt, system=None, **kw: seen.setdefault("p", prompt) and "")
        history = [chat.Turn("q%d" % i, "a%d" % i) for i in range(12)]
        chat.answer("and now?", history=history)
        assert seen["p"].count("Q: ") <= chat.HISTORY_TURNS


class TestCitations:
    def test_every_answer_can_be_traced(self, sandbox, retrieved, no_ai):
        cites = chat.citations(chat.answer("review my diff").skills)
        assert [c["name"] for c in cites] == [e["name"] for e in CANDIDATES]
        assert all(c["tap"] for c in cites), "a citation without a tap is uncheckable"

    def test_citations_of_nothing_is_empty(self):
        assert chat.citations([]) == []


class TestAmbiguousNamesAreQualified:
    """A recommendation whose follow-up command errors is not a recommendation.

    `boost info code-reviewer` raises when several taps carry the name — and
    `code-reviewer` is 13 distinct skills in the pinned eval corpus alone — so
    handing back the bare name sends the reader into an ambiguity error. The
    qualified form is only worth emitting because `info` accepts it; before
    that it would have traded one dead end for another.
    """

    def test_a_name_in_two_taps_is_reported_as_ambiguous(self, sandbox, monkeypatch):
        monkeypatch.setattr(catalog, "all_entries", lambda: [
            _entry("code-reviewer", tap="a/one"),
            _entry("code-reviewer", tap="b/two"),
            _entry("pdf", tap="a/one")])
        assert chat.multi_tap_names({"code-reviewer", "pdf"}) == {"code-reviewer"}

    def test_a_name_repeated_inside_one_tap_is_not_ambiguous(
            self, sandbox, monkeypatch):
        # catalog.resolve_one picks a canonical row for that case, so there is
        # nothing for a qualifier to disambiguate — it would be pure noise.
        monkeypatch.setattr(catalog, "all_entries", lambda: [
            _entry("code-reviewer", tap="a/one"),
            _entry("code-reviewer", tap="a/one")])
        assert chat.multi_tap_names({"code-reviewer"}) == set()

    def test_no_names_means_no_catalogue_scan(self, monkeypatch):
        monkeypatch.setattr(catalog, "all_entries",
                            lambda: pytest.fail("scanned for an empty set"))
        assert chat.multi_tap_names(set()) == set()

    def test_the_ref_is_qualified_only_where_it_has_to_be(
            self, sandbox, monkeypatch):
        monkeypatch.setattr(catalog, "all_entries", lambda: [
            _entry("code-reviewer", tap="a/one"),
            _entry("code-reviewer", tap="b/two"),
            _entry("pdf", tap="a/one")])
        cites = chat.citations([_entry("code-reviewer", tap="b/two"),
                                _entry("pdf", tap="a/one")])
        assert [c["ref"] for c in cites] == ["b/two:code-reviewer", "pdf"]

    def test_every_ref_actually_resolves(self, sandbox, monkeypatch):
        """The invariant, checked against the real resolver rather than restated.

        This is the test that would have caught the bug: the bare name was
        perfectly well-formed and simply did not resolve.
        """
        entries = [_entry("code-reviewer", tap="a/one"),
                   _entry("code-reviewer", tap="b/two"),
                   _entry("pdf", tap="a/one")]
        monkeypatch.setattr(catalog, "all_entries", lambda: entries)
        for cite in chat.citations(entries):
            resolved = catalog.resolve_one(cite["ref"])   # raises if ambiguous
            assert resolved["name"] == cite["name"]
            assert resolved["tap"] == cite["tap"]

    def test_the_bare_name_would_not_have_resolved(self, sandbox, monkeypatch):
        # Guards the test above from passing vacuously on a corpus where every
        # name happens to be unique.
        entries = [_entry("code-reviewer", tap="a/one"),
                   _entry("code-reviewer", tap="b/two")]
        monkeypatch.setattr(catalog, "all_entries", lambda: entries)
        with pytest.raises(BoostError):
            catalog.resolve_one("code-reviewer")


class TestTheAnswerAndItsSourcesAgree:
    """The model is told to answer from a NUMBERED list. Both halves must number.

    `source_text` hands the model `1. …`, and the system prompt says "answer
    only from the numbered skills", so replies cite `#3`. The rendered source
    block had no numbers at all, which made every such citation unresolvable —
    the two halves disagreed about which contract was in force.
    """

    def test_the_prompt_list_is_numbered_from_one(self):
        text = chat.source_text(CANDIDATES)
        assert text.startswith("1. ")
        assert "\n2. " in text and "\n3. " in text

    def test_the_extractive_answer_uses_the_same_indices(
            self, sandbox, retrieved, no_ai):
        reply = chat.answer("review my diff")
        for n, entry in enumerate(CANDIDATES, 1):
            assert "%d. %s" % (n, entry["name"]) in reply.text

    def test_the_prompt_still_names_skills_bare(self, sandbox, monkeypatch):
        """The qualifier must NOT reach the prompt.

        The system prompt tells the model to name skills "exactly as given" and
        `ungrounded_names` grades the reply against the entries' bare names, so
        a qualified name in the prompt would make a correctly-quoted
        recommendation look invented and throw the answer away.
        """
        monkeypatch.setattr(catalog, "all_entries", lambda: [
            _entry("code-reviewer", tap="a/one"),
            _entry("code-reviewer", tap="b/two")])
        text = chat.source_text([_entry("code-reviewer", tap="b/two")])
        assert "b/two:code-reviewer" not in text
        assert "code-reviewer (b/two)" in text

    def test_a_qualified_ref_does_not_repeat_its_tap(self):
        line = chat._describe(_entry("code-reviewer", "desc", tap="b/two"),
                              ref="b/two:code-reviewer")
        assert line.startswith("b/two:code-reviewer — ")
        assert line.count("b/two") == 1

    def test_an_unqualified_ref_keeps_the_tap_parenthetical(self):
        line = chat._describe(_entry("pdf", "desc", tap="a/one"), ref="pdf")
        assert line.startswith("pdf (a/one) — ")

    def test_followup_suggestions_name_a_real_skill(self, sandbox, retrieved):
        suggestions = chat.suggest_followups(CANDIDATES)
        assert any("code-reviewer" in s for s in suggestions)

    def test_followup_suggestions_survive_no_results(self):
        assert chat.suggest_followups([])


class TestSourceText:
    """What the model is allowed to answer from."""

    def test_candidates_are_numbered_for_reference(self):
        text = chat.source_text(CANDIDATES)
        assert text.startswith("1. code-reviewer")
        assert "3. pdf" in text

    def test_a_missing_description_is_marked_not_blank(self):
        # A blank line reads as "no such skill"; the placeholder keeps the
        # numbering honest and tells the model there is nothing to summarise.
        assert "no description" in chat.source_text([_entry("bare")])


class TestGroundingDoesNotFlagOrdinaryEnglish:
    """A hyphenated word is not a skill name.

    Reported from real use: every AI reply was rejected with "named something
    outside the retrieved skills". The catalogue's own descriptions are full of
    hyphenated compounds — "read-only", "multi-agent", "pre-deployment",
    "risk-adaptive", "test-driven" — and the first version of
    :func:`ungrounded_names` flagged any hyphenated token that was not itself a
    catalogue name. So a reply that faithfully quoted its sources was scored as
    fabricating, and the AI path degraded to extractive for essentially every
    query in this domain.

    The fix is that the *sources* ground the reply, not just the name list:
    a term that appears in the retrieved text came from the retrieved text.
    """

    ENTRIES = ({"name": "code-reviewer", "tap": "t",
                "description": "Parallel read-only multi-agent review of a git diff, "
                               "risk-adaptive and pre-deployment focused."},)

    def test_compounds_quoted_from_the_sources_are_grounded(self):
        reply = ("The read-only multi-agent code-reviewer fits — it is "
                 "risk-adaptive and pre-deployment focused.")
        assert chat.ungrounded_names(reply, self.ENTRIES) == []

    def test_a_genuinely_invented_name_is_still_caught(self):
        # The whole point of the check: boost is a package manager, so a
        # plausible-but-absent name sends the user hunting for a skill that
        # does not exist, or to a typosquat.
        reply = "Use docker-compose-expert for that."
        assert "docker-compose-expert" in chat.ungrounded_names(reply, self.ENTRIES)

    def test_a_near_miss_is_not_grounded_by_a_longer_real_name(self):
        # A substring scan would treat "code-review" as grounded because
        # "code-reviewer" contains it — exactly the near-miss shape a
        # typosquat has, so matching is on whole tokens.
        reply = "Install code-review for that."
        assert "code-review" in chat.ungrounded_names(reply, self.ENTRIES)

    def test_grounding_is_case_insensitive(self):
        reply = "Read-Only review is what Code-Reviewer does."
        assert chat.ungrounded_names(reply, self.ENTRIES) == []

    def test_a_name_never_needs_the_description_to_be_grounded(self):
        entries = [{"name": "tdd-workflow", "tap": "t", "description": ""}]
        assert chat.ungrounded_names("Try tdd-workflow.", entries) == []


class TestLongDescriptionsAreReadable:
    """Catalogue descriptions are untrusted text and some are enormous.

    Measured over a real 71,655-entry catalogue: 22.7% of descriptions exceed
    300 characters, the longest is 5,771, and 635 contain literal ``\\n``
    escape sequences. One such entry rendered as a screenful of embedded
    ``<example>`` blocks, which is what a user actually saw — the answer was
    correct and unreadable.
    """

    def test_a_long_description_is_truncated(self):
        entry = {"name": "x", "tap": "t", "description": "word " * 400}
        line = chat._describe(entry)
        assert len(line) < 300, len(line)

    def test_truncation_is_marked_rather_than_silent(self):
        entry = {"name": "x", "tap": "t", "description": "word " * 400}
        assert chat._describe(entry).rstrip().endswith("…")

    def test_a_short_description_is_left_alone(self):
        entry = {"name": "x", "tap": "t", "description": "Short and useful."}
        assert chat._describe(entry).endswith("Short and useful.")

    def test_embedded_newlines_collapse_to_one_line(self):
        # Both real newlines and the literal two-character \n seen in 635
        # entries, which reach the terminal as visible backslash-n noise.
        entry = {"name": "x", "tap": "t",
                 "description": "first\nsecond\\nthird\r\nfourth"}
        line = chat._describe(entry)
        assert "\n" not in line and "\\n" not in line
        assert "first second third fourth" in line


# The previous turn, as the session stores it: the question, the reply, and the
# skills that reply drew on — which is what a follow-up like "which of these"
# is pointing at.
PREVIOUS_QUESTION = "how do I review a diff?"
SHOWN: list[dict] = [
    _entry("orch-review", "Review a diff for correctness"),
    _entry("code-reviewer", "Reviews a diff for bugs and style"),
    _entry("teach", "Explain a concept step by step"),
]
UNRELATED: list[dict] = [
    _entry("mercury-mcp", "Install the Mercury MCP server"),
    _entry("write-concisely", "Say what the thing actually does"),
]
# In the catalogue, never shown and never returned by the stub ranker.
PRE_COMMIT = _entry("pre-commit", "Set up pre-commit hooks for linting")


def _turn(skills=SHOWN) -> chat.Turn:
    return chat.Turn(PREVIOUS_QUESTION, "…", skills)


@pytest.fixture()
def ranker(monkeypatch):
    """Drive the real :func:`chat.retrieve` over a fixed catalogue.

    Unlike ``retrieved``, this does not replace ``retrieve`` — the referential
    and exact-name logic lives inside it, so a test that stubs it out measures
    nothing. The engine returns ``UNRELATED`` for every query, which is what a
    follow-up with no searchable terms of its own gets from a real ranker, and
    records each query it was asked.
    """
    queries: list[str] = []
    catalogue = [*SHOWN, *UNRELATED, PRE_COMMIT]

    def fake_retrieve_any(query, k=60, entries=None, **kw):
        queries.append(query)
        return [{"entry": e} for e in UNRELATED][:k], "BM25 full-content"

    monkeypatch.setattr(catalog, "all_entries", lambda: catalogue)
    monkeypatch.setattr(chat.rag, "retrieve_any", fake_retrieve_any)
    return queries


def _top_for(query: str) -> dict:
    """The skill a search for ``query`` ranks first — a different one per query."""
    return _entry("top-for-" + "-".join(re.findall(r"[a-z0-9]+", query.lower())))


def _main_query(question: str) -> str:
    """What origin/main searches for ``question`` one turn after ``_turn()``.

    Written out rather than calling ``expand_query``, so the tests below pin
    main's rule instead of following whatever the code under test does: six
    words or fewer inherit the previous question, longer ones are sent alone.
    """
    if len(question.split()) > 6:
        return question
    return "%s %s" % (PREVIOUS_QUESTION, question)


@pytest.fixture()
def searched(monkeypatch):
    """Like ``ranker``, but each query ranks its own skill first.

    That is what lets a test name "the top result main returns" for a
    question: ``_top_for(_main_query(q))``. A search for any other string
    tops out with some other skill.
    """
    queries: list[str] = []

    def fake_retrieve_any(query, k=60, entries=None, **kw):
        queries.append(query)
        ranked = [_top_for(query), *UNRELATED]
        return [{"entry": e} for e in ranked][:k], "BM25 full-content"

    monkeypatch.setattr(catalog, "all_entries",
                        lambda: [*SHOWN, *UNRELATED, PRE_COMMIT])
    monkeypatch.setattr(chat.rag, "retrieve_any", fake_retrieve_any)
    return queries


def _names(entries) -> list[str]:
    return [e["name"] for e in entries]


# New subjects that happen to use a pointer word: every phrasing a review of
# this change has named. A plain search answered each correctly, and each was
# once answered from the previous list instead: an ordinal with no pointer
# ("my first skill") or with a clause after it ("the last skill I should
# install"), a bare "the other", "which one" anywhere, a "#N" or "number N"
# that numbers a pull request, an issue, a ranking or a step, "one"
# starting a compound, and the idiom "of both".
NEW_SUBJECTS = (
    "how do I create my first skill?",
    "should I add a second skill for linting?",
    "which one is best for setting up pre-commit hooks for linting?",
    "which one handles pdfs?",
    "how do I scaffold the other SKILL.md frontmatter?",
    "what's the last skill I should install for linting",
    "how do I review PR #2?",
    "how do I fix issue number 2",
    "how do I make this one-liner a reusable skill?",
    "how do I write the first one-shot prompt?",
    "how does that one-off script work",
    "which skill is #1 for security?",
    "how do I review PRs #2 and #3?",
    "is it issue #2 or #3 that breaks CI?",
    "try PR #2 vs #3",
    "what is number 1 for linting in the catalogue?",
    "what's the best of both worlds for testing?",
    "how do I merge steps #1 and #2 of my setup?",
    "try bug #2 vs #3",
    "is ticket #2 worse than #3?",
    "compare pull request #2 with #3",
)

# Follow-ups that point at the previous answer, with the row each one leads
# with: the one it names, or the first.
POINTERS = (
    ("which of these should I install first?", "orch-review"),
    ("how is it different from the others?", "orch-review"),
    ("what about the others?", "orch-review"),
    ("compare them", "orch-review"),
    ("which one of these handles pdfs?", "orch-review"),
    ("any of those skills free?", "orch-review"),
    ("what about that one?", "orch-review"),
    ("what about the second one?", "code-reviewer"),
    ("and the 2nd skill?", "code-reviewer"),
    ("#2", "code-reviewer"),
    ("tell me about #3", "teach"),
    ("is number 1 any good", "orch-review"),
    ("what does the last one do?", "teach"),
    ("and second one?", "code-reviewer"),
    ("or #3?", "teach"),
    ("and #3?", "teach"),
    ("try #2", "code-reviewer"),
    ("install #3", "teach"),
    ("how does it work with #2?", "code-reviewer"),
    ("is #3 better than #2?", "teach"),
    ("is it better than #2?", "code-reviewer"),
    ("how does it stack up vs #3?", "teach"),
    ("which one among them?", "orch-review"),
    ("is teach better than those skills?", "teach"),
)


class TestReferentialFollowUps:
    """A follow-up that points back at the last answer leads with it.

    The 2026-08 audit: chat's own suggestion "which of these should I install
    first?" re-queried the catalogue and came back with nothing from the turn
    before — and at seven words it never even reached expand_query's gate.
    """

    def test_which_of_these_leads_with_the_previous_skills(self, ranker):
        entries, engine = chat.retrieve("which of these should I install first?",
                                        [_turn()])
        assert _names(entries) == _names(SHOWN) + _names(UNRELATED)
        assert engine == "previous answer + BM25 full-content"
        # Seven words: main sends it alone, and so does the search here.
        assert ranker == ["which of these should I install first?"]

    def test_the_others_is_referential(self, ranker):
        entries, _ = chat.retrieve("how is code-reviewer different from the others?",
                                   [_turn()])
        # The previous rows lead, and the skill the question names leads them.
        assert _names(entries)[:3] == ["code-reviewer", "orch-review", "teach"]

    @pytest.mark.parametrize("question, name", [
        ("what about the second one?", "code-reviewer"),
        ("tell me about #3", "teach"),
        ("is number 1 any good", "orch-review"),
        ("what does the last one do?", "teach"),
        ("and the 2nd skill?", "code-reviewer"),
        ("the first one", "orch-review"),
        ("the third skill", "teach"),
        ("3rd option?", "teach"),
        ("1st result", "orch-review"),
    ])
    def test_an_ordinal_puts_that_row_first_and_keeps_the_rest(
            self, ranker, question, name):
        entries, _ = chat.retrieve(question, [_turn()])
        rest = [n for n in _names(SHOWN) if n != name]
        assert _names(entries) == [name, *rest, *_names(UNRELATED)]

    def test_a_word_ordinal_past_the_end_keeps_the_whole_set(self, ranker):
        entries, _ = chat.retrieve("what about the fifth one?", [_turn()])
        assert _names(entries) == _names(SHOWN) + _names(UNRELATED)

    @pytest.mark.parametrize("question", [
        "how do I review PR #42?", "what about #0?", "is number 9 any good"])
    def test_a_number_past_the_end_is_not_a_row(self, ranker, question):
        # "#42" is a pull request, not the 42nd of three rows.
        entries, engine = chat.retrieve(question, [_turn()])
        assert _names(entries) == _names(UNRELATED)
        assert engine == "BM25 full-content"

    def test_a_number_past_the_end_still_honours_a_pointer(self, ranker):
        entries, _ = chat.retrieve("which of these fixes #42?", [_turn()])
        assert _names(entries)[:3] == _names(SHOWN)

    def test_a_name_the_previous_answer_showed_past_k_still_leads(self, ranker):
        # k=2 carries two rows; "teach" was the third. The question names it,
        # and it was on screen, so it leads rather than falling off the end.
        entries, engine = chat.retrieve("is teach better than those skills?",
                                        [_turn()], k=2)
        assert engine.startswith("previous answer")
        assert _names(entries)[:3] == ["teach", "orch-review", "code-reviewer"]

    def test_k_bounds_the_carried_rows_and_the_search_alike(self, ranker):
        entries, _ = chat.retrieve("which of these?", [_turn()], k=2)
        assert _names(entries) == ["orch-review", "code-reviewer",
                                   "mercury-mcp", "write-concisely"]
        entries, _ = chat.retrieve("which of these?", [_turn()], k=1)
        assert _names(entries) == ["orch-review", "mercury-mcp"]

    def test_a_search_hit_the_previous_answer_showed_is_listed_once(
            self, ranker, monkeypatch):
        # Equal dicts, as a second catalogue load returns them.
        monkeypatch.setattr(chat.rag, "retrieve_any", lambda q, k=60, entries=None, **kw: (
            [{"entry": dict(e)} for e in [SHOWN[2], *UNRELATED]], "BM25 full-content"))
        entries, _ = chat.retrieve("which of these?", [_turn()])
        assert _names(entries) == _names(SHOWN) + _names(UNRELATED)

    def test_the_frontmatter_floor_follows_a_pointer_too(self, ranker, monkeypatch):
        monkeypatch.setattr(chat.rag, "retrieve_any",
                            lambda q, k=60, entries=None, **kw: (None, "none"))
        monkeypatch.setattr(catalog, "search",
                            lambda q: [(e, 1.0) for e in [*UNRELATED, PRE_COMMIT]])
        entries, engine = chat.retrieve("which of these?", [_turn()], k=2)
        assert engine == "previous answer + frontmatter scan"
        assert _names(entries) == ["orch-review", "code-reviewer", *_names(UNRELATED)]

    def test_without_history_it_is_an_ordinary_query(self, ranker):
        entries, engine = chat.retrieve("which of these should I install first?")
        assert _names(entries) == _names(UNRELATED)
        assert engine == "BM25 full-content"

    def test_a_previous_turn_with_no_skills_falls_back_to_retrieval(self, ranker):
        entries, engine = chat.retrieve("which of these should I install first?",
                                        [_turn(())])
        assert (_names(entries), engine) == (_names(UNRELATED), "BM25 full-content")

    def test_a_non_referential_short_followup_still_expands(self, ranker):
        chat.retrieve("and for python?", [_turn()])
        assert ranker == ["how do I review a diff? and for python?"]

    @pytest.mark.parametrize("question", [
        "how do I fix those flaky tests in CI?",
        "which skill writes commit messages?",
        "install it first",
        "compare PR #2 with #3",
        *NEW_SUBJECTS,
    ])
    def test_ordinary_questions_are_not_referential(self, question):
        assert not chat.is_referential(question)

    @pytest.mark.parametrize("question", NEW_SUBJECTS)
    def test_a_new_subject_is_searched_not_carried(self, ranker, question):
        entries, engine = chat.retrieve(question, [_turn()])
        assert engine == "BM25 full-content", "answered from the previous list"
        assert not set(_names(SHOWN)) & set(_names(entries))
        assert set(_names(UNRELATED)) <= set(_names(entries))
        assert len(ranker) == 1

    @pytest.mark.parametrize("question", [question for question, _ in POINTERS])
    def test_referential_questions_are_recognised(self, question):
        assert chat.is_referential(question)

    def test_a_long_referential_question_searches_what_main_searches(self):
        # The carried rows supply the subject; the search stays main's, which
        # is what keeps a misread pointer from losing main's answer.
        history = [chat.Turn("how do I review a diff", "...")]
        q = "which of these should I install first?"
        assert chat.expand_query(q, history) == q

    def test_the_session_keeps_what_each_turn_drew_on(self):
        assert chat.Turn("q", "a").skills == ()
        assert _turn().skills == SHOWN


class TestAMisreadPointerCostsOrderNotTheAnswer:
    """A referential follow-up never replaces the search; it goes in front of it.

    Two rounds of narrowing the detector each left new questions answered
    from the previous list alone — "this one-liner", "which skill is #1 for
    security?", "PRs #2 and #3", "best of both worlds" — with main's answer
    nowhere in sight. The detector cannot be made perfect, so its mistakes are
    made cheap instead: the search main would have run still runs, and its
    results are still returned.
    """

    @pytest.mark.parametrize("question", NEW_SUBJECTS)
    def test_main_s_top_result_is_still_returned(self, searched, question):
        entries, _ = chat.retrieve(question, [_turn()])
        assert _top_for(_main_query(question))["name"] in _names(entries)

    @pytest.mark.parametrize("question", NEW_SUBJECTS)
    def test_a_detector_that_fires_on_everything_only_reorders(
            self, searched, monkeypatch, question):
        # The worst detector possible: every question read as a pointer.
        monkeypatch.setattr(chat, "is_referential", lambda q: True)
        entries, engine = chat.retrieve(question, [_turn()])
        assert engine.startswith("previous answer"), "the misreading did not happen"
        main = [_top_for(_main_query(question)), *UNRELATED]
        assert set(_names(main)) <= set(_names(entries)), "main's answer was lost"
        assert searched == [_main_query(question)], "searched something main never did"

    @pytest.mark.parametrize("question, first", POINTERS)
    def test_a_pointer_leads_with_the_previous_rows(self, searched, question, first):
        entries, engine = chat.retrieve(question, [_turn()])
        names = _names(entries)
        assert names[0] == first
        assert sorted(names[:3]) == sorted(_names(SHOWN))
        assert _top_for(_main_query(question))["name"] in names[3:]
        assert engine == "previous answer + BM25 full-content"


class TestExactNameRanksFirst:
    """Asking about a skill by name puts that skill first."""

    def test_a_named_skill_the_previous_answer_never_showed_follows_it(self, ranker):
        # Points at the list and names a skill outside it. Without the
        # catalogue the named skill is unreachable, and an AI answer about it
        # is then rejected as naming something outside the sources. It goes
        # after the list, which is what the question points at.
        entries, engine = chat.retrieve("is pre-commit better than those skills?",
                                        [_turn()])
        assert engine == "previous answer + BM25 full-content"
        assert _names(entries) == [*_names(SHOWN), "pre-commit", *_names(UNRELATED)]

    def test_which_of_these_handles_a_named_skill_drops_none_of_these(self, ranker):
        entries, _ = chat.retrieve("which of these handles pre-commit hooks?",
                                   [_turn()], k=3)
        assert _names(entries)[:4] == [*_names(SHOWN), "pre-commit"]

    def test_an_ordinal_row_keeps_a_skill_the_question_names(self, ranker):
        entries, _ = chat.retrieve("is the second one better than pre-commit?",
                                   [_turn()])
        assert _names(entries) == ["code-reviewer", "orch-review", "teach",
                                   "pre-commit", *_names(UNRELATED)]

    def test_a_named_search_hit_is_listed_once(self, ranker):
        entries, _ = chat.retrieve("is write-concisely better than those skills?",
                                   [_turn()])
        assert _names(entries) == [*_names(SHOWN), "write-concisely", "mercury-mcp"]

    def test_a_named_hit_moves_to_the_top(self, ranker, monkeypatch):
        monkeypatch.setattr(chat.rag, "retrieve_any", lambda q, k=60, entries=None, **kw: (
            [{"entry": e} for e in [*UNRELATED, SHOWN[0]]], "BM25 full-content"))
        entries, _ = chat.retrieve("what does orch-review actually do?")
        assert _names(entries) == ["orch-review", "mercury-mcp", "write-concisely"]

    def test_a_named_skill_the_ranker_missed_is_pulled_from_the_catalogue(
            self, ranker):
        entries, _ = chat.retrieve("what does orch-review actually do?", k=2)
        assert _names(entries) == ["orch-review", "mercury-mcp"]

    def test_a_one_word_name_counts_when_it_was_just_shown(self, ranker):
        # Single words are only names when the user was just shown one: "teach"
        # in an arbitrary question is English.
        entries, _ = chat.retrieve("what does teach do?", [_turn()])
        assert _names(entries)[0] == "teach"
        entries, _ = chat.retrieve("what does teach do?")
        assert "teach" not in _names(entries)

    def test_the_row_the_user_saw_wins_over_a_namesake(self, ranker, monkeypatch):
        other = _entry("orch-review", "A different tap's copy", tap="other/tap")
        monkeypatch.setattr(chat.rag, "retrieve_any", lambda q, k=60, entries=None, **kw: (
            [{"entry": other}] + [{"entry": e} for e in UNRELATED], "BM25 full-content"))
        entries, _ = chat.retrieve("what does orch-review do?", [_turn()])
        assert entries[0] is SHOWN[0]
        assert other in entries, "the namesake was dropped rather than ranked after"

    def test_a_pointer_resolves_a_new_name_to_the_copy_the_search_ranked(
            self, ranker, monkeypatch):
        ranked = _entry("pre-commit", "The copy the search ranked", tap="other/tap")
        monkeypatch.setattr(chat.rag, "retrieve_any", lambda q, k=60, entries=None, **kw: (
            [{"entry": ranked}], "BM25 full-content"))
        entries, _ = chat.retrieve("is pre-commit better than those skills?", [_turn()])
        assert entries[3] is ranked
        assert PRE_COMMIT not in entries

    def test_an_equal_row_from_a_reloaded_catalogue_is_listed_once(self):
        reloaded = [dict(e) for e in SHOWN]
        ranked = chat.promote_named("what does teach do?", reloaded, previous=SHOWN)
        assert _names(ranked) == ["teach", "orch-review", "code-reviewer"]

    def test_no_name_leaves_the_ranking_alone(self):
        assert chat.promote_named("review my diff", UNRELATED) == UNRELATED

    def test_names_lead_in_the_order_the_question_gives_them(self):
        ranked = chat.promote_named("teach vs orch-review", SHOWN, previous=SHOWN)
        assert _names(ranked) == ["teach", "orch-review", "code-reviewer"]

    def test_the_frontmatter_floor_is_promoted_too(self, ranker, monkeypatch):
        monkeypatch.setattr(chat.rag, "retrieve_any",
                            lambda q, k=60, entries=None, **kw: (None, "none"))
        monkeypatch.setattr(catalog, "search",
                            lambda q: [(e, 1.0) for e in [*UNRELATED, SHOWN[1]]])
        entries, engine = chat.retrieve("what does code-reviewer do?")
        assert engine == "frontmatter scan"
        assert _names(entries)[0] == "code-reviewer"


class TestSuggestionsAreAnswerable:
    """Without AI, only suggest what the extractive answer can actually answer."""

    def test_without_ai_only_the_lookup_question_is_offered(self):
        assert chat.suggest_followups(SHOWN, with_ai=False) == [
            "what does orch-review actually do?"]

    def test_without_ai_no_results_suggests_nothing(self):
        assert chat.suggest_followups([], with_ai=False) == []

    def test_a_nameless_row_offers_no_lookup(self):
        assert chat.suggest_followups([{"tap": "a/b"}], with_ai=False) == []
        assert chat.suggest_followups([{"tap": "a/b"}], with_ai=True) == [
            "which of these should I install first?"]

    def test_with_ai_the_comparisons_are_offered(self):
        out = chat.suggest_followups(SHOWN, with_ai=True)
        assert "which of these should I install first?" in out
        assert any("different from the others" in s for s in out)

    def test_the_offered_question_is_answered_about_that_skill(self, ranker, no_ai):
        # The contract that matters: chat's own suggestion, typed back in,
        # answers about the skill it names.
        q = chat.suggest_followups(UNRELATED, with_ai=False)[0]
        reply = chat.answer(q, [chat.Turn("x", "y", UNRELATED[::-1])])
        assert reply.skills[0]["name"] == UNRELATED[0]["name"]
