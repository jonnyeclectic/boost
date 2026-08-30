# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: the Tier 3 tool-call eval scores BOTH directions, with intervals.

Tiers 1 and 2 grade what boost returns once it is asked. Nothing graded whether
an agent asks — the step everything downstream depends on. A gate flooring
recall@k at 0.78 reports nothing when retrieval was never invoked.

The design constraint that decides whether the tier is worth having is that it
must floor both directions. Scoring call rate alone rewards making the tool
descriptions maximally assertive — the exact capture `core/mcp.py` is written
to avoid — and boost already found this hole one tier down: flooring recall
without hit@1 passed a ranker that found the answer every time and never
ranked it first.

The live half needs a host and spends tokens. Everything below is the
deterministic half — the set's shape, the interval maths, and the verdict — so
the part that decides pass/fail is testable without either.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import ClassVar

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "eval_tools.py"
PROMPTS = ROOT / "tests" / "eval" / "tool_calls.jsonl"

pytestmark = pytest.mark.skipif(
    not SCRIPT.exists() or not PROMPTS.exists(),
    reason="eval script/prompt set not reachable (e.g. mutation sandbox)")


def load():
    """Import scripts/eval_tools.py by path, the way this repo tests scripts/."""
    spec = importlib.util.spec_from_file_location("eval_tools_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


MOD = load()


def _row(rid, expect):
    return {"id": rid, "expect": expect, "prompt": "p"}


class TestThePromptSetHasBothHalves:
    """A set with one half is the single-number failure this tier refuses."""

    def test_the_shipped_set_carries_both(self):
        rows = MOD.load_set(PROMPTS)
        call, no_call = MOD.halves(rows)
        assert call and no_call

    def test_the_halves_are_balanced(self):
        # Not a law of nature, but an unbalanced set makes the two rates
        # incomparable at a glance, and the whole point is reading them
        # together. Adjust deliberately if it ever needs to change.
        call, no_call = MOD.halves(MOD.load_set(PROMPTS))
        assert len(call) == len(no_call)

    def test_a_one_sided_set_is_refused(self):
        with pytest.raises(SystemExit) as exc:
            MOD.halves([_row("a", "call"), _row("b", "call")])
        assert "BOTH halves" in str(exc.value)

    def test_no_prompt_names_the_tool(self):
        # Naming the tool tests obedience, not judgement: it would score a
        # surface that never has to persuade anyone.
        for r in MOD.load_set(PROMPTS):
            low = r["prompt"].lower()
            assert "boost" not in low, r["id"]
            for tool in MOD.BOOST_TOOLS:
                assert tool not in low, (r["id"], tool)

    def test_every_row_names_the_trigger_it_exercises(self):
        # A failing row should name the sentence to argue with, not just a
        # number — the shipped triggers are the thing under test.
        for r in MOD.load_set(PROMPTS):
            assert r.get("signals"), r["id"]

    def test_duplicate_ids_are_refused(self, tmp_path):
        p = tmp_path / "dupe.jsonl"
        p.write_text("\n".join(json.dumps(o) for o in (
            _row("same", "call"), _row("same", "no-call"))), encoding="utf-8")
        with pytest.raises(SystemExit) as exc:
            MOD.load_set(p)
        assert "duplicate" in str(exc.value)

    def test_an_unusable_expect_is_refused(self, tmp_path):
        p = tmp_path / "bad.jsonl"
        p.write_text(json.dumps(_row("x", "maybe")), encoding="utf-8")
        with pytest.raises(SystemExit) as exc:
            MOD.load_set(p)
        assert "expect" in str(exc.value)

    def test_comments_and_blanks_are_skipped(self, tmp_path):
        p = tmp_path / "c.jsonl"
        p.write_text("# a note\n\n%s\n" % json.dumps(_row("x", "call")),
                     encoding="utf-8")
        assert [r["id"] for r in MOD.load_set(p)] == ["x"]


class TestTheIntervalRefusesToClaimCertainty:
    """Small N is the design, so the maths has to survive it."""

    def test_three_for_three_is_not_certainty(self):
        # The textbook normal interval gives [1.0, 1.0] here and would let a
        # wording regression hide behind one lucky run.
        lo, hi = MOD.wilson(3, 3)
        assert lo < 0.9
        assert hi == 1.0

    def test_zero_for_three_is_not_impossibility(self):
        lo, hi = MOD.wilson(0, 3)
        assert lo == 0.0
        assert hi > 0.1

    def test_no_evidence_is_the_widest_interval(self):
        # Not a rate of zero: a host that could not be reached must not read
        # as a host that declined to call.
        assert MOD.wilson(0, 0) == (0.0, 1.0)

    def test_more_runs_narrow_it(self):
        narrow = MOD.wilson(30, 30)
        wide = MOD.wilson(3, 3)
        assert narrow[0] > wide[0]

    def test_the_interval_stays_inside_zero_and_one(self):
        for k, n in ((0, 1), (1, 1), (0, 2), (2, 2), (5, 10), (99, 100)):
            lo, hi = MOD.wilson(k, n)
            assert 0.0 <= lo <= hi <= 1.0, (k, n, lo, hi)

    def test_the_point_estimate_sits_inside_its_interval(self):
        for k, n in ((1, 3), (2, 3), (5, 10), (7, 9)):
            lo, hi = MOD.wilson(k, n)
            assert lo <= k / n <= hi, (k, n)


class TestBothDirectionsAreScored:
    ROWS: ClassVar[list[dict]] = [
        _row("c1", "call"), _row("c2", "call"),
        _row("n1", "no-call"), _row("n2", "no-call")]

    def test_a_perfect_host_passes(self):
        obs = {"c1": [True], "c2": [True], "n1": [False], "n2": [False]}
        m = MOD.score_host(self.ROWS, obs)
        assert m["call_rate"]["rate"] == 1.0
        assert m["false_call_rate"]["rate"] == 0.0

    def test_a_host_that_never_calls_fails_the_floor(self):
        obs = {"c1": [False], "c2": [False], "n1": [False], "n2": [False]}
        reasons = MOD.verdict(MOD.score_host(self.ROWS, obs), 0.60, 0.20)
        assert any("call rate" in r for r in reasons)

    def test_a_host_that_always_calls_fails_the_CEILING(self):
        # The whole reason this tier has two halves. Call rate is a perfect
        # 1.00 here — scoring that alone would report a triumph.
        obs = {"c1": [True], "c2": [True], "n1": [True], "n2": [True]}
        m = MOD.score_host(self.ROWS, obs)
        assert m["call_rate"]["rate"] == 1.0
        reasons = MOD.verdict(m, 0.60, 0.20)
        assert reasons, "an always-calling host passed"
        assert any("false-call" in r for r in reasons)

    def test_the_two_rates_are_computed_over_different_rows(self):
        obs = {"c1": [True], "c2": [True], "n1": [True], "n2": [True]}
        m = MOD.score_host(self.ROWS, obs)
        assert m["call_rate"]["n"] == 2
        assert m["false_call_rate"]["n"] == 2

    def test_an_unreached_row_is_skipped_not_failed(self):
        obs = {"c1": [True], "n1": [False]}
        m = MOD.score_host(self.ROWS, obs)
        assert sorted(m["skipped"]) == ["c2", "n2"]
        assert m["call_rate"]["n"] == 1

    def test_runs_accumulate_into_one_rate(self):
        obs = {"c1": [True, False, True], "c2": [True, True, True],
               "n1": [False] * 3, "n2": [False] * 3}
        m = MOD.score_host(self.ROWS, obs)
        assert (m["call_rate"]["k"], m["call_rate"]["n"]) == (5, 6)


class TestTheVerdictJudgesTheInterval:
    ROWS: ClassVar[list[dict]] = [_row("c1", "call"), _row("n1", "no-call")]

    def test_a_lucky_single_run_does_not_clear_the_floor(self):
        # 1/1 is a point estimate of 1.00 and a lower bound of ~0.21. Gating on
        # the point estimate would make the tier itself flaky.
        obs = {"c1": [True], "n1": [False]}
        assert MOD.verdict(MOD.score_host(self.ROWS, obs), 0.60, 0.20)

    def test_enough_runs_do_clear_it(self):
        obs = {"c1": [True] * 30, "n1": [False] * 30}
        assert MOD.verdict(MOD.score_host(self.ROWS, obs), 0.60, 0.20) == []

    def test_no_observations_is_reported_rather_than_passed(self):
        # Silence must never read as success.
        assert MOD.verdict(MOD.score_host(self.ROWS, {}), 0.60, 0.20)


class TestTheProbeReadsTheHostNotTheProse:
    def test_a_tool_call_counts(self):
        assert MOD.called_boost('{"type":"tool_use","name":"boost_search"}')

    def test_a_host_prefixed_name_counts(self):
        # Hosts namespace MCP tools differently; matching the bare suffix keeps
        # one list correct across all of them.
        for name in ("mcp__boost__boost_search", "mcp_boost_boost_search"):
            assert MOD.called_boost('{"name":"%s"}' % name), name

    def test_narrating_a_check_without_making_one_is_a_miss(self):
        # An agent that says it will check and does not is a miss; the event
        # stream is the record, not the model's account of itself.
        assert not MOD.called_boost(
            '{"type":"text","text":"Let me check the skill registry first."}')

    def test_installing_is_not_consulting(self):
        # `boost_install` is downstream of a decision already made. Counting it
        # would let a run that installed without looking score as a check.
        assert "boost_install" in MOD.BOOST_TOOLS
        assert "boost_install" not in MOD.CONSULT_TOOLS
        assert not MOD.called_boost('{"name":"boost_install"}')

    def test_an_empty_stream_is_a_miss(self):
        assert not MOD.called_boost("")


class TestItStaysOutOfTheRequiredGate:
    def test_check_does_not_run_it(self):
        # It drives a real host and spends real tokens; a required gate that
        # does that is a build nobody can run offline.
        mk = (ROOT / "Makefile").read_text(encoding="utf-8")
        check = [ln for ln in mk.splitlines() if ln.startswith("check:")]
        assert check, "no check target"
        assert "eval-tools" not in check[0]

    def test_it_has_its_own_opt_in_target(self):
        assert "eval-tools:" in (ROOT / "Makefile").read_text(encoding="utf-8")


class TestTheRateIsNeverReadWithoutItsContext:
    """A rule is part of what is being scored, so the report has to say so.

    An installed boost RULE is standing instructions in the agent's own context
    file, and `boost-first` tells the agent in as many words to call these
    tools. A rate measured with it installed is a rate for rule + descriptions.
    Attributing that to wording alone is the mistake the context line exists to
    prevent — printed, never subtracted, because guessing at its share would be
    the same unfalsifiable move the tier was built to retire.
    """

    def test_it_names_the_installed_rules(self, capsys, monkeypatch):
        from boost_cli.core import lockfile
        monkeypatch.setattr(lockfile, "all_installed",
                            lambda: {"skill": {}, "rule": {"boost-first": {}},
                                     "workflow": {}})
        MOD._print_context()
        out = capsys.readouterr().out
        assert "boost-first" in out
        assert "not descriptions alone" in out

    def test_no_rules_is_reported_as_no_rules(self, capsys, monkeypatch):
        from boost_cli.core import lockfile
        monkeypatch.setattr(lockfile, "all_installed",
                            lambda: {"skill": {}, "rule": {}, "workflow": {}})
        MOD._print_context()
        out = capsys.readouterr().out
        assert "0 rule(s)" in out
        # The caveat belongs only where it applies.
        assert "not descriptions alone" not in out

    def test_a_context_note_never_fails_the_run(self, capsys, monkeypatch):
        # It is a note. If the lock file cannot be read, the eval still runs.
        from boost_cli.core import lockfile

        def boom():
            raise OSError("no lock file")

        monkeypatch.setattr(lockfile, "all_installed", boom)
        MOD._print_context()
        assert "could not read" in capsys.readouterr().out
