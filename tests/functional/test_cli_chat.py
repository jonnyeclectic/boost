# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Functional tests: `boost chat`, in-process.

The engine is covered in tests/unit/test_chat.py. This pins the CLI contract —
exit codes, that `--json` is parseable, that citations are shown by default, and
that a rejected AI reply is *reported* rather than silently downgraded.

The sandbox fixture sets BOOST_NO_AI=1, so the default path here is the
extractive one — which is the right default to pin, because it is what every
keyless install gets.
"""
from __future__ import annotations

import json


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


class TestLimit:
    def test_limit_bounds_the_candidates(self, boost, tapped):
        payload = json.loads(boost("chat", "--json", "-k", "2", "skills").out)
        assert len(payload["skills"]) <= 2
