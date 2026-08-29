# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: scripts/eval_gate.py — the pass/fail decision itself.

The harness's arithmetic is pinned in test_eval_metrics.py. This file pins the
*verdict*: which combinations of floor breach, drop size and p-value mean "fail".
That logic decides whether a release ships once the gate is required, and it is
outside both other quality gates — coverage measures `boost_cli` only, and mutmut
mutates `boost_cli/core` only — so untested here means untested anywhere.

Synthetic result/baseline dicts throughout: no corpus, no retrieval, no network.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals import metrics  # noqa: E402


def _load_gate():
    """Import scripts/eval_gate.py by path — scripts/ is not a package.

    Same importlib shim tests/unit/test_eval_stats_summary.py uses.
    """
    spec = importlib.util.spec_from_file_location(
        "boost_eval_gate", ROOT / "scripts" / "eval_gate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gate = _load_gate()


def _results(per_query, arm="bm25", entries=57):
    """A results payload shaped like evals/results.json."""
    means = {m: metrics.mean([q[m] for q in per_query.values()])
             for m in metrics.METRIC_NAMES}
    return {"version": 1, "primary": arm, "metrics": list(metrics.METRIC_NAMES),
            "corpus": {"entries": entries, "docs": entries, "taps": 1},
            "golden": {"queries": len(per_query), "judgments": len(per_query)},
            "arms": {arm: {"mean": means, "per_query": per_query}}}


def _flat(value, n=20):
    """n queries all scoring `value` on every metric."""
    return {"q%02d" % i: dict.fromkeys(metrics.METRIC_NAMES, value)
            for i in range(n)}


class TestFloors:
    def test_all_metrics_above_their_floor_pass(self):
        assert gate.check_floors(dict.fromkeys(metrics.METRIC_NAMES, 0.99)) == []

    def test_exactly_on_the_floor_passes(self):
        """`>=`, not `>` — a floor is inclusive or it is a moving target."""
        assert gate.check_floors(dict(gate.FLOORS)) == []

    def test_a_hair_below_the_floor_fails(self):
        mean = {m: v - 0.001 for m, v in gate.FLOORS.items()}
        assert len(gate.check_floors(mean)) == len(gate.FLOORS)

    def test_names_the_metric_and_both_numbers(self):
        mean = dict(gate.FLOORS)
        mean["MRR"] = 0.10
        failures = gate.check_floors(mean)
        assert len(failures) == 1
        assert "MRR" in failures[0] and "0.10" in failures[0]

    def test_a_missing_metric_is_treated_as_zero_not_skipped(self):
        """A results file that lost a metric must fail, never silently pass."""
        assert len(gate.check_floors({})) == len(gate.FLOORS)

    def test_every_headline_metric_has_a_floor(self):
        assert set(gate.FLOORS) == set(metrics.METRIC_NAMES)


class TestRegressionVerdict:
    """The conjunction: fail only when the drop is BOTH big enough AND real."""

    def _run(self, base_v, cur_v, n=20, capsys=None):
        base = _results(_flat(base_v, n))
        cur = _results(_flat(cur_v, n))
        return gate.check_regressions(cur, base, gate.REGRESSION_EPS, gate.ALPHA)

    def test_identical_arms_do_not_fail(self):
        assert self._run(0.80, 0.80) == []

    def test_large_and_significant_drop_fails(self):
        failures = self._run(0.90, 0.40)
        assert len(failures) == len(metrics.METRIC_NAMES)
        assert "dropped" in failures[0]

    def test_improvement_never_fails(self):
        assert self._run(0.40, 0.90) == []

    def test_significant_but_tiny_drop_passes(self):
        """Below the epsilon, a real difference is still not worth a re-baseline."""
        assert self._run(0.800, 0.795) == []

    def test_large_but_insignificant_drop_passes(self):
        """One unlucky query out of many: big mean move, no statistical support."""
        base = _results(_flat(1.0, 30))
        cur = _results(_flat(1.0, 30))
        cur["arms"]["bm25"]["per_query"]["q00"] = dict.fromkeys(
            metrics.METRIC_NAMES, 0.0)
        failures = gate.check_regressions(cur, base, gate.REGRESSION_EPS,
                                          gate.ALPHA)
        assert failures == []

    def test_missing_baseline_arm_does_not_fail_the_build(self, capsys):
        base = _results(_flat(0.8), arm="catalog")
        cur = _results(_flat(0.4))
        assert gate.check_regressions(cur, base, gate.REGRESSION_EPS,
                                      gate.ALPHA) == []
        assert "re-pin" in capsys.readouterr().out

    def test_no_shared_queries_does_not_fail_the_build(self, capsys):
        base = _results({"old1": dict.fromkeys(metrics.METRIC_NAMES, 0.9)})
        cur = _results({"new1": dict.fromkeys(metrics.METRIC_NAMES, 0.1)})
        assert gate.check_regressions(cur, base, gate.REGRESSION_EPS,
                                      gate.ALPHA) == []
        assert "share no queries" in capsys.readouterr().out

    def test_queries_dropped_since_the_baseline_are_reported_not_hidden(self,
                                                                       capsys):
        """A shrinking comparison set is how a regression hides."""
        base = _results(_flat(0.9, 10))
        cur = _results({k: v for k, v in _flat(0.9, 10).items()
                        if k != "q09"})
        gate.check_regressions(cur, base, gate.REGRESSION_EPS, gate.ALPHA)
        out = capsys.readouterr().out
        assert "q09" in out and "absent" in out


class TestCorpusDrift:
    def test_same_entry_count_is_no_drift(self):
        assert gate.corpus_drift(_results(_flat(0.8)),
                                 _results(_flat(0.8))) is None

    def test_different_entry_count_is_refused(self):
        msg = gate.corpus_drift(_results(_flat(0.8), entries=56),
                                _results(_flat(0.8), entries=57))
        assert msg and "57" in msg and "56" in msg

    def test_absent_baseline_is_not_drift(self):
        assert gate.corpus_drift(_results(_flat(0.8)), None) is None

    def test_baseline_without_a_corpus_block_is_tolerated(self):
        old = _results(_flat(0.8))
        del old["corpus"]
        assert gate.corpus_drift(_results(_flat(0.8)), old) is None


class TestCalibration:
    """The constants are the gate. Pin them so a tweak is a deliberate diff."""

    def test_regression_epsilon(self):
        assert gate.REGRESSION_EPS == 0.02

    def test_alpha_is_the_conventional_five_percent(self):
        assert gate.ALPHA == 0.05

    def test_floors_sit_below_the_committed_baseline(self):
        """Every floor must have real headroom under the pinned scores.

        A floor at or above the baseline would fail the moment anything moved;
        one far below would never fire. The calibration policy is ~0.05 under.
        """
        import json
        baseline = json.loads(
            (ROOT / "evals" / "baseline.json").read_text(encoding="utf-8"))
        pinned = baseline["arms"][baseline["primary"]]["mean"]
        for m, floor in gate.FLOORS.items():
            assert floor < pinned[m], "%s floor %.3f is not below the pinned %.3f" % (
                m, floor, pinned[m])
            assert pinned[m] - floor < 0.12, (
                "%s floor %.3f is too slack under the pinned %.3f"
                % (m, floor, pinned[m]))


class TestBaselineIsMachineIndependent:
    def test_no_absolute_path_is_committed(self):
        """The baseline ships in the PyPI sdist; it must carry no local path."""
        text = (ROOT / "evals" / "baseline.json").read_text(encoding="utf-8")
        # S108 is suppressed on the next line: flake8-bandit reads these path
        # literals as a temp-file write. They are needles searched for inside a
        # repo file that was already read above, never opened.
        for needle in ("/Users/", "/home/", "/private/tmp", "/tmp/"):  # noqa: S108
            assert needle not in text, "baseline.json leaks %r" % needle
