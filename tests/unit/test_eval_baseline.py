# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: the eval gate's baseline bookkeeping and metric floors.

Two defects motivate this file, both observed by running the shipped harness:

1. **The baseline is not keyed to the query set that produced it.**
   `tests/eval/baseline.json` records only `k` and per-engine metrics. Running
   `scripts/eval_retrieval.py --golden tests/eval/golden-natural.jsonl` against
   it therefore reports eight confident "REGRESSION vs baseline" lines — BM25
   recall 1.000 -> 0.690, hit@1 0.780 -> 0.240 and so on — which are not
   regressions at all. They are the difference between two different question
   sets. Worse, `--save-baseline` on the natural set would overwrite the keyword
   set's numbers with them, silently.

2. **`--fail-under` floors `recall@k` and nothing else.** All four metrics are
   computed and printed; only one can fail the build. A total `hit@1` collapse
   from 0.780 to 0.000 passes the gate, which is the concrete way the roadmap
   item's "no retrieval work in this repo is falsifiable" shows up in code.

Synthetic results and baselines throughout — no corpus, no retrieval, no
network — so these pin the verdict logic rather than any measured score.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_eval():
    """Import scripts/eval_retrieval.py by path — scripts/ is not a package."""
    spec = importlib.util.spec_from_file_location(
        "boost_eval_retrieval", ROOT / "scripts" / "eval_retrieval.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["boost_eval_retrieval"] = mod
    spec.loader.exec_module(mod)
    return mod


ev = _load_eval()

KEYWORD = ROOT / "tests" / "eval" / "golden.jsonl"
NATURAL = ROOT / "tests" / "eval" / "golden-natural.jsonl"


def _result(engine="BM25 full-content", **metrics):
    base = {"recall@k": 1.0, "hit@1": 0.78, "MRR": 0.86, "nDCG@k": 0.89}
    base.update(metrics)
    return {"engine": engine, "agg": {"overall": base}, "n": 91}


@pytest.fixture()
def baseline(tmp_path, monkeypatch):
    """Redirect the module's BASELINE constant at a throwaway file."""
    p = tmp_path / "baseline.json"
    monkeypatch.setattr(ev, "BASELINE", p)
    return p


class TestBaselineIsKeyedToItsQuerySet:
    """A baseline only means something against the questions that produced it."""

    def test_saving_two_sets_keeps_both(self, baseline):
        ev.save_baseline(10, [_result()], golden=KEYWORD)
        ev.save_baseline(10, [_result(**{"recall@k": 0.69, "hit@1": 0.24})],
                         golden=NATURAL)
        data = json.loads(baseline.read_text())
        keys = set(data["sets"])
        assert len(keys) == 2, "one set's baseline overwrote the other: %s" % keys

    def test_natural_run_is_not_graded_against_keyword_numbers(self, baseline):
        # The observed bug: 1.000 -> 0.690 reported as a regression when it is
        # simply a different, harder question set.
        ev.save_baseline(10, [_result()], golden=KEYWORD)
        natural = [_result(**{"recall@k": 0.69, "hit@1": 0.24,
                              "MRR": 0.38, "nDCG@k": 0.45})]
        assert ev.check_regressions(natural, eps=0.02, golden=NATURAL) == []

    def test_same_set_still_catches_a_real_drop(self, baseline):
        # The guard must not disable regression detection wholesale.
        ev.save_baseline(10, [_result()], golden=KEYWORD)
        worse = [_result(**{"recall@k": 0.50})]
        problems = ev.check_regressions(worse, eps=0.02, golden=KEYWORD)
        assert problems and "recall@k" in problems[0]

    def test_content_change_invalidates_the_baseline(self, baseline, tmp_path):
        # Editing the queries changes what the numbers mean, even under the same
        # filename — so identity is the content, not the path.
        golden = tmp_path / "golden.jsonl"
        golden.write_text('{"query": "a", "relevant": ["x"], "kind": "skill"}\n')
        ev.save_baseline(10, [_result()], golden=golden)
        golden.write_text('{"query": "b", "relevant": ["y"], "kind": "skill"}\n')
        assert ev.check_regressions([_result(**{"recall@k": 0.1})],
                                    eps=0.02, golden=golden) == []


class TestBackCompat:
    """An existing flat baseline.json must keep working, not silently stop."""

    def test_flat_baseline_still_grades_the_default_set(self, baseline):
        baseline.write_text(json.dumps({
            "k": 10,
            "engines": {"BM25 full-content": {
                "recall@k": 1.0, "hit@1": 0.78, "MRR": 0.86, "nDCG@k": 0.89}},
        }))
        problems = ev.check_regressions([_result(**{"hit@1": 0.10})],
                                        eps=0.02, golden=KEYWORD)
        assert problems, "a pre-existing baseline stopped catching regressions"

    def test_flat_baseline_is_not_applied_to_another_set(self, baseline):
        baseline.write_text(json.dumps({
            "k": 10,
            "engines": {"BM25 full-content": {
                "recall@k": 1.0, "hit@1": 0.78, "MRR": 0.86, "nDCG@k": 0.89}},
        }))
        assert ev.check_regressions([_result(**{"hit@1": 0.10})],
                                    eps=0.02, golden=NATURAL) == []


class TestMetricFloors:
    """Every reported metric must be gateable, not just recall@k."""

    def test_hit_at_1_collapse_fails_even_with_perfect_recall(self):
        # The headline hole: recall@10 = 1.000 with hit@1 = 0.000 means the
        # right answer is always found and never ranked first. That is a broken
        # ranker, and the shipped gate passes it.
        breaches = ev.check_floors(_result(**{"recall@k": 1.0, "hit@1": 0.0}),
                                   {"recall@k": 0.85, "hit@1": 0.65})
        assert len(breaches) == 1
        assert "hit@1" in breaches[0]

    def test_all_metrics_within_floor_is_clean(self):
        assert ev.check_floors(_result(), {"recall@k": 0.85, "hit@1": 0.65,
                                           "MRR": 0.74, "nDCG@k": 0.78}) == []

    def test_every_breach_is_reported_not_just_the_first(self):
        # A one-line failure hides how far the run actually fell.
        breaches = ev.check_floors(
            _result(**{"recall@k": 0.1, "hit@1": 0.1, "MRR": 0.1, "nDCG@k": 0.1}),
            {"recall@k": 0.85, "hit@1": 0.65, "MRR": 0.74, "nDCG@k": 0.78})
        assert len(breaches) == 4

    def test_floor_exactly_met_passes(self):
        # >= not >, so a floor set to the measured value is not self-failing.
        assert ev.check_floors(_result(**{"hit@1": 0.65}), {"hit@1": 0.65}) == []

    def test_unknown_metric_in_a_floor_is_an_error_not_a_silent_pass(self):
        # A typo'd floor name that silently passes is worse than no floor.
        with pytest.raises(SystemExit):
            ev.check_floors(_result(), {"recall@10": 0.85})


class TestFloorParsing:
    """`--floor name=value`, the CLI surface for the above."""

    def test_parses_pairs(self):
        assert ev.parse_floors(["hit@1=0.65", "MRR=0.74"]) == {
            "hit@1": 0.65, "MRR": 0.74}

    def test_rejects_a_missing_value(self):
        with pytest.raises(SystemExit):
            ev.parse_floors(["hit@1"])

    def test_rejects_a_non_numeric_value(self):
        with pytest.raises(SystemExit):
            ev.parse_floors(["hit@1=high"])

    def test_rejects_an_unknown_metric_before_the_run(self):
        # Validated at parse time, not gate time: a typo used to surface only
        # after several minutes of tapping and retrieval had already happened.
        with pytest.raises(SystemExit):
            ev.parse_floors(["recall@10=0.85"])

    def test_empty_is_no_floors(self):
        assert ev.parse_floors([]) == {}
