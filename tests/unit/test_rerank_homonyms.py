# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: an LLM rerank reorders the shortlist and never shrinks it.

The model answers with names, and a name is not an identity — two taps can
both ship a ``brainstorming``, and a rule and a skill can share
``python-style``. Both rerank paths (``rag.rerank``, behind MCP
``boost_search``, and ``discovery._ai_rank``, behind ``search --smart``) used
to build a name-keyed dict, keep the last homonym, and then drop every row the
model had named — so ``search --smart`` printed "1 match" where BM25 had 2.
"""
from __future__ import annotations

import pytest

from boost_cli.commands import discovery
from boost_cli.core import rag


def _hit(name: str, tap: str, kind: str = "skill") -> dict:
    return {"entry": {"name": name, "tap": tap, "kind": kind,
                      "description": "%s from %s" % (name, tap),
                      "skill_md": "skills/%s/SKILL.md" % name},
            "score": 1.0, "snippet": "%s snippet" % name}


def _rows(hits) -> list:
    return [(h["entry"]["name"], h["entry"]["tap"]) for h in hits]


class TestReorderByNames:
    def test_a_named_homonym_brings_every_copy_in_incoming_order(self):
        items = ["a1", "b", "a2", "c"]
        out = rag.reorder_by_names(items, ["a", "c"], lambda s: s[0])
        assert out == ["a1", "a2", "c", "b"]

    def test_a_repeated_name_emits_its_group_once(self):
        out = rag.reorder_by_names(["a1", "a2", "b"], ["a", "a", "b"],
                                   lambda s: s[0])
        assert out == ["a1", "a2", "b"]

    def test_an_invented_name_selects_nothing(self):
        out = rag.reorder_by_names(["a", "b"], ["zzz", "b"], lambda s: s)
        assert out == ["b", "a"]

    def test_non_string_names_in_the_order_still_match(self):
        out = rag.reorder_by_names(["1", "2"], [2, 1], lambda s: s)
        assert out == ["2", "1"]

    def test_an_empty_order_keeps_the_incoming_order(self):
        assert rag.reorder_by_names(["a", "b"], [], lambda s: s) == ["a", "b"]


@pytest.fixture
def stub_ai(monkeypatch, sandbox):
    monkeypatch.setenv("BOOST_NO_RERANK_CACHE", "1")
    monkeypatch.setattr(rag.ai, "available", lambda: True)

    def _reply(text):
        monkeypatch.setattr(rag.ai, "ask", lambda *_a, **_k: text)
    return _reply


class TestRagRerankKeepsHomonyms:
    def test_both_taps_brainstorming_survive(self, stub_ai):
        stub_ai('["brainstorming"]')
        hits = [_hit("brainstorming", "tap2"), _hit("brainstorming", "fixture")]
        out, label = rag.rerank("brainstorming", hits, limit=10)
        assert _rows(out) == [("brainstorming", "tap2"),
                              ("brainstorming", "fixture")]
        assert label == rag.LLM_RANKER

    def test_a_rule_and_a_skill_sharing_a_name_both_survive(self, stub_ai):
        stub_ai('["python-style", "other"]')
        hits = [_hit("other", "t"), _hit("python-style", "r", kind="rule"),
                _hit("python-style", "s")]
        out, _label = rag.rerank("python style", hits, limit=10)
        assert _rows(out) == [("python-style", "r"), ("python-style", "s"),
                              ("other", "t")]

    def test_limit_still_applies_after_the_reorder(self, stub_ai):
        stub_ai('["b", "a"]')
        hits = [_hit("a", "x"), _hit("a", "y"), _hit("b", "z")]
        out, _label = rag.rerank("q", hits, limit=2)
        assert _rows(out) == [("b", "z"), ("a", "x")]


class TestSmartRankKeepsHomonyms:
    def test_both_taps_brainstorming_survive(self, stub_ai):
        stub_ai('["brainstorming"]')
        scored = [(_hit("brainstorming", "tap2")["entry"], 2.0),
                  (_hit("brainstorming", "fixture")["entry"], 1.0)]
        out = discovery._ai_rank("brainstorming", scored)
        assert [(e["tap"], s) for e, s in out] == [("tap2", 2.0),
                                                    ("fixture", 1.0)]

    def test_named_homonyms_move_ahead_together(self, stub_ai):
        stub_ai('["a"]')
        scored = [(_hit("b", "t")["entry"], 3.0),
                  (_hit("a", "x")["entry"], 2.0),
                  (_hit("a", "y")["entry"], 1.0)]
        out = discovery._ai_rank("q", scored)
        assert [(e["name"], e["tap"]) for e, _s in out] == [
            ("a", "x"), ("a", "y"), ("b", "t")]

    def test_an_unparseable_reply_is_none(self, stub_ai):
        stub_ai("nope")
        assert discovery._ai_rank("q", [(_hit("a", "x")["entry"], 1.0)]) is None
