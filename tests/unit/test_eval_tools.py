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

    def test_the_edges_are_exact(self):
        # In real arithmetic the bound IS 0 at k=0 and 1 at k=n. Floating
        # point misses by ~1e-17 at some N (11, 22, 88, ...), and a lower bound
        # of 2.8e-17 compared with `>` against a ceiling of 0 convicted a
        # host that had made no false call at all.
        for n in range(1, 3000):
            assert MOD.wilson(0, n)[0] == 0.0, n
            assert MOD.wilson(n, n)[1] == 1.0, n

    def test_the_point_estimate_sits_inside_its_interval(self):
        for k, n in ((1, 3), (2, 3), (5, 10), (7, 9)):
            lo, hi = MOD.wilson(k, n)
            assert lo <= k / n <= hi, (k, n)


class TestBothDirectionsAreScored:
    ROWS: ClassVar[list[dict]] = [
        _row("c1", "call"), _row("c2", "call"),
        _row("n1", "no-call"), _row("n2", "no-call")]

    def test_a_perfect_host_passes(self):
        """And passes `verdict()`, which this test used never to call.

        It asserted the two rates and stopped, so it went on passing while
        `verdict()` returned TWO failures for this very observation — the
        ceiling was unreachable at n=2, and the test named "a perfect host
        passes" would have failed if it had asserted the thing its name claims.
        Enough runs to make both bounds reachable, then assert the verdict.
        """
        runs = MOD.min_n_for_ceiling(0.25)          # per half, across 2 rows
        obs = {"c1": [True] * runs, "c2": [True] * runs,
               "n1": [False] * runs, "n2": [False] * runs}
        m = MOD.score_host(self.ROWS, obs)
        assert m["call_rate"]["rate"] == 1.0
        assert m["false_call_rate"]["rate"] == 0.0
        assert MOD.verdict(m, 0.60, 0.25) == []
        assert MOD.unjudgeable(m, 0.25) is None

    def test_a_host_that_never_calls_fails_the_floor(self):
        obs = {"c1": [False], "c2": [False], "n1": [False], "n2": [False]}
        reasons = MOD.verdict(MOD.score_host(self.ROWS, obs), 0.60, 0.20)
        assert any("call rate" in r for r in reasons)

    def test_a_host_that_always_calls_fails_the_CEILING(self):
        # The whole reason this tier has two halves. Call rate is a perfect
        # 1.00 here — scoring that alone would report a triumph.
        #
        # One run per row, on purpose. n=2 is too few to PASS the ceiling, but
        # 2/2 puts the Wilson LOWER bound at 0.34, over it already: a sample
        # too small to clear a host can still convict one. This test was once
        # moved to n=16 so that reading such a sample as undecided could pass.
        obs = {"c1": [True], "c2": [True], "n1": [True], "n2": [True]}
        m = MOD.score_host(self.ROWS, obs)
        assert m["call_rate"]["rate"] == 1.0
        reasons = MOD.verdict(m, 0.60, 0.20)
        assert reasons, "an always-calling host passed"
        assert any("false-call" in r for r in reasons)
        assert MOD.unjudgeable(m, 0.20) is None
        assert MOD.exit_code(reasons, MOD.unjudgeable(m, 0.20)) == 1

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


class TestTheCeilingMustBeReachable:
    """A bound judged against an upper bound needs enough N to be clearable.

    At k=0 the Wilson upper bound is z^2/(n+z^2), a function of N alone, so
    below a certain N the ceiling reports FAIL for every possible host. At the
    old `--runs 1` default that was the shipped state: 8 no-call observations,
    best achievable bound 0.3244, ceiling 0.20 — an unsatisfiable gate that
    told its reader the tier was broken.
    """

    ROWS: ClassVar[list[dict]] = [_row("c1", "call"), _row("n1", "no-call")]

    @pytest.mark.parametrize("ceiling,need", [(0.20, 16), (0.25, 12),
                                              (0.10, 35), (0.50, 4)])
    def test_the_minimum_n_is_the_wilson_algebra(self, ceiling, need):
        assert MOD.min_n_for_ceiling(ceiling) == need
        # and it is exactly the boundary, from both sides
        assert MOD.wilson(0, need)[1] <= ceiling
        assert MOD.wilson(0, need - 1)[1] > ceiling

    # 30 happens to give a lower bound of exactly 0.0; 11, 22 and 88 are
    # where k=0 used to come out at ~1e-17 and read as a conviction.
    @pytest.mark.parametrize("n", [11, 22, 30, 88])
    def test_a_ceiling_of_zero_is_never_judgeable(self, n):
        assert MOD.min_n_for_ceiling(0.0) == 0
        m = MOD.score_host(self.ROWS, {"c1": [True] * n, "n1": [False] * n})
        assert "any sample size" in (MOD.unjudgeable(m, 0.0) or "")
        assert not [r for r in MOD.verdict(m, 0.60, 0.0) if "false-call" in r]

    def test_too_small_a_sample_is_inconclusive_not_a_failure(self):
        # The defect, inverted: a flawless host used to be told it FAILED.
        obs = {"c1": [True] * 8, "n1": [False] * 8}
        m = MOD.score_host(self.ROWS, obs)
        assert not [r for r in MOD.verdict(m, 0.60, 0.20) if "false-call" in r]
        note = MOD.unjudgeable(m, 0.20)
        assert note and "at least 16" in note and "--runs" in note

    def test_a_reachable_sample_still_judges_the_ceiling(self):
        # The fix must not turn the ceiling off: a host that always calls
        # still fails it once the sample is big enough to say so.
        obs = {"c1": [True] * 16, "n1": [True] * 16}
        m = MOD.score_host(self.ROWS, obs)
        assert MOD.unjudgeable(m, 0.20) is None
        assert any("false-call" in r for r in MOD.verdict(m, 0.60, 0.20))

    def test_a_sample_too_small_to_pass_can_still_prove_a_failure(self):
        # Below the minimum a PASS is out of reach, but a FAIL is not: 8/8
        # false calls put the Wilson LOWER bound at 0.68, over the ceiling
        # whatever more runs would show. Reading that as "too few runs" hid
        # the capture this half exists to catch, at the default N it had.
        m = MOD.score_host(self.ROWS, {"c1": [True] * 8, "n1": [True] * 8})
        assert MOD.unjudgeable(m, 0.25) is None
        assert any("false-call" in r for r in MOD.verdict(m, 0.60, 0.25))

    def test_a_zero_ceiling_still_convicts_a_host_that_calls(self):
        # No sample can clear a ceiling of 0, but one can exceed it.
        m = MOD.score_host(self.ROWS, {"c1": [True] * 30, "n1": [True] * 24})
        assert MOD.unjudgeable(m, 0.0) is None
        assert any("false-call" in r for r in MOD.verdict(m, 0.60, 0.0))

    def test_a_ceiling_of_one_is_judgeable_from_the_first_observation(self):
        # 1.0 is no ceiling rather than an unreachable one: every bound sits
        # at or under it, so even an always-calling host clears it.
        assert MOD.min_n_for_ceiling(1.0) == 1
        m = MOD.score_host(self.ROWS, {"c1": [True] * 30, "n1": [True]})
        assert MOD.unjudgeable(m, 1.0) is None
        assert MOD.verdict(m, 0.60, 1.0) == []

    def test_an_empty_no_call_half_is_inconclusive_not_a_pass(self):
        # Every no-call run timed out: nothing was observed, so nothing was
        # cleared. It used to fall through as a pass (exit 0), while the call
        # half has always reported the same silence as a failure.
        m = MOD.score_host(self.ROWS, {"c1": [True] * 30})
        assert MOD.verdict(m, 0.60, 0.25) == []
        note = MOD.unjudgeable(m, 0.25)
        assert note and "no should-NOT-call observations" in note
        assert MOD.exit_code([], note) == 2

    def test_the_note_counts_prompts_per_run_not_observations(self):
        # The note tells its reader how far to raise --runs, so the per-run
        # figure is the half's PROMPT count. It printed the observation count,
        # which is only the same number at one run. One prompt, eight runs, a
        # ceiling that needs 16: three different numbers, each in its place.
        m = MOD.score_host(self.ROWS, {"c1": [True] * 8, "n1": [False] * 8})
        note = MOD.unjudgeable(m, 0.20) or ""
        assert "needs at least 16 observations and this run has 8" in note
        assert "the no-call half is 1 prompt(s) per run" in note

    def test_the_minimum_is_where_wilson_says_at_every_ceiling(self):
        """Property: the answer is the smallest N that `verdict` would clear.

        The closed form is exact in real arithmetic and an ulp either side of
        it in floats, where `verdict` reads `wilson()` with a strict `>`. Over
        the exact k=0 boundaries c = z^2/(n+z^2) the two disagreed thousands
        of times; round ceilings never did, so both grids are here.
        """
        z2 = 1.96 * 1.96
        grid = ([i / 1000 for i in range(1, 1000)]
                + [z2 / (n + z2) for n in range(1, 2000)])
        wrong = []
        for c in grid:
            need = MOD.min_n_for_ceiling(c)
            clears = MOD.wilson(0, need)[1] <= c
            smallest = need == 1 or MOD.wilson(0, need - 1)[1] > c
            if not (clears and smallest):
                wrong.append((c, need))
        assert not wrong, "%d wrong, e.g. %s" % (len(wrong), wrong[:3])

    @pytest.mark.parametrize("n", [3, 13])
    def test_the_minimum_agrees_with_verdict_at_an_exact_boundary(self, n):
        # The two the review found. At n=3 the closed form answered 4 though
        # 0/3 already clears; at n=13 it answered 13 though 0/13 sits 2.8e-17
        # over and fails `verdict`'s strict `>` — a flawless host told it
        # failed by a sample the gate had just called big enough.
        z2 = 1.96 * 1.96
        c = z2 / (n + z2)
        need = MOD.min_n_for_ceiling(c)

        def flawless(obs: int) -> dict:
            return MOD.score_host(self.ROWS, {"c1": [True] * 60,
                                              "n1": [False] * obs})

        assert MOD.unjudgeable(flawless(need), c) is None
        assert MOD.verdict(flawless(need), 0.60, c) == []
        assert MOD.unjudgeable(flawless(need - 1), c) is not None
        assert MOD.wilson(0, need - 1)[1] > c

    def test_the_shipped_defaults_can_actually_pass(self):
        """The parity that was missing: the two defaults against the algebra.

        `--runs` and `--ceiling-false-call` were set independently and nothing
        checked that the first produces a sample the second can clear. Read
        off the shipped parser, never restated here — a test that restates a
        default cannot catch it drifting.
        """
        defaults = _defaults()
        rows = MOD.load_set(MOD.DEFAULT_SET)
        _call, no_call = MOD.halves(rows)
        n = len(no_call) * defaults["runs"]
        need = MOD.min_n_for_ceiling(defaults["ceiling_false_call"])
        assert n >= need, (
            "the default --runs %d gives %d no-call observations, but the "
            "default ceiling %.2f needs %d — a flawless host would be "
            "reported as failing"
            % (defaults["runs"], n, defaults["ceiling_false_call"], need))

    def test_the_runs_help_names_the_run_count_that_cannot_pass(self):
        # The help said anything under the default 3 runs was unreachable, but
        # 2 runs reach the default ceiling; only 1 does not. Pin the sentence
        # to the algebra it states, against the shipped set.
        runs = next(a for a in MOD.build_parser()._actions if a.dest == "runs")
        need = MOD.min_n_for_ceiling(_defaults()["ceiling_false_call"])
        _call, no_call = MOD.halves(MOD.load_set(MOD.DEFAULT_SET))
        assert len(no_call) * 1 < need <= len(no_call) * 2
        assert "at 1 run" in runs.help
        assert "n>=%d" % need in runs.help
        assert "%d no-call prompts" % len(no_call) in runs.help

    def test_the_ceiling_tolerates_one_slip_at_the_default_sample(self):
        # Stated tolerance, not an accident: the floor absorbs four misses in
        # 24, so a ceiling that fails on the first false call is not the same
        # kind of measurement.
        rows = MOD.load_set(MOD.DEFAULT_SET)
        call, no_call = MOD.halves(rows)
        defaults = _defaults()
        runs, ceiling = defaults["runs"], defaults["ceiling_false_call"]
        obs = {r["id"]: [True] * runs for r in call}
        obs.update({r["id"]: [False] * runs for r in no_call})
        obs[no_call[0]["id"]] = [True] + [False] * (runs - 1)
        assert MOD.verdict(MOD.score_host(rows, obs), 0.60, ceiling) == []
        obs[no_call[1]["id"]] = [True] + [False] * (runs - 1)
        assert MOD.verdict(MOD.score_host(rows, obs), 0.60, ceiling)


class TestTheExitCodeSaysWhichKind:
    def test_a_clean_run_is_zero(self):
        assert MOD.exit_code([], None) == 0

    def test_an_undecided_ceiling_is_two(self):
        assert MOD.exit_code([], "too few observations") == 2

    def test_a_failure_outranks_an_undecided_ceiling(self):
        # A floor miss is a real answer whatever the other half could not say.
        assert MOD.exit_code(["call rate under floor"], "too few") == 1


class TestMainReportsWhatItJudged:
    """`main()` end to end, against a fake host.

    Every other class tests a scoring function; nothing tested that main()
    returns their answer, prints it, or puts it in --json — so replacing
    `exit_code()` with the old `1 if reasons else 0` passed the whole file.
    The host is faked at the three seams main() reaches it through: a prompt
    goes in, the prompt comes back as the "event stream", and the probe
    answers from which half that prompt belongs to.
    """

    @pytest.fixture
    def run(self, monkeypatch, capsys):
        from boost_cli.core import lockfile
        monkeypatch.delenv("BOOST_NO_AI", raising=False)
        monkeypatch.setattr(lockfile, "all_installed",
                            lambda: {"skill": {}, "rule": {"boost-first": {}},
                                     "workflow": {}})
        monkeypatch.setattr(MOD, "claude_available", lambda: True)
        rows = MOD.load_set(MOD.DEFAULT_SET)
        call = {r["prompt"] for r in rows if r["expect"] == "call"}

        # A real stream opens with the init event naming the tool surface, so
        # the fake's does too; the prompt rides on the first line so the probe
        # can answer from it.
        init = json.dumps({"type": "system", "subtype": "init",
                           "tools": ["a", "b", "c"], "mcp_servers": [{}]})

        def go(*argv: str, host: str = "perfect") -> tuple[int, str, str]:
            # "timeout": every should-NOT-call prompt comes back empty.
            monkeypatch.setattr(
                MOD, "run_claude", lambda prompt, timeout, cfg=None:
                None if host == "timeout" and prompt not in call
                else prompt + "\n" + init)
            monkeypatch.setattr(
                MOD, "called_boost",
                lambda events: host == "always"
                or events.split("\n", 1)[0] in call)
            rc = MOD.main(list(argv))
            cap = capsys.readouterr()
            return rc, cap.out, cap.err

        return go

    def test_a_perfect_host_at_the_defaults_exits_zero(self, run):
        rc, out, _ = run()
        assert rc == 0
        assert "FAIL:" not in out and "INCONCLUSIVE:" not in out

    def test_a_sample_too_small_to_pass_exits_two_and_says_why(self, run):
        rc, out, _ = run("--runs", "1")
        assert rc == 2
        assert ("INCONCLUSIVE: false-call ceiling 0.25 needs at least 12 "
                "observations and this run has 8") in out
        assert "FAIL:" not in out

    def test_the_note_names_the_prompts_per_run(self, run):
        # 8 no-call prompts x 2 runs = 16 observations, against 35 needed.
        rc, out, _ = run("--runs", "2", "--ceiling-false-call", "0.10")
        assert rc == 2
        assert "needs at least 35 observations and this run has 16" in out
        assert "the no-call half is 8 prompt(s) per run" in out

    @pytest.mark.parametrize("argv", [
        ("--runs", "1"),
        ("--runs", "3", "--ceiling-false-call", "0.10"),
        ("--ceiling-false-call", "0"),
    ])
    def test_a_host_that_always_calls_fails_at_any_n(self, run, argv):
        # Each of these is a sample that could never PASS the ceiling, and
        # each proves the host over it: the lower bound is 0.68 at 8/8 and
        # 0.86 at 24/24. A red, exit 1 — never "raise --runs".
        rc, out, _ = run(*argv, host="always")
        assert rc == 1
        assert "FAIL: false-call rate 1.00" in out
        assert "INCONCLUSIVE:" not in out

    def test_every_no_call_run_timing_out_exits_two(self, run):
        rc, out, _ = run(host="timeout")
        assert rc == 2
        assert "INCONCLUSIVE: no should-NOT-call observations" in out

    def test_json_carries_the_undecided_state(self, run):
        # The whole of stdout is the document: the context notes go to
        # stderr under --json, where they used to open stdout and make it
        # unparseable before the verdict was ever read.
        rc, out, err = run("--runs", "1", "--json")
        doc = json.loads(out)
        assert rc == 2
        assert doc["failures"] == []
        assert "needs at least 12" in doc["inconclusive"]
        assert "context:" in err

    def test_json_carries_a_proven_failure(self, run):
        rc, out, _ = run("--runs", "1", "--json", host="always")
        doc = json.loads(out)
        assert rc == 1
        assert any("false-call" in r for r in doc["failures"])
        assert doc["inconclusive"] is None

    def test_json_keeps_the_strict_mcp_note_off_stdout(self, run):
        # --strict-mcp-config adds a third context line; under --json it goes
        # where the other two go.
        _rc, out, err = run("--runs", "1", "--json", "--strict-mcp-config")
        assert json.loads(out)["inconclusive"]
        assert "--strict-mcp-config on" in err

    def test_without_json_the_context_stays_on_stdout(self, run):
        _rc, out, err = run()
        assert "context:" in out
        assert "context:" not in err

    def test_json_sends_every_context_line_to_stderr(self, run):
        # All three lines a real run prints: the rules count, the rules
        # caveat, and the tool surface from the init event.
        _rc, out, err = run("--json")
        json.loads(out)
        assert "1 rule(s) installed" in err
        assert "these are standing instructions" in err
        assert "host offered 3 tool(s) across 1 MCP server(s)" in err
        assert "host offered" not in out

    def test_json_sends_a_lock_file_error_to_stderr(self, run, monkeypatch):
        from boost_cli.core import lockfile

        def broken():
            raise OSError("unreadable")
        monkeypatch.setattr(lockfile, "all_installed", broken)
        _rc, out, err = run("--json")
        json.loads(out)
        assert "could not read the lock file" in err

    def test_a_perfect_host_at_a_ceiling_of_zero_is_never_convicted(self, run):
        # 11 runs x 8 no-call prompts = 88, where the k=0 lower bound used to
        # come out at ~3e-18 and a flawless host was told it FAILED.
        rc, out, _ = run("--runs", "11", "--ceiling-false-call", "0")
        assert rc == 2
        assert "FAIL:" not in out
        assert "cannot be cleared at any sample size" in out


def _defaults() -> dict:
    """Every shipped default, from the parser itself."""
    return vars(MOD.build_parser().parse_args([]))


def _assistant_call(name: str) -> str:
    """One `assistant` event carrying one `tool_use` block — a real call.

    These fixtures used to be bare fragments like `{"name":"boost_search"}`,
    which no host emits. That shape is why this class passed against a probe
    that substring-scanned the raw stream and therefore answered True on every
    run: the fixtures had no `system`/`init` event, so the tool *list* the real
    host sends was never in the input under test. A fixture the author invented
    cannot catch the author's wrong model of the input, and it did not.
    `tests/unit/test_eval_tools_probe.py` now drives a captured real stream.
    """
    return json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": name, "input": {}}]}})


class TestTheProbeReadsTheHostNotTheProse:
    def test_a_tool_call_counts(self):
        assert MOD.called_boost(_assistant_call("boost_search"))

    def test_a_host_prefixed_name_counts(self):
        # Hosts namespace MCP tools differently; matching the bare suffix keeps
        # one list correct across all of them.
        for name in ("mcp__boost__boost_search", "mcp_boost_boost_search",
                     "boost/boost_search"):
            assert MOD.called_boost(_assistant_call(name)), name

    def test_being_offered_a_tool_is_not_calling_it(self):
        # The bug this class missed: the host's init event lists every
        # available tool, so a stream with no call at all still names them.
        init = json.dumps({"type": "system", "subtype": "init",
                           "tools": ["mcp__boost__boost_search",
                                     "mcp__boost__boost_list"]})
        assert not MOD.called_boost(init)

    def test_narrating_a_check_without_making_one_is_a_miss(self):
        # An agent that says it will check and does not is a miss; the event
        # stream is the record, not the model's account of itself.
        assert not MOD.called_boost(json.dumps(
            {"type": "assistant", "message": {"content": [
                {"type": "text",
                 "text": "Let me check the skill registry with boost_search."}]}}))

    def test_installing_is_not_consulting(self):
        # `boost_install` is downstream of a decision already made. Counting it
        # would let a run that installed without looking score as a check.
        assert "boost_install" in MOD.BOOST_TOOLS
        assert "boost_install" not in MOD.CONSULT_TOOLS
        assert not MOD.called_boost(_assistant_call("boost_install"))

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


class TestStrictMcpConfigControlsTheSurfaceConfound:
    """`--strict-mcp-config` is the card's own fix for the confound
    `_report_surface` can only report: a crowded machine's other MCP servers
    move the call rate far more than any wording edit under test.
    """

    def test_the_config_names_only_boost(self):
        from boost_cli.core import mcphost
        cfg = MOD.strict_mcp_config("/usr/local/bin/boost")
        assert set(cfg["mcpServers"]) == {mcphost.SERVER_NAME}

    def test_the_entry_launches_boost_as_an_mcp_stdio_server(self):
        # Mirrors core.mcphost.register_argv's own invocation of boost, so a
        # config built here starts the exact same server a real registration
        # would — confirmed against a real `claude mcp add-json` write, not
        # guessed at.
        cfg = MOD.strict_mcp_config("/usr/local/bin/boost")
        entry = cfg["mcpServers"]["boost"]
        assert entry["command"] == "/usr/local/bin/boost"
        assert entry["args"] == ["mcp", "--stdio"]

    def test_the_entry_carries_the_fork_safety_env(self):
        # Without LAUNCH_ENV a real host can SIGABRT the boost subprocess
        # post-fork on macOS — the same failure core.mcphost.LAUNCH_ENV exists
        # to prevent for every other registration path.
        from boost_cli.core import mcphost
        cfg = MOD.strict_mcp_config("/usr/local/bin/boost")
        assert cfg["mcpServers"]["boost"]["env"] == mcphost.LAUNCH_ENV

    def test_run_claude_adds_no_flags_without_a_config(self, monkeypatch):
        captured = {}

        def fake_run(cmd, **kw):
            captured["cmd"] = cmd
            class P:
                stdout = ""
            return P()

        monkeypatch.setattr(MOD.subprocess, "run", fake_run)
        MOD.run_claude("hi", 5)
        assert "--strict-mcp-config" not in captured["cmd"]
        assert "--mcp-config" not in captured["cmd"]

    def test_run_claude_adds_both_flags_with_a_config(self, monkeypatch, tmp_path):
        captured = {}

        def fake_run(cmd, **kw):
            captured["cmd"] = cmd
            class P:
                stdout = ""
            return P()

        monkeypatch.setattr(MOD.subprocess, "run", fake_run)
        cfg_path = tmp_path / "mcp.json"
        cfg_path.write_text("{}", encoding="utf-8")
        MOD.run_claude("hi", 5, cfg_path)
        cmd = captured["cmd"]
        assert "--strict-mcp-config" in cmd
        i = cmd.index("--mcp-config")
        assert cmd[i + 1] == str(cfg_path)
