#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Mutation-strength gate: fail unless >= MIN_SCORE% of mutants are killed.

Usage:  python3 scripts/mutation_gate.py [--run] [--min 80]

  --run   run `mutmut run` first (otherwise gate the existing results)

Score = killed / (total - skipped). "no tests" mutants count against the
score — untested code is unkilled mutants by definition.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MUTMUT = ROOT / ".venv" / "bin" / "mutmut"
STATS = ROOT / "mutants" / "mutmut-cicd-stats.json"


def sh(*args: str) -> int:
    return subprocess.call(args, cwd=ROOT)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true", help="run mutmut first")
    ap.add_argument("--min", type=float, default=80.0, help="minimum kill %%")
    args = ap.parse_args()

    mutmut = str(MUTMUT if MUTMUT.exists() else shutil.which("mutmut") or "mutmut")
    if args.run:
        rc = sh(mutmut, "run")
        if rc not in (0, 2):  # mutmut exits nonzero when mutants survive
            print("mutation gate: `mutmut run` failed to execute (rc %d)" % rc)
            return 2
    if sh(mutmut, "export-cicd-stats") != 0 or not STATS.exists():
        print("mutation gate: no mutation results — run `make mutation`")
        return 2

    s = json.loads(STATS.read_text(encoding="utf-8"))
    denominator = s["total"] - s.get("skipped", 0)
    score = 100.0 * s["killed"] / denominator if denominator else 0.0
    print("mutation gate: %d/%d killed (%.1f%%) — survived %d, no-tests %d, "
          "timeout %d, suspicious %d"
          % (s["killed"], denominator, score, s.get("survived", 0),
             s.get("no_tests", 0), s.get("timeout", 0), s.get("suspicious", 0)))
    if score < args.min:
        print("mutation gate: FAIL — %.1f%% < %.1f%% minimum" % (score, args.min))
        return 1
    print("mutation gate: PASS (>= %.1f%%)" % args.min)
    return 0


if __name__ == "__main__":
    sys.exit(main())
