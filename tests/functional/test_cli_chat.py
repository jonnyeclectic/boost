# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: `boost chat`, in-process.

The engine is covered in tests/unit/test_chat.py. This pins the CLI contract —
exit codes, that `--json` is parseable, that citations are shown by default, and
that a rejected AI reply is *reported* rather than silently downgraded.

The sandbox fixture sets BOOST_NO_AI=1, so the default path here is the
extractive one — which is the right default to pin, because it is what every
keyless install gets.
"""
from __future__ import annotations

import io
import json
import re


class TestChatRequiresATap:
    def test_no_taps_is_an_error_with_a_hint(self, boost):
        r = boost("chat", "anything", expect=1)
        assert "no taps configured" in r.err
        assert "boost tap --defaults" in r.err


class TestOneShot:
    def test_a_question_gets_an_answer(self, boost, tapped):
        r = boost("chat", "brainstorming ideas")
        assert r.out.strip(), "answered with nothing"

    def test_citations_are_shown_by_default(self, boost, tapped):
        # The next step after an answer is installing code that runs inside the
        # user's agent, so a claim has to be checkable against a real entry.
        r = boost("chat", "brainstorming ideas")
        assert "sources" in r.out

    def test_the_source_list_is_numbered(self, boost, tapped):
        # The model is handed a list numbered from 1 and told to answer from
        # "the numbered skills", so it writes "(#3)". Rendering the same list
        # unnumbered made every such citation point at nothing, and left the
        # reader counting rows to decode an answer written to be scanned.
        r = boost("chat", "brainstorming ideas")
        body = r.out.split("sources ·", 1)[1]
        assert "1. " in body, "source block is unnumbered — citations cannot resolve"

    def test_no_sources_suppresses_them(self, boost, tapped):
        r = boost("chat", "brainstorming ideas", "--no-sources")
        assert "sources ·" not in r.out

    def test_the_answer_names_the_next_command(self, boost, tapped):
        # Without AI the answer is extractive, and its job is to get the user to
        # the skill rather than to sound conversational.
        r = boost("chat", "brainstorming ideas")
        assert "boost install" in r.out or "boost info" in r.out


class TestJson:
    def test_json_is_parseable_and_complete(self, boost, tapped):
        r = boost("chat", "--json", "brainstorming ideas")
        payload = json.loads(r.out)
        assert set(payload) == {"question", "answer", "engine", "source",
                                "grounded", "skills"}
        assert payload["question"] == "brainstorming ideas"

    def test_json_reports_which_engine_ran(self, boost, tapped):
        payload = json.loads(boost("chat", "--json", "brainstorming").out)
        assert payload["engine"], "an answer with no attribution is unauditable"

    def test_json_skills_carry_name_and_tap(self, boost, tapped):
        payload = json.loads(boost("chat", "--json", "brainstorming").out)
        for skill in payload["skills"]:
            assert skill["name"] and skill["tap"]

    def test_json_without_a_question_is_an_error(self, boost, tapped):
        # --json implies one-shot; there is no sensible interactive JSON.
        r = boost("chat", "--json", expect=1)
        assert "needs a question" in r.err

    def test_json_carries_no_human_chrome(self, boost, tapped):
        # Other programs parse this; a stray citation block corrupts it.
        r = boost("chat", "--json", "brainstorming ideas")
        assert "sources ·" not in r.out
        json.loads(r.out)


class TestRejectedRepliesAreReported:
    def test_an_invented_name_warns_rather_than_downgrading_silently(
            self, boost, tapped, monkeypatch):
        from boost_cli.core import ai
        monkeypatch.setattr(ai, "available", lambda: True)
        monkeypatch.setattr(ai, "ask",
                            lambda *a, **kw: "Install docker-compose-expert for that.")
        r = boost("chat", "brainstorming ideas")
        assert "docker-compose-expert" not in r.out
        assert "outside the retrieved skills" in r.err or \
               "outside the retrieved skills" in r.out

    def test_json_marks_it_ungrounded(self, boost, tapped, monkeypatch):
        from boost_cli.core import ai
        monkeypatch.setattr(ai, "available", lambda: True)
        monkeypatch.setattr(ai, "ask",
                            lambda *a, **kw: "Install docker-compose-expert for that.")
        payload = json.loads(boost("chat", "--json", "brainstorming").out)
        assert payload["grounded"] is False
        assert payload["source"] == "extractive"

    def test_a_failed_ai_call_is_reported_not_silent(self, boost, tapped, monkeypatch):
        # The audit bug this card fixes: AI was available and was tried, the
        # call itself returned nothing, and one-shot chat said nothing about
        # it — indistinguishable from the deliberate extractive answer every
        # keyless install gets.
        from boost_cli.core import ai
        monkeypatch.setattr(ai, "available", lambda: True)
        monkeypatch.setattr(ai, "ask", lambda *a, **kw: None)
        r = boost("chat", "brainstorming ideas")
        assert "AI" in r.err and "heuristic fallback" in r.err


class TestLimit:
    def test_limit_bounds_the_candidates(self, boost, tapped):
        payload = json.loads(boost("chat", "--json", "-k", "2", "skills").out)
        assert len(payload["skills"]) <= 2

    def test_limit_must_be_positive_int(self, boost, tapped):
        # -k 0 used to slice every retrieved hit to nothing and fabricate
        # "Nothing in the tapped catalogue matches that" for a real query.
        r = boost("chat", "-k", "0", "skills", expect=2)
        assert "must be >= 1" in r.err
        r = boost("chat", "-k", "-1", "skills", expect=2)
        assert "must be >= 1" in r.err


class _FakeTtyStdin(io.StringIO):
    """Scripted stdin that claims to be a terminal, so the prompt fires."""

    def isatty(self):
        return True


def _session(boost, monkeypatch, *lines, tty=False, args=()):
    text = "".join(line + "\n" for line in lines)
    monkeypatch.setattr("sys.stdin", _FakeTtyStdin(text) if tty else io.StringIO(text))
    return boost("chat", *args)


def _source_blocks(out):
    """Each answer's ``(engine, cited names)``, in order — one per answered question."""
    blocks: list[tuple[str, list[str]]] = []
    for line in out.splitlines():
        ranked = re.search(r"sources · ranked by (.+)", line)
        if ranked:
            blocks.append((ranked.group(1).strip(), []))
        m = re.match(r"\s+\d+\. (\S+)  ", line)
        if m and blocks:
            blocks[-1][1].append(m.group(1))
    return blocks


class TestPipedSession:
    """A script piping questions in gets answers, not prompt chrome.

    The 2026-08 audit captured three "> " lines in stdout with stdin piped.
    """

    def test_no_prompt_reaches_piped_stdout(self, boost, tapped, monkeypatch):
        r = _session(boost, monkeypatch, "brainstorming ideas", "commit messages")
        assert "brainstorming" in r.out, "the questions were not answered"
        assert "> " not in r.out
        assert "Ctrl-D" not in r.out, "typing instructions with nobody typing"

    def test_empty_piped_stdin_prints_no_prompt(self, boost, tapped, monkeypatch):
        r = _session(boost, monkeypatch)
        assert "> " not in r.out
        assert not r.out.endswith("\n\n"), "a blank line closing a prompt never shown"

    def test_a_terminal_still_gets_the_prompt(self, boost, tapped, monkeypatch):
        r = _session(boost, monkeypatch, "brainstorming ideas", tty=True)
        assert r.out.count("> ") == 2, "one prompt per read, including the one hit by EOF"
        assert "Ctrl-D to exit" in r.out


class TestSessionFollowUps:
    def test_which_of_these_answers_from_the_previous_turn(
            self, boost, tapped, monkeypatch):
        r = _session(boost, monkeypatch, "how do I write commit messages?",
                     "which of these should I install first?", args=("-k", "2"))
        (_, first), (engine, second) = _source_blocks(r.out)
        assert first and second[:len(first)] == first
        # The label is what tells the wiring apart from a re-query that happens
        # to return the same rows on a small catalogue.
        assert engine.startswith("previous answer + "), \
            "the session did not keep the turn's skills"

    def test_an_ordinal_answers_with_that_row_of_the_previous_turn(
            self, boost, tapped, monkeypatch):
        r = _session(boost, monkeypatch, "how do I write commit messages?",
                     "what about the second one?")
        (_, first), (engine, second) = _source_blocks(r.out)
        assert len(first) >= 2
        assert engine.startswith("previous answer + ")
        # That row first, and the rest of the list still after it.
        assert second[0] == first[1] and set(first) <= set(second)

    def test_a_new_subject_is_searched_not_carried(self, boost, tapped, monkeypatch):
        # "which one" with no pointer asks the catalogue, not the last list.
        r = _session(boost, monkeypatch, "how do I write commit messages?",
                     "which one is best for test-driven development?")
        _, (engine, second) = _source_blocks(r.out)
        assert not engine.startswith("previous answer")
        assert second and second[0] == "tdd-workflow"

    def test_without_ai_it_only_suggests_what_it_can_answer(
            self, boost, tapped, monkeypatch):
        r = _session(boost, monkeypatch, "how do I write commit messages?")
        tries = [l.strip() for l in r.out.splitlines() if l.strip().startswith("try:")]
        assert tries and all("actually do?" in t for t in tries), tries

    def test_with_ai_it_suggests_the_comparisons_too(self, boost, tapped, monkeypatch):
        from boost_cli.core import ai
        monkeypatch.setattr(ai, "available", lambda: True)
        monkeypatch.setattr(ai, "ask", lambda *a, **kw: None)
        r = _session(boost, monkeypatch, "how do I write commit messages?")
        assert "different from the others?" in r.out

    def test_a_blank_line_ends_the_session(self, boost, tapped, monkeypatch):
        r = _session(boost, monkeypatch, "", "how do I write commit messages?")
        assert "sources" not in r.out, "answered a question after the blank line"
