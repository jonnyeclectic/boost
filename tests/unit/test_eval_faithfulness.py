# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the Ragas-methodology faithfulness scorer (evals/faithfulness.py).

The scorer's real inputs are LLM replies, which are neither available nor
deterministic in CI — so the bridge is stubbed and what gets tested is the part
that can actually be wrong: parsing a model's reply, the supported/total
arithmetic, and the degradation contract. That contract matters as much as the
score: an eval that silently reports 0.0 when it could not reach a model is
worse than one that reports nothing, because 0.0 reads as "the model
overclaimed" when it means "nothing was measured".
"""
from __future__ import annotations

import pytest

from evals import faithfulness


@pytest.fixture()
def stub_ai(monkeypatch):
    """Replace core.ai.ask with a scripted sequence of replies."""
    def install(*replies):
        queue = list(replies)
        calls = []

        def fake_ask(prompt, system=None, **kw):
            calls.append({"prompt": prompt, "system": system})
            return queue.pop(0) if queue else None

        from boost_cli.core import ai
        monkeypatch.setattr(ai, "ask", fake_ask)
        monkeypatch.setattr(ai, "ask_author", fake_ask)
        monkeypatch.setattr(ai, "available", lambda: True)
        return calls
    return install


class TestJsonValue:
    def test_bare_array(self):
        assert faithfulness._json_value('["a", "b"]') == ["a", "b"]

    def test_array_wrapped_in_prose(self):
        assert faithfulness._json_value(
            'Sure! Here you go:\n["a"]\nLet me know.') == ["a"]

    def test_array_inside_a_code_fence(self):
        assert faithfulness._json_value('```json\n["a", "b"]\n```') == ["a", "b"]

    @pytest.mark.parametrize("text", [None, "", "no array here",
                                      "[not valid json"])
    def test_unparseable_is_none(self, text):
        assert faithfulness._json_value(text) is None


class TestExtractStatements:
    def test_parses_and_strips(self, stub_ai):
        stub_ai('["  The agent writes a failing test first.  ", "It refactors."]')
        assert faithfulness.extract_statements("some answer") == [
            "The agent writes a failing test first.", "It refactors."]

    def test_drops_blank_entries(self, stub_ai):
        stub_ai('["real statement", "   ", ""]')
        assert faithfulness.extract_statements("x") == ["real statement"]

    def test_unparseable_reply_is_none(self, stub_ai):
        stub_ai("I could not do that.")
        assert faithfulness.extract_statements("x") is None

    def test_no_reply_is_none(self, stub_ai):
        stub_ai(None)
        assert faithfulness.extract_statements("x") is None


class TestVerifyStatements:
    def test_parses_verdicts(self, stub_ai):
        stub_ai('[{"statement": "a", "supported": true, "reason": "stated"},'
                ' {"statement": "b", "supported": false, "reason": "absent"}]')
        got = faithfulness.verify_statements(["a", "b"], "context")
        assert [v["supported"] for v in got] == [True, False]
        assert got[1]["reason"] == "absent"

    def test_numbers_the_statements_for_the_judge(self, stub_ai):
        calls = stub_ai('[{"statement": "a", "supported": true}]')
        faithfulness.verify_statements(["first", "second"], "CTX")
        prompt = calls[0]["prompt"]
        assert "1. first" in prompt and "2. second" in prompt
        assert "CTX" in prompt

    def test_missing_supported_key_counts_as_unsupported(self, stub_ai):
        """A judge that omits the verdict must not be read as approval."""
        stub_ai('[{"statement": "a", "reason": "unclear"}]')
        got = faithfulness.verify_statements(["a"], "ctx")
        assert got[0]["supported"] is False

    def test_non_object_entries_are_dropped(self, stub_ai):
        stub_ai('["just a string", {"statement": "a", "supported": true}]')
        got = faithfulness.verify_statements(["a"], "ctx")
        assert len(got) == 1

    def test_unparseable_reply_is_none(self, stub_ai):
        stub_ai("nope")
        assert faithfulness.verify_statements(["a"], "ctx") is None


class TestScoreSample:
    def test_score_is_supported_over_total(self, stub_ai):
        stub_ai('["a", "b", "c", "d"]',
                '[{"statement": "a", "supported": true},'
                ' {"statement": "b", "supported": true},'
                ' {"statement": "c", "supported": true},'
                ' {"statement": "d", "supported": false}]')
        got = faithfulness.score_sample("answer", "context")
        assert got["score"] == pytest.approx(0.75)
        assert (got["supported"], got["statements"]) == (3, 4)
        assert got["unsupported"] == ["d"]

    def test_every_claim_supported_is_one(self, stub_ai):
        stub_ai('["a"]', '[{"statement": "a", "supported": true}]')
        assert faithfulness.score_sample("answer", "ctx")["score"] == 1.0

    def test_every_claim_unsupported_is_zero(self, stub_ai):
        stub_ai('["a"]', '[{"statement": "a", "supported": false}]')
        assert faithfulness.score_sample("answer", "ctx")["score"] == 0.0

    def test_failed_extraction_is_none_not_zero(self, stub_ai):
        """'Could not measure' must never be reported as 'scored 0.0'."""
        stub_ai("garbage")
        assert faithfulness.score_sample("answer", "ctx") is None

    def test_failed_verification_is_none_not_zero(self, stub_ai):
        stub_ai('["a"]', "garbage")
        assert faithfulness.score_sample("answer", "ctx") is None

    def test_truncated_judge_reply_does_not_inflate_the_score(self, stub_ai):
        """The denominator is statements extracted, never verdicts returned.

        The judge call is capped at max_tokens, so a long answer can come back
        judged only in part. Dividing by the verdicts would score 3/3 = 1.0 for
        a reply that actually left 7 of 10 claims unexamined — the metric would
        read best exactly when the judge coped worst.
        """
        stub_ai('["a", "b", "c", "d", "e"]',
                '[{"statement": "a", "supported": true},'
                ' {"statement": "b", "supported": true}]')
        assert faithfulness.score_sample("answer", "ctx") is None

    def test_spurious_extra_verdicts_are_ignored(self, stub_ai):
        """A judge that invents verdicts must not dilute or pad the denominator."""
        stub_ai('["a", "b"]',
                '[{"statement": "a", "supported": true},'
                ' {"statement": "b", "supported": false},'
                ' {"statement": "c", "supported": true}]')
        got = faithfulness.score_sample("answer", "ctx")
        assert (got["supported"], got["statements"]) == (1, 2)
        assert got["score"] == pytest.approx(0.5)


class TestGuardrailVerdict:
    """The eval must report what `boost explain` would actually do with a reply."""

    def test_grounded_answer_would_be_shown(self, sandbox):
        source = "# Skill\n\nRun `boost install --local` to add a skill.\n"
        got = faithfulness.guardrail_verdict(
            "Run `boost install --local` to add a skill.", source)
        assert got["would_be_shown"] is True
        assert got["guardrail_score"] >= got["guardrail_threshold"]

    def test_fabricated_specifics_would_fall_back(self, sandbox):
        """Invented flags/commands are exactly what the runtime guard catches."""
        source = "# Skill\n\nA plain skill with no commands.\n"
        got = faithfulness.guardrail_verdict(
            "Pass `--force` to `boost frobnicate` and edit `~/.boost/nope.toml`.",
            source)
        assert got["would_be_shown"] is False

    def test_reported_alongside_the_judged_score(self, stub_ai, monkeypatch):
        """run() must attach the guard verdict to every explain sample."""
        from boost_cli.core import ai
        monkeypatch.setattr(ai, "available", lambda: True)
        monkeypatch.setattr(faithfulness, "generate_explain",
                            lambda name: ("an answer", "a context"))
        monkeypatch.setattr(faithfulness, "generate_distill", lambda names: None)
        monkeypatch.setattr(faithfulness, "score_sample",
                            lambda a, c: {"score": 1.0, "statements": 1,
                                          "supported": 1, "unsupported": []})
        got = faithfulness.run()
        assert got["status"] == "ok"
        assert "would_fall_back" in got
        for sample in got["samples"]:
            assert "guardrail_score" in sample
            assert "would_be_shown" in sample


class TestRunDegradation:
    """`run()` reads the live catalog, so these use the throwaway-$HOME fixture."""

    def test_skips_naming_the_missing_credential(self, sandbox, monkeypatch):
        """AI is switched on but unreachable — say which credential is missing."""
        from boost_cli.core import ai
        monkeypatch.setattr(ai, "enabled", lambda: True)
        monkeypatch.setattr(ai, "available", lambda: False)
        got = faithfulness.run()
        assert got["status"] == "skipped"
        assert "ANTHROPIC_API_KEY" in got["reason"]
        assert "mean" not in got, "a skip must not report a score"

    def test_skips_naming_boost_no_ai_when_that_is_the_cause(self, sandbox,
                                                             monkeypatch):
        """The sandbox fixture sets BOOST_NO_AI=1, which is the live case here.

        Reporting "no CLI on PATH" when the CLI is present and boost was merely
        told not to use it sends the reader hunting for the wrong problem.
        """
        from boost_cli.core import ai
        monkeypatch.setattr(ai, "available", lambda: False)
        got = faithfulness.run()
        assert got["status"] == "skipped"
        assert "BOOST_NO_AI" in got["reason"]
        assert "on PATH" not in got["reason"]

    def test_skips_when_generation_fails_for_every_target(self, sandbox,
                                                          monkeypatch):
        """The bridge is present but broken — still a skip, never a failure."""
        from boost_cli.core import ai
        monkeypatch.setattr(ai, "available", lambda: True)
        monkeypatch.setattr(ai, "ask", lambda *a, **k: None)
        monkeypatch.setattr(ai, "ask_author", lambda *a, **k: None)
        got = faithfulness.run()
        assert got["status"] == "skipped"
        assert "generation failed" in got["reason"]
        assert "mean" not in got

    def test_ragas_scorer_skips_cleanly_when_the_package_is_absent(
            self, sandbox, monkeypatch):
        from boost_cli.core import ai
        monkeypatch.setattr(ai, "available", lambda: True)
        got = faithfulness.run(scorer="ragas")
        # ragas is an opt-in [eval] extra: absent in CI, possibly present in a
        # developer venv. Either way the contract is the same — never a crash,
        # and a skip must carry a reason rather than a score.
        assert got["status"] in ("skipped", "ok")
        if got["status"] == "skipped":
            assert got["reason"]


class TestReport:
    def test_prints_the_skip_reason(self, capsys):
        faithfulness.report({"status": "skipped", "scorer": "builtin",
                             "reason": "no judge key"})
        assert "SKIPPED — no judge key" in capsys.readouterr().out

    def test_prints_scores_and_unsupported_claims(self, capsys):
        faithfulness.report({
            "status": "ok", "scorer": "builtin", "mean": 0.75, "n": 1,
            "samples": [{"target": "explain:x", "score": 0.75, "supported": 3,
                         "statements": 4, "unsupported": ["invented claim"]}],
        })
        out = capsys.readouterr().out
        assert "explain:x" in out and "3/4 supported" in out
        assert "unsupported (explain:x): invented claim" in out
