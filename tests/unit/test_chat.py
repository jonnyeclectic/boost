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

from typing import List

import pytest

from boost_cli.core import ai, catalog, chat
from boost_cli.errors import BoostError


def _entry(name: str, desc: str = "", tap: str = "acme/skills",
           kind: str = "skill") -> dict:
    return {"name": name, "tap": tap, "kind": kind, "description": desc,
            "skill_md": "%s/SKILL.md" % name}


CANDIDATES: List[dict] = [
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
        _with_ai(monkeypatch, "")
        reply = chat.answer("review my diff")
        assert reply.source == "extractive"
        assert reply.grounded is True


class TestWorksWithoutAI:
    """The keyless/offline path has to be useful, not an apology."""

    def test_it_answers_with_the_retrieved_skills(self, sandbox, retrieved, no_ai):
        reply = chat.answer("review my diff")
        assert reply.source == "extractive"
        assert "code-reviewer" in reply.text
        assert "Reviews a diff for bugs and style" in reply.text

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
