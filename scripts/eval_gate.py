#!/usr/bin/env python3
"""Retrieval-quality gate: fail on a floor breach or a significant regression.

Usage:  python3 scripts/eval_gate.py [--run] [--results evals/results.json]

  --run   run evals/run_evals.py first (otherwise gate the existing results)

Two independent checks, both must pass:

  1. ABSOLUTE FLOOR   each metric of the primary arm must clear its floor.
     Catches "the ranker got worse over many small merges", which a
     regression-vs-last-commit check never notices.

  2. SIGNIFICANT REGRESSION vs evals/baseline.json — a metric fails only when it
     drops by more than --regression-eps AND a paired bootstrap over the
     per-query deltas says p < --alpha. Both conditions are required on purpose:
     a drop that is large but not significant is one unlucky query, and a drop
     that is significant but tiny is a rounding change nobody should have to
     re-baseline for. Requiring both is what keeps this gate from flaking.

Mirrors scripts/mutation_gate.py: a small script that reads a result file,
prints what it measured, and returns 0/1/2. Re-baseline deliberately with
`make evals-baseline`.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals import metrics  # noqa: E402

RESULTS = ROOT / "evals" / "results.json"
BASELINE = ROOT / "evals" / "baseline.json"

# Absolute floors for the primary (BM25) arm.
#
# CALIBRATION — measured on the first full run of the 36-query hermetic golden
# set over the 57-item generated corpus (evals/baseline.json holds the same
# numbers). Each floor is set ~0.05 below the observed score, which is the
# documented policy: wide enough that ordinary indexing or tokenizer churn
# cannot flake the gate red, tight enough that a real ranking regression cannot
# hide inside the margin.
#
#     metric      observed   floor
#     recall@5      0.507     0.45
#     recall@10     0.602     0.55
#     MRR           0.838     0.78
#     nDCG@5        0.692     0.64
#     nDCG@10       0.714     0.66
#
# Raise a floor only after the higher score has held for a release; lowering one
# is a decision to make explicitly in review, not a way to make CI green.
FLOORS: Dict[str, float] = {
    "recall@5": 0.45,
    "recall@10": 0.55,
    "MRR": 0.78,
    "nDCG@5": 0.64,
    "nDCG@10": 0.66,
}

# A metric must fall this far below the baseline before significance is even
# considered. 0.02 is below the smallest change a single query can make to the
# mean of a 36-query set (1/36 = 0.028 in the worst case), so a one-query blip
# is filtered by the significance half of the test rather than by this.
REGRESSION_EPS = 0.02
ALPHA = 0.05


def load(path: Path, what: str) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print("eval gate: cannot read %s (%s) — %s" % (what, path.name, e))
        return None


def check_floors(mean: Dict[str, float]) -> List[str]:
    failures = []
    print("eval gate: absolute floors")
    for name in metrics.METRIC_NAMES:
        got, floor = mean.get(name, 0.0), FLOORS[name]
        ok = got >= floor
        print("  %-10s %.3f  (floor %.2f)  %s"
              % (name, got, floor, "PASS" if ok else "FAIL"))
        if not ok:
            failures.append("%s %.3f < floor %.2f" % (name, got, floor))
    return failures


def check_regressions(current: dict, baseline: dict, eps: float,
                      alpha: float) -> List[str]:
    """Paired-bootstrap each metric against the baseline's per-query scores."""
    arm = current["primary"]
    cur_q = current["arms"][arm]["per_query"]
    base_arm = baseline.get("arms", {}).get(arm)
    if not base_arm:
        print("eval gate: baseline has no %r arm — re-pin with "
              "`make evals-baseline`" % arm)
        return []
    base_q = base_arm["per_query"]

    shared = sorted(set(cur_q) & set(base_q))
    missing = sorted(set(base_q) - set(cur_q))
    if not shared:
        print("eval gate: baseline and results share no queries — re-pin with "
              "`make evals-baseline`")
        return []
    if missing:
        # Never silent: a shrinking comparison set is how a regression hides.
        print("eval gate: NOTE — %d baseline queries are absent from this run "
              "(%s); comparing the %d shared ones"
              % (len(missing), ", ".join(missing[:5]), len(shared)))

    failures = []
    print("\neval gate: regression vs baseline (paired bootstrap, %d resamples, "
          "%d queries)" % (metrics.RESAMPLES, len(shared)))
    print("  %-10s %9s %9s %9s %9s  %s"
          % ("metric", "baseline", "current", "delta", "p", "verdict"))
    for name in metrics.METRIC_NAMES:
        b = [base_q[q][name] for q in shared]
        c = [cur_q[q][name] for q in shared]
        r = metrics.paired_bootstrap(b, c)
        drop = -r["delta"]
        significant = r["p_value"] < alpha
        bad = drop > eps and significant
        if bad:
            verdict = "FAIL (significant regression)"
            failures.append("%s dropped %.3f (p=%.4f)" % (name, drop, r["p_value"]))
        elif drop > eps:
            verdict = "ok (drop > %.2f but not significant)" % eps
        elif significant and r["delta"] > 0:
            verdict = "ok (significant improvement)"
        else:
            verdict = "ok"
        print("  %-10s %9.3f %9.3f %+9.3f %9.4f  %s"
              % (name, metrics.mean(b), metrics.mean(c), r["delta"],
                 r["p_value"], verdict))
    return failures


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="store_true",
                    help="run evals/run_evals.py before gating")
    ap.add_argument("--results", type=Path, default=RESULTS)
    ap.add_argument("--baseline", type=Path, default=BASELINE)
    ap.add_argument("--regression-eps", type=float, default=REGRESSION_EPS,
                    metavar="E", help="minimum drop to consider (default %.2f)"
                                      % REGRESSION_EPS)
    ap.add_argument("--alpha", type=float, default=ALPHA, metavar="A",
                    help="significance level (default %.2f)" % ALPHA)
    args = ap.parse_args(argv)

    if args.run:
        rc = subprocess.call([sys.executable, str(ROOT / "evals" / "run_evals.py"),
                              "--out", str(args.results), "--quiet"],
                             cwd=str(ROOT))
        if rc != 0:
            print("eval gate: the eval run failed (rc %d)" % rc)
            return 2

    current = load(args.results, "results")
    if current is None:
        print("eval gate: no results — run `make evals`")
        return 2
    arm = current.get("primary")
    if not arm or arm not in current.get("arms", {}):
        print("eval gate: results file has no primary arm — regenerate it")
        return 2

    mean = current["arms"][arm]["mean"]
    print("eval gate: %d queries over %d corpus entries, primary arm %r"
          % (current["golden"]["queries"], current["corpus"]["entries"], arm))
    failures = check_floors(mean)

    baseline = load(args.baseline, "baseline")
    if baseline is None:
        print("\neval gate: no baseline pinned — floors only. "
              "Run `make evals-baseline` to enable regression testing.")
    else:
        failures += check_regressions(current, baseline, args.regression_eps,
                                      args.alpha)

    faith = current.get("faithfulness")
    if faith:
        print("\neval gate: faithfulness %s"
              % ("mean %.3f (n=%d)" % (faith["mean"], faith["n"])
                 if faith.get("status") == "ok"
                 else "skipped — %s" % faith.get("reason", "")))

    if failures:
        print("\neval gate: FAIL")
        for f in failures:
            print("  - %s" % f)
        return 1
    print("\neval gate: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
