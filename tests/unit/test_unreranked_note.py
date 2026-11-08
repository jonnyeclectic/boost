# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_search's closing note names why the rerank did not run.

With ``BOOST_NO_AI=1`` and `claude` on PATH, the ``initialize`` instructions
said no AI backend was available or enabled, and every boost_search reply on
the same connection still ended "Configure ANTHROPIC_API_KEY or the `claude`
CLI to enable it." -- telling the agent to set up what the user had turned
off on purpose, with both remedies already present.
"""
from __future__ import annotations

import pytest

from boost_cli.commands import configuration
from boost_cli.core import ai, config, mcp, rag

KEY_ADVICE = "Configure ANTHROPIC_API_KEY or the `claude` CLI"


@pytest.fixture
def claude_on_path(monkeypatch):
    monkeypatch.setattr(ai, "has_cli", lambda: True)


class TestUnavailableCause:
    def test_the_env_switch(self, sandbox, claude_on_path, monkeypatch):
        monkeypatch.setenv("BOOST_NO_AI", "1")
        assert ai.unavailable_cause() == ai.CAUSE_DISABLED

    def test_the_config_switch(self, sandbox, claude_on_path, monkeypatch):
        monkeypatch.delenv("BOOST_NO_AI", raising=False)
        config.set_value("ai.enabled", "false")
        assert ai.unavailable_cause() == ai.CAUSE_DISABLED

    def test_no_backend(self, sandbox, monkeypatch):
        monkeypatch.delenv("BOOST_NO_AI", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setattr(ai, "has_cli", lambda: False)
        assert ai.unavailable_cause() == ai.CAUSE_MISSING

    def test_a_key_alone_is_a_backend(self, sandbox, monkeypatch):
        monkeypatch.delenv("BOOST_NO_AI", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        monkeypatch.setattr(ai, "has_cli", lambda: False)
        assert ai.unavailable_cause() == ai.CAUSE_FAILED

    def test_a_backend_that_did_not_answer(self, sandbox, claude_on_path,
                                           monkeypatch):
        monkeypatch.delenv("BOOST_NO_AI", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert ai.unavailable_cause() == ai.CAUSE_FAILED


class TestUnrerankedNote:
    def test_disabled_names_the_setting_and_gives_no_key_advice(self):
        note = mcp.unreranked_note("BM25", ai.CAUSE_DISABLED,
                                   "disabled (BOOST_NO_AI is set)")
        assert "did NOT run" in note
        assert ("AI is disabled (BOOST_NO_AI is set) on this machine: a "
                "setting, not a fault, so leave it as it is.)") in note
        assert KEY_ADVICE not in note

    def test_missing_keeps_the_setup_advice(self):
        note = mcp.unreranked_note("BM25", ai.CAUSE_MISSING, "unavailable")
        assert note.endswith(KEY_ADVICE + " to enable it.)")

    def test_failed_names_the_failure_and_gives_no_key_advice(self):
        note = mcp.unreranked_note("BM25", ai.CAUSE_FAILED,
                                   "claude CLI timed out — see the log")
        assert note.endswith("An AI backend is configured and did not "
                             "rerank this call (claude CLI timed out — see "
                             "the log).)")
        assert KEY_ADVICE not in note

    def test_the_causes_are_the_words_the_note_branches_on(self):
        # mcp stays free of an `ai` import, so it compares the words.
        assert (ai.CAUSE_DISABLED, ai.CAUSE_MISSING, ai.CAUSE_FAILED) == (
            "disabled", "missing", "failed")

    @pytest.mark.parametrize("cause", ["disabled", "missing", "failed"])
    def test_every_cause_names_the_ranker(self, cause):
        note = mcp.unreranked_note("hybrid RRF", cause, "r")
        assert note.startswith("\n(ranked by hybrid RRF — the LLM rerank did "
                               "NOT run, so this is a shortlist to read "
                               "rather than a verdict to act on. ")


class TestTheSearchReplyUsesIt:
    def test_ai_off_on_purpose_with_claude_present(self, sandbox,
                                                   claude_on_path,
                                                   monkeypatch):
        monkeypatch.setenv("BOOST_NO_AI", "1")
        note = configuration._ranking_note("BM25 full-content")
        assert "BOOST_NO_AI is set" in note
        assert KEY_ADVICE not in note

    def test_a_reranked_reply_is_unchanged(self, sandbox):
        assert configuration._ranking_note(rag.LLM_RANKER) == \
            "\n(ranked by %s)" % rag.LLM_RANKER
